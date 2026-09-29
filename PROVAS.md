# Provas no calendário

## Como aplicar

Esta atualização usa a última versão do projeto com a tela Strava já aplicada.

1. Extraia o ZIP e copie o conteúdo da pasta SpyTeam para a raiz do projeto, mesclando as pastas e substituindo os arquivos.
2. Faça commit e push e aguarde o deploy do serviço da aplicação no Railway.
3. O Dockerfile existente executa a migração antes de iniciar. Procure a revisão 20260929_04 nos logs de migração. Ela cria a tabela provas; não remove alunos, treinos ou conexões Strava.
4. Não são necessárias variáveis de ambiente nem dependências novas.

## Professor

- Abra Calendário e toque em + Adicionar prova.
- Informe nome, data e modalidade.
- Ao escolher Corrida, aparecem 5, 7, 10, 15, 21 e 42 km. É possível escolher várias distâncias na mesma prova.
- Natação oferece atalhos de 50, 100, 200, 400, 800 e 1.500 m. São apenas sugestões; é possível adicionar outra distância.
- Musculação oferece a opção Livre. Use Outra distância ou categoria para informar as categorias oferecidas pelo organizador.
- O link de inscrição é opcional e precisa começar com http:// ou https://. Ele abre o site do organizador em outra aba.
- Ao salvar, o calendário vai para o mês da prova.
- Toque na data para ver provas e treinos daquele dia. No detalhe é possível editar ou excluir a prova. Também é possível adicionar uma prova diretamente no dia selecionado.

## Aluno

- No Meu painel, na seção Agenda da semana, toque em Provas.
- A página /aluno/provas mostra as próximas provas em ordem de data; abaixo fica o calendário mensal.
- O filtro por modalidade vale para a lista e para o calendário.
- A lista considera eventos a partir de hoje, no fuso America/Sao_Paulo. Para ver provas passadas, navegue para o mês correspondente no calendário.
- Todas as provas cadastradas estão disponíveis aos alunos, independentemente das modalidades do perfil. A participação é opcional.
- O botão Inscrição abre o endereço fornecido pelo professor. A inscrição, pagamento e confirmação ocorrem no site do organizador; o SpyTeam não inscreve o aluno automaticamente.
- Sem link, a tela informa que ele ainda não foi fornecido.

## Calendário no celular

O calendário mantém sete colunas, com números e contadores de provas/treinos. Toque no dia para abrir os nomes e detalhes. No computador, os nomes dos eventos também aparecem nas células. Os controles de mês ficam alinhados em uma única linha no celular.

## Dados e acesso

- Nova tabela provas: nome, data, modalidade, opções, link e datas de criação/alteração.
- Somente professores podem criar, editar e excluir; os alunos têm consulta.
- As ações administrativas são registradas na auditoria existente e usam o CSRF já implementado.
- Validação de data, modalidade, quantidade/tamanho de opções e esquema do link no servidor.
- Títulos e opções são inseridos na tela como texto, sem executar HTML.
- API GET /api/provas lista as próximas provas. GET /api/provas?ano=2026&mes=10 lista o mês. Cada consulta limita a 300 eventos e informa o total.
- Migração 20260929_04 é posterior à migração Strava 20260929_03.

## Verificações

Testes de cadastro, edição, exclusão, consulta do aluno, bloqueio de escrita pelo aluno, sessão/CSRF, datas inválidas, links inseguros, opções duplicadas, provas passadas e renderização de páginas.

Migração verificada em SQLite temporário: banco vazio, banco versionado e banco pré-Alembic, incluindo reaplicação e preservação de um aluno de exemplo. Banco PostgreSQL de produção não foi acessado.

Para executar localmente os testes (dependências do projeto e httpx instalados):

python -m unittest discover -s tests -p test_provas.py -v

Os testes reutilizam as configurações temporárias de tests/test_strava.py e não devem ser executados no serviço de produção.

Validação visual e de interação: Chromium com dados simulados nas larguras 320, 390 e 1440 px, incluindo seleção múltipla, troca de modalidade, cadastro, edição, exclusão, filtro e calendário com treinos e provas. Nenhuma rolagem horizontal detectada. Os 15 testes Python de provas e Strava passaram.
