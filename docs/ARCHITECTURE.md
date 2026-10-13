# Arquitetura do AURIX AI

## Objetivo

Manter o assistente ativo em segundo plano no Windows. O HUD só aparece quando o usuário o chama por voz, pelo ícone da bandeja ou pelo atalho global Ctrl+Alt+Espaço.

## Componentes

- aurix.app: ciclo de vida da aplicação, bandeja do sistema, hotkey e execução assíncrona das solicitações.
- aurix.hud: janela frameless, sempre no topo, com núcleo animado e campo de comando.
- aurix.voice: captura PCM a 16 kHz, detecção local da palavra “Hey Jarvis”, detecção simples de silêncio e transcrição.
- aurix.commands: parser determinístico e allowlist de ações locais.
- aurix.brain: provedor conversacional opcional OpenAI Responses API ou Ollama local.
- aurix.config: preferências não secretas no perfil do usuário e integração de inicialização do Windows.

## Ciclo da voz

1. Um fluxo de áudio de 16 kHz é processado localmente por openWakeWord.
2. Após detectar “Hey Jarvis”, o HUD aparece e o assistente coleta um trecho curto, encerrando após silêncio ou limite máximo.
3. Por padrão, SpeechRecognition envia o trecho para Google Speech Recognition, com idioma pt-BR. A transcrição local opcional via Vosk pode ser configurada com AURIX_SPEECH_PROVIDER=vosk e AURIX_VOSK_MODEL_PATH.
4. A transcrição passa primeiro pelo parser de comandos conhecidos. Somente se não corresponder a um comando permitido é enviada ao provedor conversacional.
5. Em pedidos por voz, a resposta pode ser falada por pyttsx3.

O modelo openWakeWord pré-treinado é em inglês e reconhece “Hey Jarvis”, não somente “Jarvis”. O modelo é baixado na primeira execução; o resultado varia com o ambiente acústico.

## Fronteira de segurança

A IA conversacional não possui uma ferramenta de shell. As ações locais são escolhidas pelo parser a partir de nomes de comandos fixos. Não existe execução de texto arbitrário com shell=True. Operações destrutivas, envio de mensagens, automação de cliques e acesso irrestrito aos arquivos foram deixados fora deste MVP.

A chave da OpenAI é lida da variável de ambiente OPENAI_API_KEY/arquivo .env local e nunca é persistida nas preferências. O histórico conversacional é limitado e permanece apenas em memória.

## Dependências de voz

- openwakeword + sounddevice: detector de ativação e stream do microfone.
- SpeechRecognition: transcrição online padrão por Google Speech Recognition.
- vosk (opcional): transcrição local; o usuário precisa baixar separadamente um modelo de português e apontar AURIX_VOSK_MODEL_PATH.
- pyttsx3: saída de fala local.

## Próximas etapas técnicas

1. Validar tempo de resposta, consumo de CPU e falsos positivos em máquinas Windows reais.
2. Adicionar tela de configurações de microfone, provedor de fala e estado de privacidade.
3. Substituir a transcrição online opcional pela experiência local padrão quando um modelo pt-BR compatível estiver instalado.
4. Implementar testes de integração e um empacotamento reproduzível para Windows.
5. Avaliar um modelo de wake word personalizado para a frase “Jarvis” em português.
