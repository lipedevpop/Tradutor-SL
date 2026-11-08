# Manutenção do Tradutor SL

O usuário pediu que correções concluídas sejam enviadas ao repositório e
publicadas após os testes. Repositório: https://github.com/lipedevpop/Tradutor-SL.

- Preserve a chave DeepL e as configurações do usuário fora dos pacotes.
- Faça a correção e execute os testes pertinentes antes de preparar a release.
- Para alterações do app, aumente APP_VERSION com tools/prepare_release.py e
  registre as correções em release-notes/<versão>.md.
- Envie os fontes para main usando o acesso autorizado ao repositório. O
  workflow publicar.yml testa, gera o instalador e publica uma nova versão.
- Não modifique uma versão já publicada. Use um número maior para a correção.
- A release precisa incluir o EXE e um único ZIP Tradutor_Hot_SL_*_Atualizacoes.zip.
- Acompanhe o workflow até terminar e confira os arquivos da release antes de
  informar que a publicação foi concluída.
- Se faltar autenticação ou permissão de escrita, conclua o trabalho local,
  explique o bloqueio e peça a conexão da conta correta. Não solicite senhas
  ou tokens no chat e não afirme que um pacote local já foi publicado.
