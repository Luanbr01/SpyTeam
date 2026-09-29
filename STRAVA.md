# Strava no SpyTeam

Esta versão adiciona a conexão OAuth à área do aluno. Cada aluno autoriza sua própria conta. Na opção Strava do menu do aluno (/aluno/strava), ele pode conectar, consultar suas 30 atividades mais recentes e desconectar. O perfil mantém um atalho para essa tela. Não muda os treinos planejados, não conclui treinos automaticamente e não mostra dados do Strava ao professor.

A tela consulta as atividades ao abrir e também pelo botão Atualizar atividades, respeitando o intervalo mínimo de 30 segundos. Se houve uma consulta há pouco, aguarda o intervalo automaticamente. A lista traz nome, modalidade, data, distância, pace e tempo em movimento. O botão Ver detalhes abre tempo total, ganho de elevação, velocidade e mapa do percurso quando disponível, sem sair do SpyTeam. Não importa todo o histórico. Não guarda atividades no banco nem no armazenamento do navegador; consulta diretamente a API. Uma página já aberta mostra a última consulta até a próxima atualização.

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
2. Abra Strava no menu do aluno > Conectar com Strava.
3. Autorize usando sua conta Strava de desenvolvedor enquanto sua aplicação estiver limitada ao próprio atleta. Seu perfil de professor não recebe acesso aos dados dos alunos.
4. Mantenha a permissão de leitura de atividades marcada. Esta versão não solicita atividades “Somente você” nem permissão de escrita.
5. Ao retornar à página Strava, aguarde o carregamento das atividades. O botão Atualizar atividades permite consultar novamente depois do intervalo. A API pode retornar menos de 30 itens ou nenhum, conforme as permissões e atividades existentes.
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

Testes de migração: banco vazio, reaplicação e evolução de schema existente. A integração anterior já foi confirmada pelo usuário. Nesta atualização, não foram acessadas contas reais: as verificações locais usam dados simulados. A nova tela foi verificada em Chromium nos tamanhos 320, 390, 768 e 1440 px, incluindo filtros, detalhes, mapa, estados vazio/erro/desconectado e falha no mapa de fundo. Concorrência no PostgreSQL não foi simulada.

Para repetir testes LOCALMENTE, instale as dependências do projeto e httpx; na raiz do projeto execute:

python -m unittest discover -s tests -p test_strava.py -v

## Documentação oficial

- https://developers.strava.com/docs/authentication/
- https://developers.strava.com/docs/reference/
- https://developers.strava.com/docs/webhooks/
- https://www.strava.com/legal/api


## Atualização da tela de atividades — 29/09/2026

Esta atualização pressupõe a integração Strava já instalada e configurada. Não exige variáveis novas, cadastro de webhook novamente, nova permissão OAuth ou nova migração. Copie todos os arquivos do pacote por cima da versão integrada e publique normalmente.

- Menu do aluno: opção Strava e cinco destinos ajustados ao celular. Menu do professor não é modificado.
- Página /aluno/strava: cards, filtro por modalidade, consulta ao abrir, atualização e desconexão.
- Detalhes: distância, pace, tempo em movimento, tempo total com pausas, ganho de elevação e velocidade quando disponíveis.
- Corrida/caminhada: pace em min/km. Natação: min/100 m e distância em metros. Ciclismo: velocidade em km/h. Musculação sem distância: pace não aplicável.
- Pace = tempo em movimento / distância. Não utiliza ritmo ajustado por inclinação nem estima valores ausentes. O horário local registrado na atividade é preservado.
- Mapas: Leaflet 1.9.4 incluído localmente, com licença BSD-2-Clause. Os tiles são consultados diretamente do OpenStreetMap, com atribuição visível e somente quando os detalhes são abertos. Não há pré-download de mapas ou cache offline customizado. A infraestrutura de tiles públicos não oferece SLA; para uso em grande escala, avalie um provedor próprio de tiles.
- O percurso disponibilizado pela API é desenhado localmente no navegador. Sem GPS, percurso ocultado ou polilinha inválida: aparece uma mensagem, sem inventar traçado. A polilinha resumida pode ser menos detalhada que a visualização original do Strava.
- Em caso de falha da internet/tiles, a tela explica a indisponibilidade do fundo; o traçado já recebido continua visível.
- Não armazena atividades, GPS ou tokens em localStorage/sessionStorage. Mantém os dados somente em memória durante a exibição. O professor continua sem acesso aos dados importados.

Verificações desta atualização: 10 testes Python passaram e 14 verificações JavaScript de cálculos, unidades, datas e polilinhas passaram. Testes em navegador usaram dados fictícios e tiles indisponíveis de propósito para verificar o fallback.

Para repetir os testes de apresentação com Node.js:

node tests/test_strava_view.cjs

Referências dos mapas:
- https://leafletjs.com/examples/quick-start/
- https://operations.osmfoundation.org/policies/tiles/
