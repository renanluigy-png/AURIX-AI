# Arquitetura do AURIX AI

## Objetivo

Manter o assistente ativo em segundo plano no Windows. O HUD só aparece quando o usuário o chama por voz, pelo ícone da bandeja ou pelo atalho global Ctrl+Alt+Espaço.

## Componentes

- aurix.app: ciclo de vida da aplicação, bandeja do sistema, hotkey e execução assíncrona das solicitações.
- aurix.hud: janela frameless, sempre no topo, com núcleo animado e campo de comando.
- aurix.voice: captura PCM a 16 kHz sob demanda, detecção local da palavra “Hey Jarvis”, detecção simples de silêncio e transcrição Vosk pt-BR.
- aurix.speech: síntese neural local Piper Plus com voz pt-BR em cache e reprodução WAV; pyttsx3 é o fallback local.
- aurix.commands: parser determinístico e allowlist de ações locais.
- aurix.brain: provedor conversacional opcional OpenAI Responses API ou Ollama local.
- aurix.config: preferências não secretas no perfil do usuário e integração de inicialização do Windows.

## Ciclo da voz

1. Um fluxo de áudio de 16 kHz é processado localmente por openWakeWord.
2. Após detectar “Hey Jarvis”, o HUD aparece e o assistente coleta um trecho curto, encerrando após silêncio ou limite máximo.
3. Por padrão, Vosk transcreve o trecho localmente em pt-BR. O modelo de aproximadamente 31 MB é baixado uma vez para a pasta de dados do usuário. Google Speech Recognition continua disponível como opção explícita.
4. A transcrição passa primeiro pelo parser de comandos conhecidos. Somente se não corresponder a um comando permitido é enviada ao provedor conversacional local Ollama (Qwen 2.5 3B por padrão).
5. Em pedidos por voz, Piper Plus sintetiza a resposta com a voz neural Faber pt-BR. O arquivo ONNX é fixado a uma revisão upstream e validado por SHA-256 antes de ser carregado. A reprodução é local; pyttsx3 é o fallback se a voz neural falhar.

O modelo openWakeWord pré-treinado é em inglês e reconhece “Hey Jarvis”, não somente “Jarvis”. O modelo é baixado na primeira execução; o resultado varia com o ambiente acústico.

## Fronteira de segurança

A IA conversacional não possui uma ferramenta de shell. As ações locais são escolhidas pelo parser a partir de nomes de comandos fixos. Não existe execução de texto arbitrário com shell=True. Operações destrutivas, envio de mensagens, automação de cliques e acesso irrestrito aos arquivos foram deixados fora deste MVP.

A chave da OpenAI é lida da variável de ambiente OPENAI_API_KEY/arquivo .env local e nunca é persistida nas preferências. O histórico conversacional é limitado e permanece apenas em memória.

## Dependências de voz

- openwakeword + sounddevice: detector de ativação e stream do microfone.
- Vosk: reconhecimento de fala local pt-BR (modelo baixado sob demanda).
- Google Speech Recognition: alternativa online opcional, habilitada somente quando selecionada.
- piper-plus: síntese neural local; o modelo Faber Medium pt-BR é baixado sob demanda e validado por SHA-256.
- pyttsx3: fallback local para voz instalada no Windows.

## Próximas etapas técnicas

1. Medir tempo de resposta, consumo de CPU/RAM e falsos positivos em máquinas Windows reais.
2. Adicionar seleção de microfone e ajuste fino da sensibilidade de ativação.
3. Avaliar um modelo de wake word pt-BR personalizado para aceitar “Jarvis” sem “Hey”.
4. Executar testes de integração de áudio e validar o instalador em hardware Windows real.
