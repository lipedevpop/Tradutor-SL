# Publicar correções do Tradutor Hot SL

## Repositório oficial

https://github.com/lipedevpop/Tradutor-SL

A edição 1.0.2 já vem configurada para consultar esse repositório público.
Em instalações anteriores, é possível informar `lipedevpop/Tradutor-SL`
em Configurações → Atualizações → Salvar e verificar.
Os pacotes distribuídos ficam públicos. Não publique chaves, configurações
pessoais, logs de conversas nem a pasta de dados do usuário.

## Instalador para novos usuários — versão 1.1.0

Crie uma nova release `v1.1.0` em:
https://github.com/lipedevpop/Tradutor-SL/releases/new

Título: **Tradutor SL 1.1.0 — Instalador para Windows**.
Anexe estes dois arquivos:

1. **Tradutor_SL_Setup_1.1.0.exe** — opção recomendada para novos usuários.
2. **Tradutor_Hot_SL_v1_1_0_Atualizacoes.zip** — arquivo que o atualizador interno baixa.

Opcionalmente, anexe também `Tradutor_SL_v1_1_0_Instalacao.zip` para quem
prefere baixar o instalador e o guia juntos. Esse ZIP contém somente o EXE
e LEIA_AQUI.txt.

Publique como estável e mais recente. Preserve a release 1.0.2.
O atualizador procura um único ZIP com o prefixo `Tradutor_Hot_SL_`.
Não anexe o pacote de fontes de manutenção com esse mesmo prefixo à release.
O instalador EXE e o ZIP de instalação têm nomes diferentes e são ignorados
pelo atualizador. As configurações e a chave já salvas continuam compatíveis.

### Gerar o instalador novamente

Os fontes em `installer/` e `tools/build_windows_installer.py` geram o EXE
com o compilador C# do .NET Framework do Windows. Os componentes precisam
estar disponíveis no computador de manutenção: CPython 3.12 de 64 bits com
Tcl/Tk, langid 1.1.6, NumPy 2.3.5 e Pillow 13.0.0.

```powershell
py -3.12 tools/build_windows_installer.py --version 1.1.0 --build-dir work/build-1.1.0 --output dist --base-python "C:/caminho/Python312" --dependency-sites "C:/caminho/Lib/site-packages"
```

Use uma pasta de compilação nova. O script confere o funcionamento offline,
preserva licenças dos componentes e gera hashes SHA-256. O executável ainda
não é assinado digitalmente; o Windows poderá indicar editor desconhecido.

## Referência: publicação inicial da 1.0.2

No repositório, abra **Releases → Draft a new release**:
https://github.com/lipedevpop/Tradutor-SL/releases/new

Crie a tag `v1.0.2` apontando para a branch `main`, use o título
`Tradutor SL 1.0.2` e descreva as novidades. Anexe o arquivo
`Tradutor_Hot_SL_v1_0_2_Atualizacoes.zip` como um arquivo de release.
Publique como versão estável e mais recente, sem marcar pré-lançamento.
O GitHub calcula o SHA-256 do arquivo; o app exige esse digest ao baixar.
Os arquivos automáticos "Source code" não substituem o ZIP que deve ser anexado.

## Gerar e publicar cada correção

O pacote de manutenção inclui `app/`, o inicializador, os scripts e
`tools/build_release.py`. Faça a correção nos fontes de `app/` e execute
os testes apropriados antes de empacotar. Exemplo no PowerShell:

```powershell
py -3.12 tools/build_release.py --version 1.0.3 --output dist
```

O script mantém o repositório oficial configurado, define a versão no pacote e gera o manifesto dos arquivos e o ZIP
limpo com seu SHA-256. Ele não inclui ambientes Python, configurações locais
ou credenciais. Não compacte uma instalação em uso para publicar.

Crie a release `v1.0.3` no mesmo repositório, descreva as correções e anexe
exatamente um ZIP `Tradutor_Hot_SL_*.zip` gerado pelo script. Publique como
estável e mais recente. Instalações 1.0.2 passarão a oferecer a correção.
Não substitua uma release antiga: publique sempre um número maior.

## Limites e manutenção

- Usa releases públicas do GitHub, via HTTPS, sem senha/token embutido.
- O hash do ZIP é conferido contra a API autenticada por HTTPS do GitHub;
  o manifesto confere todos os arquivos do app. Não é uma assinatura digital
  independente: o controle da conta/repositório controla as atualizações.
- O ZIP tem limite de 64 MB e 256 MB após extração.
- As versões usam três números, como `1.0.1`. Pré-lançamentos são ignorados.
- A chave DeepL e os textos das IMs nunca entram nas requisições do atualizador.
- Mudanças em requirements.txt criam outro ambiente antes da troca de versão.
  A criação usa o Python-base instalado e o pip, com seus índices configurados.
- O inicializador da raiz usa protocolo 1 e permanece estável. Uma mudança
  incompatível nesse protocolo requer um novo instalador completo.
- A verificação de início cobre janela e filtro local, não toda a funcionalidade.
- Há uma instância por instalação; o bloqueio é liberado pelo Windows se ela cair.
- A restauração é transacional para o código e as bibliotecas. Futuras migrações
  de configurações devem manter compatibilidade para permitir voltar de versão.
- Teste no Windows uma instalação limpa e a atualização entre duas releases
  reais antes de distribuir para outras pessoas.

Documentação oficial: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
