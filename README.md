# AURIX AI

Assistente pessoal de desktop para Windows, inspirado em interfaces sci-fi, com voz, HUD flutuante e ferramentas locais escolhidas por um modelo de IA.

## Quero apenas instalar o aplicativo

O AURIX é empacotado para Windows com seu runtime Python e bibliotecas. O computador não precisa ter Git ou Python instalados.

1. Abra a aba **Actions** deste repositório.
2. Selecione o workflow **Windows app installer** e abra a execução mais recente concluída com sucesso.
3. Na seção **Artifacts**, baixe **AURIX-AI-Installer**.
4. Extraia o ZIP e execute **AURIX-AI-Setup.exe**.
5. Abra o AURIX pelo atalho criado. Na primeira execução, configure a IA e as opções de voz.

O instalador é construído pelo GitHub Actions; o arquivo de instalação só fica disponível depois de o workflow Windows terminar com sucesso.

[Ver os builds do Windows](https://github.com/renanluigy-png/AURIX-AI/actions/workflows/windows-installer.yml)

## O que é o AURIX

O AURIX não é apenas um conjunto de respostas predefinidas. Quando um provedor de IA está configurado, o modelo interpreta o pedido em linguagem natural e pode selecionar ferramentas que o próprio aplicativo executa. O resultado dessas ações volta ao modelo para produzir uma resposta contextual.

Ferramentas incluídas no MVP:

- abrir aplicativos permitidos, como Spotify, WhatsApp, Discord, navegador, VS Code, Calculadora e Explorador;
- pesquisar na web ou abrir um site HTTP/HTTPS solicitado;
- consultar data e hora locais;
- abrir Desktop, Documentos ou Downloads;
- criar novas notas de texto em Documentos/AURIX Notes.

As ferramentas validam os argumentos e não dão à IA um terminal arbitrário. Enviar mensagens, apagar arquivos, controlar qualquer janela ou executar comandos de shell não estão habilitados neste MVP.

## Primeira configuração

A janela inicial permite escolher como a inteligência será fornecida.

### OpenAI API — online

Cole sua chave da API no assistente de configuração. A chave é salva no armazenamento de credenciais do Windows, não no repositório nem no arquivo de preferências. O uso da API pode gerar custos conforme o modelo e sua conta.

[Gerenciar chaves da OpenAI API](https://platform.openai.com/api-keys)

### Ollama — local

Instale o [Ollama para Windows](https://ollama.com/download/windows) e mantenha-o em execução. O AURIX verifica o modelo configurado e, se ele ainda não existir no Ollama, solicita o download automaticamente na primeira conversa. O download pode ter vários GB e leva tempo; a velocidade depende da internet, memória e hardware do PC. O aplicativo não instala o runtime do Ollama sem seu consentimento.

### Voz e privacidade

- A detecção da frase de ativação é feita localmente. O modelo pré-treinado incluído reconhece **“Hey Jarvis”**, e não somente “Jarvis”.
- Para reconhecimento de fala em português sem enviar seu pedido a um serviço externo, escolha **Local**. Na primeira solicitação por voz, o AURIX baixa o modelo Vosk de português (aproximadamente 31 MB) para a pasta de dados do usuário.
- A opção Google usa um serviço externo para transcrever o áudio capturado depois da ativação.
- A escuta de ativação pode ser pausada no menu da bandeja. As permissões de microfone são controladas pelo Windows; a configuração inicial fornece um atalho para as opções de privacidade.
- Fechar o HUD apenas o oculta. Para encerrar o processo, use **Sair do AURIX** no menu da bandeja.

## Controles

- **Ctrl + Alt + Espaço**: abrir o HUD.
- **Ícone na bandeja**: abrir o HUD, pausar/retomar a escuta, configurar IA/voz, definir inicialização automática ou sair.
- Ao chamar por voz, o AURIX mostra o HUD, transcreve o pedido, usa ferramentas quando necessário e fala a resposta.

## Desenvolvimento a partir do código-fonte

Somente para quem deseja modificar o código. O usuário do instalador não precisa realizar estes passos.

~~~powershell
git clone https://github.com/renanluigy-png/AURIX-AI.git
cd AURIX-AI
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python -m aurix
~~~

Testes locais:

~~~powershell
python -m compileall -q aurix tests
python -m unittest discover -s tests -v
~~~

## Estrutura

- aurix/app.py: ciclo de vida, bandeja, atalho e fila de solicitações.
- aurix/onboarding.py: primeira configuração, consentimento de voz e provedor da IA.
- aurix/hud.py: interface futurista flutuante.
- aurix/voice.py: detecção de ativação e captura/transcrição de áudio.
- aurix/brain.py: conversa e loop de chamadas de ferramenta para OpenAI/Ollama.
- aurix/agent_tools.py: catálogo de ferramentas e validação das ações.
- aurix/commands.py: abertura de aplicativos da lista permitida.
- aurix/config.py: preferências e configuração de inicialização.

## Estado do MVP

Os testes automáticos verificam compilação sintática e a validação de ferramentas. Áudio real, permissões, instalação do Ollama e abertura dos programas precisam ser verificados em um Windows de destino. O modelo de ativação pré-treinado do openWakeWord tem licença CC BY-NC-SA 4.0; antes de redistribuir comercialmente, verifique a licença do modelo ou substitua-o por um modelo com licença adequada. O reconhecimento por voz depende do microfone e o uso da OpenAI API depende de uma chave válida. A automação foi mantida deliberadamente limitada por segurança.

## Licença

MIT. Veja o arquivo LICENSE.
