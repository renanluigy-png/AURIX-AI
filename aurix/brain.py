"""Conversational model with safe, validated desktop tools."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable

from aurix.agent_tools import execute_tool, ollama_tools, openai_tools
from aurix.commands import (
    APP_ALIASES,
    ParsedCommand,
    execute_command,
    normalize_text,
    parse_command,
)


SYSTEM_PROMPT = (
    "Você é AURIX, uma IA generativa assistente pessoal para desktop. Fale em português brasileiro "
    "com naturalidade, use o contexto recente da conversa e não dependa de frases exatas. Quando o "
    "usuário pedir uma ação compatível com suas ferramentas, chame a ferramenta apropriada em vez de "
    "apenas descrever o que faria. Você pode abrir aplicativos permitidos, controlar teclas de mídia "
    "do Windows, abrir sites, iniciar uma pesquisa no navegador, consultar data/hora, abrir pastas "
    "padrão e criar notas. Aguarde o resultado real da ferramenta antes de confirmar a execução. "
    "Se uma tarefa tiver várias etapas, execute apenas as etapas permitidas e informe claramente "
    "quais foram concluídas. Não invente ferramentas nem alegue acesso a arquivos, mensagens, tela, "
    "câmera ou dados que não foram disponibilizados. Não execute comandos arbitrários de terminal, "
    "não apague arquivos, não instale software sem consentimento e não envie mensagens sem confirmação. "
    "Uma pesquisa na web abre o navegador; isso não significa que você leu ou verificou o conteúdo da página. "
    "Para ações indisponíveis, explique o limite e ofereça um caminho seguro."
)


def _simple_local_command(prompt: str) -> ParsedCommand | None:
    """Route unambiguous one-step commands without loading or querying the LLM."""
    parsed = parse_command(prompt)
    if parsed is None:
        return None

    normalized = normalize_text(prompt)
    if parsed.name == "time":
        return parsed if normalized in {"que horas sao", "horas sao", "hora atual", "what time is it"} else None
    if parsed.name == "date":
        return parsed if normalized in {"qual e a data", "data de hoje", "que dia e hoje", "what is the date"} else None

    if parsed.name == "open_app":
        match = re.match(
            r"^(?:por favor[,]?\s+)?(?:abra|abrir|abre|inicie|iniciar|inicia|execute|executa|lance|lancar|open|start)\s+"
            r"(?:(?:o|a|os|as)\s+)?(?:(?:aplicativo|app|programa)\s+)?(.+)$",
            normalized,
        )
        if not match:
            return None
        requested = match.group(1).strip()
        requested = re.sub(r"\s+(?:por favor|para mim|please)$", "", requested)
        return parsed if requested in APP_ALIASES else None

    if parsed.name == "search_web":
        # If the user asks for a summary/explanation as well, the model should interpret it.
        if re.search(r"\b(?:e me (?:explique|diga|resuma|traga)|resuma|explique|leia|summarize)\b", normalized):
            return None
        return parsed

    return None


class AssistantBrain:
    """Generative assistant with a bounded tool loop and a small deterministic fast path."""

    MAX_TOOL_ROUNDS = 3

    def __init__(self) -> None:
        self.provider = os.getenv("AURIX_LLM_PROVIDER", "auto").strip().lower()
        self.history: list[dict[str, str]] = []

    def respond(self, prompt: str, status_callback: Callable[[str], None] | None = None) -> str:
        direct_command = _simple_local_command(prompt)
        if direct_command is not None:
            try:
                answer = execute_command(direct_command)
            except Exception as exc:
                return f"Não consegui concluir essa ação: {str(exc).splitlines()[0][:180]}"
            self._remember("user", prompt)
            self._remember("assistant", answer)
            return answer

        provider = self._selected_provider()
        if provider == "none":
            return self._local_fallback(prompt, explain=True)

        try:
            if provider == "openai":
                if status_callback:
                    status_callback("Consultando a IA online…")
                answer = self._respond_openai(prompt)
            elif provider == "ollama":
                answer = self._respond_ollama(prompt, status_callback)
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
                "Não consegui acessar ou concluir a solicitação com o provedor de IA. Confira sua "
                "configuração e se o Ollama está ativo. Detalhe: " + detail
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
                max_output_tokens=700,
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
                except Exception as exc:
                    result = f"A ação não foi concluída: {str(exc).splitlines()[0][:160]}"
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": str(result),
                })
        return "Cheguei ao limite de etapas desta solicitação. Divida a tarefa em partes menores."

    def _respond_ollama(
        self,
        prompt: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> str:
        base_url = os.getenv("AURIX_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        model = os.getenv("AURIX_OLLAMA_MODEL", "qwen2.5:3b")
        if status_callback:
            status_callback("Verificando modelo local…")
        self._ensure_ollama_model(base_url, model, status_callback)

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        for _ in range(self.MAX_TOOL_ROUNDS + 1):
            if status_callback:
                status_callback("IA local processando…")
            payload = json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "tools": ollama_tools(),
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {
                        "temperature": 0.25,
                        "num_ctx": 4096,
                        "num_predict": 500,
                    },
                },
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                f"{base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=75) as response:
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
                try:
                    result = execute_tool(name, arguments)
                except Exception as exc:
                    result = f"A ação falhou: {str(exc).splitlines()[0][:160]}"
                messages.append({"role": "tool", "content": str(result)})

        return "Cheguei ao limite de etapas desta solicitação. Divida a tarefa em partes menores."

    def _local_fallback(self, prompt: str, explain: bool = False) -> str:
        """Offline fallback only runs clear, supported one-step commands."""
        parsed = _simple_local_command(prompt)
        if parsed:
            return execute_command(parsed)
        if explain:
            return (
                "Ainda não há um provedor de IA generativa configurado. Posso executar alguns "
                "comandos simples conhecidos, mas para conversar com linguagem natural e decidir "
                "entre ferramentas, configure uma chave da OpenAI API ou conecte o Ollama em "
                "Configurações do AURIX."
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

    def _ensure_ollama_model(
        self,
        base_url: str,
        model: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Check the local model and report progress while downloading it if needed."""
        try:
            self._ollama_post(base_url, "api/show", {"model": model}, timeout=8)
            return
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        except RuntimeError as exc:
            if "not found" not in str(exc).casefold() and "does not exist" not in str(exc).casefold():
                raise

        request = urllib.request.Request(
            f"{base_url}/api/pull",
            data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if status_callback:
            status_callback("Baixando o modelo de IA local pela primeira vez…")
        with urllib.request.urlopen(request, timeout=1800) as response:
            for raw_line in response:
                if not raw_line.strip():
                    continue
                item = json.loads(raw_line.decode("utf-8"))
                if item.get("error"):
                    raise RuntimeError(str(item["error"]))
                total = int(item.get("total") or 0)
                completed = int(item.get("completed") or 0)
                status = str(item.get("status") or "Baixando modelo")
                if status_callback:
                    if total > 0:
                        percent = min(100, int(completed * 100 / total))
                        status_callback(f"Baixando modelo local… {percent}%")
                    else:
                        status_callback(f"Preparando modelo local… {status[:72]}")
