"""AI conversation loop with validated tool calling (OpenAI Responses API or Ollama)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from aurix.agent_tools import execute_tool, ollama_tools, openai_tools
from aurix.commands import execute_command, parse_command


SYSTEM_PROMPT = (
    "Você é AURIX, uma IA assistente pessoal para desktop, fala português brasileiro e "
    "conversa naturalmente, como um copiloto inteligente. Entenda intenção e contexto, peça "
    "esclarecimento quando faltar uma informação importante e não dependa de frases exatas. "
    "Você tem ferramentas para abrir aplicações, abrir sites solicitados, pesquisar na web, "
    "consultar data/hora, abrir pastas padrão e criar notas. Use as ferramentas quando forem "
    "necessárias para fazer algo, então explique o resultado com base na saída real da ferramenta. "
    "Nunca diga que executou algo sem receber uma saída de sucesso. Não tente contornar as "
    "ferramentas, não invente ferramentas nem alegue acesso a arquivos, mensagens, tela, câmera "
    "ou outros dados que não foram disponibilizados. Para ações não disponíveis, explique o limite. "
    "Não execute nem solicite comandos de terminal arbitrários, não apague arquivos e não envie "
    "mensagens sem um fluxo separado de confirmação. Se o usuário pede algo que exigiria uma ação "
    "que não está entre as ferramentas, explique que essa capacidade ainda não foi implementada."
)


class AssistantBrain:
    """Conversational model with a bounded agent loop and safe local fallback."""

    MAX_TOOL_ROUNDS = 4

    def __init__(self) -> None:
        self.provider = os.getenv("AURIX_LLM_PROVIDER", "auto").strip().lower()
        self.history: list[dict[str, str]] = []

    def respond(self, prompt: str) -> str:
        provider = self._selected_provider()
        if provider == "none":
            return self._local_fallback(prompt, explain=True)

        try:
            if provider == "openai":
                answer = self._respond_openai(prompt)
            elif provider == "ollama":
                answer = self._respond_ollama(prompt)
            else:
                return self._local_fallback(prompt, explain=True)

            answer = answer.strip()
            if not answer:
                return "Não recebi uma resposta útil do modelo. Pode tentar de outra forma?"
            self._remember("user", prompt)
            self._remember("assistant", answer)
            return answer
        except Exception as exc:
            detail = str(exc).strip().splitlines()[0][:180] or exc.__class__.__name__
            return (
                "Não consegui acessar o provedor de IA. Confira sua configuração, conexão ou "
                f"se o Ollama e o modelo estão ativos. Detalhe: {detail}"
            )

    def _selected_provider(self) -> str:
        if self.provider in {"openai", "ollama", "none"}:
            if self.provider == "openai" and not os.getenv("OPENAI_API_KEY", "").strip():
                return "none"
            return self.provider
        if os.getenv("OPENAI_API_KEY", "").strip():
            return "openai"
        return "ollama"

    def _respond_openai(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        input_items: list = [
            {"role": item["role"], "content": item["content"]} for item in self.history
        ]
        input_items.append({"role": "user", "content": prompt})

        for _ in range(self.MAX_TOOL_ROUNDS + 1):
            response = client.responses.create(
                model=os.getenv("AURIX_OPENAI_MODEL", "gpt-5-mini"),
                instructions=SYSTEM_PROMPT,
                input=input_items,
                tools=openai_tools(),
                tool_choice="auto",
                max_output_tokens=900,
            )
            calls = [
                item for item in response.output
                if getattr(item, "type", None) == "function_call"
            ]
            if not calls:
                return str(response.output_text or "")
            input_items.extend(response.output)
            for call in calls:
                if not getattr(call, "call_id", None):
                    continue
                try:
                    args = json.loads(call.arguments or "{}")
                    result = execute_tool(call.name, args)
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    result = f"Ação recusada por argumentos inválidos: {exc}"
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": str(result),
                })
        return "Executei o limite de ações desta solicitação. Resuma o próximo passo ou divida a tarefa em partes."

    def _respond_ollama(self, prompt: str) -> str:
        base_url = os.getenv("AURIX_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        model = os.getenv("AURIX_OLLAMA_MODEL", "llama3.2")
        self._ensure_ollama_model(base_url, model)
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        for _ in range(self.MAX_TOOL_ROUNDS + 1):
            payload = json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "tools": ollama_tools(),
                    "stream": False,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                f"{base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))

            message = body.get("message") or {}
            calls = message.get("tool_calls") or []
            if not calls:
                return str(message.get("content", ""))

            messages.append(message)
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name", ""))
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                result = execute_tool(name, arguments)
                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": str(result),
                })

        return "Executei o limite de ações desta solicitação. Divida a tarefa em etapas menores."

    def _local_fallback(self, prompt: str, explain: bool = False) -> str:
        """Only a small offline fallback; natural conversation requires an AI provider."""
        parsed = parse_command(prompt)
        if parsed:
            return execute_command(parsed)
        if explain:
            return (
                "Ainda não há um modelo de IA configurado. O AURIX consegue executar alguns "
                "comandos locais simples, mas para conversar com linguagem natural e decidir "
                "entre ferramentas, configure uma chave da OpenAI API ou conecte um modelo Ollama "
                "na opção Configurações do AURIX."
            )
        return "Não consigo responder sem um provedor de IA configurado."

    @staticmethod
    def _ollama_post(base_url: str, endpoint: str, payload: dict, timeout: float) -> dict:
        request = urllib.request.Request(
            f"{base_url}/{endpoint.lstrip('/')}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise RuntimeError("O Ollama retornou uma resposta inválida.")
        if body.get("error"):
            raise RuntimeError(str(body["error"]))
        return body

    def _ensure_ollama_model(self, base_url: str, model: str) -> None:
        """Pull a missing local model through Ollama after the user selected local AI."""
        try:
            self._ollama_post(base_url, "api/show", {"model": model}, timeout=12)
            return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        except RuntimeError as exc:
            if "not found" not in str(exc).casefold() and "does not exist" not in str(exc).casefold():
                raise

        # Ollama's non-streaming pull endpoint downloads the weights into its own model store.
        # This can take a while for multi-gigabyte models; it runs on the request worker, not the UI.
        self._ollama_post(
            base_url,
            "api/pull",
            {"model": model, "stream": False},
            timeout=1800,
        )

    def _remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # Short-lived history only; never persist private conversations by default.
        self.history = self.history[-12:]
