# Strava no SpyTeam

Esta versão adiciona a conexão OAuth à área do aluno. Cada aluno autoriza sua própria conta. No Meu perfil, o aluno pode conectar, atualizar suas 30 atividades mais recentes e desconectar. Não muda os treinos planejados, não conclui treinos automaticamente e não mostra dados do Strava ao professor.

A consulta é manual, pelo botão Atualizar atividades, com intervalo mínimo de 30 segundos. A lista traz nome, modalidade, data, distância, duração e link para o Strava. Não importa todo o histórico. Não guarda atividades no banco nem no armazenamento do navegador; consulta diretamente a API. Uma página já aberta mostra a última consulta até a próxima atualização.

## Aplicar os arquivos

1. Copie o conteúdo da pasta SpyTeam do pacote para a raiz do projeto, mesclando as pastas e substituindo os arquivos indicados. O pacote contém somente arquivos novos/modificados, não o projeto inteiro.
2. Faça commit e push. O Dockerfile existente já instala requirements.txt e executa scripts/aplicar_migracoes.py antes de iniciar.
3. Confira no deploy a revisão Alembic 20260929_03. A migração cria strava_conexoes e não apaga alunos ou treinos. Faça o backup habitual antes de atualizar produção.

## Variáveis no serviço da aplicação Railway

Mantenha as três variáveis já configuradas:

- STRAVA_CLIENT_ID: ID da aplicação.
- STRAVA_CLIENT_SECRET: segredo da aplicação, somente no Railway.
- STRAVA_REDIRECT_URI: https://www.spyteam.com.br/api/strava/callback

SPYTEAM_SECRET, já usado pelo login, também deve estar configurado e ser mantido estável. A chave de criptografia dos tokens é derivada dele com separação de finalidade. Se trocar esse segredo, os alunos precisarão entrar e conectar o Strava novamente. Não publique segredos, tokens ou dumps do banco no GitHub.

No Strava, Authorization Callback Domain deve ser www.spyteam.com.br. Abra o SpyTeam pelo mesmo domínio www antes de conectar, para manter a sessão no retorno.

## Webhook de revogação (concluir antes de liberar aos alunos)

O Strava exige tratar a desautorização da aplicação. Este pacote recebe o aviso e confirma a revogação na API antes de remover as credenciais. Eventos de atividade são reconhecidos, mas a atualização da lista é manual, sem cópia persistente a atualizar.

1. Gere um segredo aleatório no terminal LOCAL com Python:

   python -c "import secrets; print(secrets.token_urlsafe(32))"

2. Copie o resultado para a variável STRAVA_WEBHOOK_VERIFY_TOKEN no serviço da aplicação Railway. Não precisa enviar esse valor a ninguém.
3. Aguarde o deploy dos arquivos e dessa variável.
4. No terminal do container/serviço da aplicação Railway (o mesmo usado nas migrações anteriores), execute:

   python scripts/configurar_strava_webhook.py

5. O script exibe STRAVA_WEBHOOK_SUBSCRIPTION_ID com um número. Crie essa variável no mesmo serviço usando o número exibido e aguarde a atualização.
6. O script é reutilizável: reaproveita uma assinatura existente para o mesmo endereço e não exclui outra assinatura automaticamente.

Endereço do webhook: https://www.spyteam.com.br/api/strava/webhook
Apenas esse endpoint público é dispensado do CSRF; as ações do aluno continuam protegidas. O POST valida o ID da assinatura e confirma revogações na API, porque o ID sozinho não é um segredo de autenticação. A verificação do webhook tem seu próprio token.

## Testar a integração real

1. Entre no SpyTeam com uma conta de ALUNO destinada ao seu teste.
2. Abra Meu perfil > Suas atividades do Strava > Conectar com Strava.
3. Autorize usando sua conta Strava de desenvolvedor enquanto sua aplicação estiver limitada ao próprio atleta. Seu perfil de professor não recebe acesso aos dados dos alunos.
4. Mantenha a permissão de leitura de atividades marcada. Esta versão não solicita atividades “Somente você” nem permissão de escrita.
5. Ao retornar ao perfil, toque em Atualizar atividades. A API pode retornar menos de 30 itens ou nenhum, conforme as permissões e atividades existentes.
6. Teste a desconexão pelo SpyTeam e também a revogação pelo Strava > Configurações > Meus aplicativos.
7. Antes de liberar outros alunos, confira a capacidade de atletas no painel do Strava e solicite a ampliação necessária.

A autorização pertence a cada conta individual. Não copie o token pessoal do painel de desenvolvedor para todos os alunos. A aplicação não pede a senha do Strava.

## Arquitetura e limites

- app/strava.py: router OAuth, consulta, refresh, desconexão e webhook.
- app/models.py: tabela privada, tokens criptografados com Fernet; atleta único por conta.
- app/main.py: registra o router, isenção pontual do webhook e limpeza dos tokens ao excluir aluno.
- Alembic: migração aditiva e ajuste da validação pré-baseline para admitir a tabela nova.
- Perfil, CSS e JS: interface responsiva; textos de atividades inseridos com textContent.
- Rotas autenticadas usam exclusivamente o usuário da sessão, sem aceitar ID de aluno no cliente.
- State OAuth vinculado à sessão, com prazo de 10 minutos e consumo único.
- PostgreSQL utiliza bloqueio de linha para serializar a renovação de tokens.
- Callback exige sessão ativa no mesmo navegador/domínio; se ela expirar, entre novamente e reinicie a conexão.
- Respostas privadas usam Cache-Control: no-store. O service worker atual já ignora chamadas /api/.
- Sem sincronização automática em segundo plano nem conclusão automática dos treinos.
- O webhook confirma revogações em tarefa de background do processo. Se o serviço parar nesse intervalo, a próxima consulta ainda revalida os tokens; a implantação não inclui fila durável de eventos.

## Verificações executadas

Testes automatizados com banco SQLite temporário e API Strava simulada: sessão/CSRF, bloqueio de professor, state inválido/expirado/repetido, permissão insuficiente, tokens criptografados, separação entre alunos, vínculo duplicado, limite de atualização, persistência de refresh rotacionado após falha, desconexão, verificação/revogação de webhook e renderização do perfil.

Testes de migração: banco vazio, reaplicação e evolução de schema existente. A conexão real com o Strava, o Railway e a concorrência no PostgreSQL precisam ser validados no ambiente de implantação; não foram acessadas contas reais durante a preparação.

Para repetir testes LOCALMENTE, instale as dependências do projeto e httpx; na raiz do projeto execute:

python -m unittest discover -s tests -p test_strava.py -v

## Documentação oficial

- https://developers.strava.com/docs/authentication/
- https://developers.strava.com/docs/reference/
- https://developers.strava.com/docs/webhooks/
- https://www.strava.com/legal/api
