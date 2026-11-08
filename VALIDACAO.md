# Validação desta edição

- 26 testes do atualizador aprovados no Windows/Python 3.12, incluindo a
  preservação do repositório oficial ao gerar as próximas correções e a
  ativação da versão instalada pelo EXE com a transação de recuperação.
- 73 testes existentes do tradutor aprovados, incluindo filtro de inglês,
  preservação das mensagens, API simulada, chave protegida e reconhecimento de viewers.
- A troca de versão e a restauração foram testadas com processos Python reais:
  inicialização bem-sucedida, término com erro, tempo limite e interrupção da troca.
- A janela real do tradutor e a janela Atualizações foram abertas e conferidas
  visualmente. As configurações e a API foram substituídas por dados locais de teste.
- O repositório público lipedevpop/Tradutor-SL foi conferido e configurado no
  pacote 1.0.2. Ainda falta publicar a primeira release e validar o download
  entre duas releases públicas reais antes de distribuir o app para outras pessoas.
- A preparação via pip para mudanças futuras de dependências foi verificada com
  subprocessos simulados. O pip real não foi executado nem foram instaladas
  bibliotecas no sistema.

## Instalador 1.1.0

- O EXE compilado foi executado de verdade em uma pasta isolada do workspace,
  incluindo nomes com espaços e acentos e caminhos extensos do Windows.
- A instalação cria atalhos .lnk reais para o executável, na área de trabalho
  de teste e no menu Iniciar de teste. O ícone oficial é embutido no EXE.
- Foram testadas instalação, reinstalação e recusa de pasta contendo outros arquivos.
- O Python e as bibliotecas carregam da própria instalação: CPython 3.12.10,
  langid 1.1.6, NumPy 2.3.5 e Pillow 13.0.0. Não usa o Python do usuário.
- Os 73 testes existentes passaram com o runtime que vai no instalador.
- Uma atualização real 1.1.0 → 1.1.1 foi preparada e ativada com a janela do
  aplicativo e o filtro reais; o download foi simulado por um pacote local.
- A desinstalação real removeu o app e os atalhos e manteve arquivos pessoais
  separados, incluindo um arquivo de chave fictício. Nenhuma chave real foi usada.
- O registro em Aplicativos do Windows está implementado no ramo de instalação
  normal. Os testes usam registro de teste e não modificaram o registro do usuário.
- A tela WinForms do instalador foi renderizada e conferida visualmente.
- O instalador é para Windows 10/11 de 64 bits e não está assinado digitalmente.
  Não foi testado em uma máquina virtual limpa nem entre duas releases reais do GitHub.

## Publicação automática

- O publicador tem 8 testes locais aprovados: incremento de versão, exigência
  de notas, preservação de releases existentes, arquivos ausentes, conferência
  dos hashes e publicação somente após anexar os arquivos ao rascunho.
- O workflow e as ações oficiais fixadas por SHA foram preparados localmente.
- O envio dos fontes e a primeira execução no GitHub ainda estão pendentes:
  a conexão atual não tem escrita no repositório lipedevpop/Tradutor-SL.

O pacote de manutenção inclui os testes adicionais em tests/test_updates.py.
Para executar, dentro da pasta dos fontes:

```powershell
py -3.12 -m unittest discover -s tests -v
py -3.12 -m unittest discover -s app -v
```

Os testes do app precisam das dependências de app/requirements.txt instaladas
no Python usado para os testes. Os testes do atualizador usam a biblioteca padrão.

Para gerar um pacote distribuível, use tools/build_release.py conforme
PUBLICAR_ATUALIZACOES.md. Os fontes de manutenção não são uma instalação pronta.
