# Distribuição Windows do AURIX AI

## Canal recomendado: Microsoft Store (MSIX)

O AURIX usa uma aplicação Win32/Python empacotada com PyInstaller. Para computadores com Smart App Control, o caminho de produção selecionado é publicar o pacote MSIX pela Microsoft Store. A Store assina novamente o pacote aprovado e gerencia a entrega de atualizações. Um MSIX de teste assinado com certificado próprio **não** é uma versão confiável para usuários e não deve ser instalado em computadores de terceiros.

Documentação oficial:
- [Assinatura para Smart App Control](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control)
- [Opções de assinatura para aplicativos Windows](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Guia de assinatura MSIX](https://learn.microsoft.com/en-us/windows/msix/package/sign-msix-package-guide)

## Preparar a identidade de publicação

1. Registre uma conta de desenvolvedor da Microsoft Store no [Partner Center](https://partner.microsoft.com/dashboard).
2. Reserve o nome **AURIX AI** e abra a página de identidade do produto.
3. Copie exatamente o **Package/Identity Name** e o **Publisher** exibidos pelo Partner Center.
4. No repositório GitHub, acesse **Settings → Secrets and variables → Actions → Variables** e crie:
   - `AURIX_MSIX_IDENTITY_NAME`: o Package/Identity Name reservado.
   - `AURIX_MSIX_PUBLISHER`: o Publisher completo, normalmente começando por `CN=`.
   - `AURIX_MSIX_PUBLISHER_DISPLAY_NAME`: o nome público do editor.
5. Execute o workflow **Windows MSIX Store Package** ou envie as alterações à branch `main`.
6. Baixe o artefato `AURIX-AI-MSIX-Store-Package` na execução do GitHub Actions e envie o `.msix` ao Partner Center para certificação.

Sem as duas primeiras variáveis de identidade, o workflow usa valores provisórios para validar a compilação. Esse pacote provisório não pode ser enviado como pacote final da Store. Depois da certificação, a Microsoft aplica a assinatura de distribuição e o usuário instala o AURIX pela página oficial da Store.

A inscrição e a aprovação da conta, reserva do nome, certificação e publicação precisam ser feitas pelo titular da conta Partner Center. O workflow não tenta publicar sem essa identidade.

## Segurança da assinatura

O workflow assina temporariamente o artefato com um certificado descartável apenas para validar a estrutura da assinatura e a integridade do MSIX durante a compilação. O certificado temporário não é confiável, não é enviado como instalador para usuários e é removido ao final do job. **Não distribua um MSIX assinado por certificado autoassinado.**

Para distribuição fora da Store, será necessário obter um certificado de assinatura de código emitido por uma autoridade confiável e assinar o instalador e os binários PE. Certificados autoassinados não resolvem o bloqueio do Smart App Control em computadores públicos.

## Comportamento da versão MSIX

- Configurações, logs e modelos baixados são armazenados em `LocalState` do pacote.
- O atualizador GitHub antigo e a inicialização via chave `Run` do Registro são desativados na versão MSIX. A Microsoft Store controla as atualizações; o recurso de inicialização é omitido até ser implementado usando o mecanismo apropriado para pacotes.
- O áudio, os modelos locais Vosk/Kokoro e Ollama continuam separados do pacote e são baixados apenas quando necessários.
