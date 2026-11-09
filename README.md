# Tradutor SL

Tradutor para Second Life com instalador para Windows, ícone oficial,
atualização pelo aplicativo e recuperação da versão anterior.

Compatível com Firestorm, Alchemy, Cool VL Viewer e **Aurora Viewer**.

## Aurora Viewer

Em **Preferences → Chat** do Aurora, mantenha o histórico de IMs ativado.
No tradutor, abra Configurações e use **Automático → Detectar** ou selecione
**Aurora Viewer**. Escolha a conta e o grid se houver várias pastas.
O tradutor reconhece o nome do avatar pelo catálogo local do Aurora.

A pasta padrão das conversas no Windows é
`%APPDATA%\Aurora\AuroraViewer\config\accounts\<UUID>\chat_logs\<grid>\`
(normalmente `agni` para Second Life). Pastas alteradas nas preferências do
Aurora também são detectadas. Para selecionar manualmente, escolha a pasta
do grid que contém os arquivos `.txt`.

A leitura começa nas novas mensagens; histórico antigo, chat local, grupos
e conferências são ignorados. A tradução e a cópia de respostas usam o mesmo
fluxo dos outros viewers. Nenhuma mensagem é enviada automaticamente.

Layout e formato conferidos no [código oficial do Aurora](https://github.com/Aurora-Viewer/Aurora-Viewer/tree/main/crates/aurora-viewer/src/world/chat_log)
e na instalação local 0.9.1. A validação usa conversas sintéticas; uma IM real
ao vivo depende do viewer conectado.

## Instalar

Baixe o arquivo **Tradutor_SL_Setup_<versão>.exe** em
[Releases](https://github.com/lipedevpop/Tradutor-SL/releases/latest).
Abra, clique em Instalar e use o atalho da área de trabalho ou do menu Iniciar.
O instalador inclui os componentes necessários. A chave de API DeepL é
informada pelo próprio usuário e não acompanha o programa.

## Publicação automática

O workflow `.github/workflows/publicar.yml` executa os testes no Windows,
compila o instalador e publica a versão ainda não lançada ao receber os fontes
em `main`. As correções precisam de um número novo em `APP_VERSION` e de notas
em `release-notes/<versão>.md`.

O fluxo usa o token temporário do próprio GitHub Actions. Não exige chave
DeepL nem token pessoal no código. A publicação só sai de rascunho depois que
todos os arquivos forem anexados e seus hashes forem conferidos.

```powershell
python tools/prepare_release.py --notes-file caminho/correcoes.md
python -m unittest discover -s tests -v
python -m unittest discover -s app -v
```

Depois, envie a alteração para `main` e acompanhe a execução em Actions.
O instalador não tem assinatura digital nesta edição.
