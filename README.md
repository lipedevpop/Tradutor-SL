# Tradutor SL

Tradutor para Second Life com instalador para Windows, ícone oficial,
atualização pelo aplicativo e recuperação da versão anterior.

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
