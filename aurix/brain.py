"""Optional cloud/local conversation provider."""

from __future__ import annotations

import json
import os
import urllib.request


SYSTEM_PROMPT = (
    "Você é AURIX, um assistente pessoal para desktop que fala português brasileiro. "
    "Seja claro, prestativo e relativamente conciso. Você pode conversar e orientar o usuário, "
    "mas não tem permissão para executar ações no computador a menos que o aplicativo informe "
    "explicitamente que uma ação permitida foi realizada. Nunca alegue que abriu programas, "
    "alterou arquivos ou enviou mensagens. Não peça nem revele chaves de API e senhas."
)


class AssistantBrain:
    """Routes messages to OpenAI, Ollama, or a transparent setup hint."""

    def __init__(self) -> None:
        self.provider = os.getenv("AURIX_LLM_PROVIDER", "auto").strip().lower()
        self.history: list[dict[str, str]] = []

    def respond(self, prompt: str) -> str:
        provider = self._selected_provider()
        try:
            if provider == "openai":
                answer = self._respond_openai(prompt)
            elif provider == "ollama":
                answer = self._respond_ollama(prompt)
            else:
                return (
                    "Os comandos locais estão funcionando, mas a conversa com IA ainda não está "
                    "configurada. Defina OPENAI_API_KEY em um arquivo .env local ou instale o "
                    "Ollama e configure AURIX_LLM_PROVIDER=ollama."
                )
            answer = answer.strip()
            if not answer:
                return "Não recebi uma resposta útil do modelo. Pode tentar novamente?"
            self._remember("user", prompt)
            self._remember("assistant", answer)
            return answer
        except Exception as exc:
            detail = str(exc).strip().splitlines()[0][:180]
            if not detail:
                detail = exc.__class__.__name__
            return (
                "Não consegui acessar o provedor de IA agora. Verifique a conexão, a chave ou "
                f"se o Ollama está em execução. Detalhe: {detail}"
            )

    def _selected_provider(self) -> str:
        if self.provider in {"openai", "ollama", "none"}:
            return self.provider
        if os.getenv("OPENAI_API_KEY", "").strip():
            return "openai"
        return "ollama"

    def _respond_openai(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        messages = [{"role": item["role"], "content": item["content"]} for item in self.history]
        messages.append({"role": "user", "content": prompt})
        response = client.responses.create(
            model=os.getenv("AURIX_OPENAI_MODEL", "gpt-5-mini"),
            instructions=SYSTEM_PROMPT,
            input=messages,
            max_output_tokens=700,
        )
        return response.output_text or ""

    def _respond_ollama(self, prompt: str) -> str:
        base_url = os.getenv("AURIX_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        model = os.getenv("AURIX_OLLAMA_MODEL", "llama3.2")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})
        payload = json.dumps(
            {"model": model, "messages": messages, "stream": False},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body.get("message", {}).get("content", ""))

    def _remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # Keep a short in-memory conversation; history is not persisted to disk.
        self.history = self.history[-12:]
