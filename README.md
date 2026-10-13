# AURIX AI

> Assistente pessoal para Windows com ativação por voz, interface HUD futurista e automações locais controladas.

O **AURIX AI** é um projeto open source em Python que funciona em segundo plano e pode ser chamado por voz ou por atalho global. A interface holográfica aparece sob demanda, sem exigir que uma janela convencional fique aberta.

## Visão do produto

- **Execução em segundo plano:** ícone na bandeja do Windows, sem janela aberta por padrão.
- **Ativação por voz:** palavra de ativação em inglês **“Hey Jarvis”** (modelo pré-treinado openWakeWord) e atalho `Ctrl + Alt + Espaço`.
- **Interface HUD:** núcleo animado, status e resposta em uma janela flutuante.
- **Comandos locais:** abrir aplicativos permitidos, pesquisar na web e consultar data/hora.
- **Conversa com IA:** OpenAI API ou Ollama local; comandos locais básicos não exigem chave de API.
- **Segurança por allowlist:** o modelo não recebe acesso arbitrário ao terminal, shell ou arquivos.
- **Configuração local:** preferências ficam no perfil do usuário; credenciais não são versionadas.

> **Estado do projeto:** primeira base de desenvolvimento. O suporte de voz depende dos dispositivos e permissões do Windows e precisa ser validado no computador de destino. O detector incluído reconhece “Hey Jarvis”; uma palavra de ativação apenas “Jarvis” exigiria um modelo customizado.

## Requisitos

- Windows 10/11 de 64 bits.
- Python 3.11 ou 3.12 recomendado.
- Microfone e saída de áudio para uso por voz.
- Conexão com internet para transcrição padrão por Google Speech Recognition ou para a OpenAI API. Ollama pode fornecer conversa local.
- Opcional: [Ollama](https://ollama.com/) com um modelo instalado, ou uma chave da [OpenAI API](https://platform.openai.com/api-keys).

## Instalação no Windows

Abra o PowerShell na pasta onde deseja clonar o projeto:

```powershell
git clone https://github.com/renanluigy-png/AURIX-AI.git
cd AURIX-AI

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente, execute apenas para a sessão atual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Na primeira inicialização, o AURIX tentará baixar os modelos públicos de detecção de palavra de ativação. É necessário ter internet nessa etapa. Depois execute:

```powershell
python -m aurix
```

O AURIX deverá aparecer na bandeja do sistema. Use **Hey Jarvis** para chamá-lo por voz ou `Ctrl + Alt + Espaço` para abrir o HUD manualmente. Fechar o HUD apenas o oculta; use **Sair do AURIX** na bandeja para encerrar o processo. Para ele iniciar junto com o Windows nas próximas sessões, clique com o botão direito no ícone da bandeja e habilite **Iniciar com o Windows**.

## Configurar a conversa com IA (opcional)

Copie o exemplo para criar um arquivo local de configuração:

```powershell
Copy-Item .env.example .env
```

Edite `.env` e escolha uma das opções.

### OpenAI API

```dotenv
AURIX_LLM_PROVIDER=openai
OPENAI_API_KEY=coloque_sua_chave_aqui
AURIX_OPENAI_MODEL=gpt-5-mini
```

A utilização da API pode gerar custos conforme a sua conta e o modelo escolhido. **Nunca publique o arquivo `.env` nem a chave de API.**

### Ollama local

Instale e inicie o Ollama, baixe um modelo compatível e configure:

```dotenv
AURIX_LLM_PROVIDER=ollama
AURIX_OLLAMA_MODEL=llama3.2
AURIX_OLLAMA_URL=http://localhost:11434
```

Com `AURIX_LLM_PROVIDER=auto`, o AURIX tenta OpenAI quando existe uma chave configurada e, caso contrário, usa Ollama. Sem um provedor disponível, os comandos locais continuam ativos e o assistente informa como habilitar conversa com IA.

### Transcrição de voz totalmente local (opcional)

A transcrição padrão usa o Google Speech Recognition após a palavra de ativação. Para processar a transcrição localmente, instale a dependência opcional:

```powershell
pip install -e ".[offline-speech]"
```

Baixe um modelo de português compatível no [catálogo de modelos do Vosk](https://alphacephei.com/vosk/models) e configure no arquivo `.env`:

```dotenv
AURIX_SPEECH_PROVIDER=vosk
AURIX_VOSK_MODEL_PATH=C:\caminho\para\o\modelo
```

A detecção de ativação continua local. O modelo Vosk precisa ser baixado separadamente e usa mais espaço em disco.

## Privacidade e permissões

- O detector de palavra de ativação processa o fluxo de áudio localmente.
- Na configuração padrão, **após a ativação**, o áudio da solicitação é enviado ao serviço Google Speech Recognition para transcrição. Não use essa opção se não quiser enviar áudio para um serviço externo; configure o reconhecimento local seguindo a documentação de arquitetura.
- A chave OpenAI deve ficar apenas no arquivo `.env` local ou em uma variável de ambiente.
- O AURIX não executa comandos de shell arbitrários gerados por IA. Ações locais passam por um conjunto explícito de comandos.
- A automação de mensagens, exclusão de arquivos e outras ações sensíveis não faz parte desta primeira base.
- A permissão de microfone pode ser revogada nas configurações de Privacidade do Windows.

## Comandos de exemplo

- “Abre o Spotify.”
- “Abre o WhatsApp.”
- “Abre o VS Code.”
- “Pesquisa por documentação do Python.”
- “Que horas são?”
- Perguntas gerais em português, quando um provedor de IA está configurado.

O nome de ativação pré-treinado é **“Hey Jarvis”**, que pode ser pronunciado com sotaque brasileiro. O reconhecimento do modelo pode variar conforme microfone, ruído e distância.

## Desenvolvimento e testes

```powershell
python -m unittest discover -s tests -v
python -m compileall aurix
```

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para arquitetura, decisões e próximos passos.

## Roadmap

- [x] Estrutura inicial do projeto e documentação.
- [x] Bandeja do sistema e HUD flutuante.
- [x] Atalho global e comandos locais restritos.
- [x] Integrações opcionais com OpenAI e Ollama.
- [x] Detector local de palavra de ativação e fluxo de voz.
- [ ] Executar testes de áudio em diferentes dispositivos Windows.
- [ ] Configuração gráfica da inicialização com Windows e preferências de voz.
- [ ] Transcrição local integrada de ponta a ponta e pacote instalável.
- [ ] Testes e2e automatizados e instalador assinado.

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
