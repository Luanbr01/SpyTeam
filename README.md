# SPY TEAM

Sistema web para **gestão de alunos, criação e distribuição de treinos
esportivos**, desenvolvido com **FastAPI, SQLAlchemy, SQLite, Jinja2,
HTML, CSS e JavaScript**.

O SPY TEAM possui dois tipos de acesso:

-   **Professor:** administra alunos, cria treinos base, agenda treinos
    individuais, acompanha treinos e feedbacks e realiza planejamento
    semanal por modalidade.
-   **Aluno:** acessa seu painel pessoal, visualiza os treinos
    programados, acompanha a semana, conclui treinos e envia feedback ao
    professor.

------------------------------------------------------------------------

## 1. Objetivo do projeto

O objetivo do SPY TEAM é centralizar o planejamento de uma assessoria
esportiva.

O professor consegue cadastrar seus alunos e organizar os treinos que
serão executados. O sistema também possui um recurso de **planejamento
semanal**, no qual os treinos de segunda a sexta são distribuídos
automaticamente para os alunos cuja modalidade corresponde à modalidade
do treino.

Exemplo:

-   treino base de **Corrida** → enviado aos alunos de Corrida;
-   treino base de **Natação** → enviado aos alunos de Natação.

O aluno recebe somente os treinos vinculados à própria conta.

------------------------------------------------------------------------

## 2. Principais funcionalidades

### Professor

O professor possui acesso administrativo ao sistema e pode:

-   fazer login;
-   visualizar o painel principal;
-   cadastrar alunos;
-   definir nome, nível e modalidade do aluno;
-   criar usuário e senha para cada aluno;
-   listar alunos cadastrados;
-   excluir alunos;
-   criar treinos base;
-   agendar um treino para um aluno específico;
-   listar os treinos agendados;
-   consultar os treinos de determinado aluno;
-   enviar um treino em massa;
-   montar o planejamento semanal de segunda a sexta;
-   distribuir automaticamente os treinos conforme a modalidade;
-   consultar conclusão e feedback dos treinos.

### Aluno

O aluno pode:

-   entrar com seu próprio usuário e senha;
-   acessar somente o painel de aluno;
-   visualizar seus dados;
-   visualizar seus próprios treinos;
-   acompanhar os treinos da semana;
-   verificar treinos pendentes e concluídos;
-   marcar um treino como concluído;
-   dar uma nota de 1 a 5;
-   informar a dificuldade;
-   escrever um comentário;
-   consultar o histórico de treinos concluídos;
-   sair da conta.

------------------------------------------------------------------------

## 3. Tecnologias utilizadas

  Tecnologia   Utilização
  ------------ ---------------------------------------------------
  Python       Linguagem principal do backend
  FastAPI      Framework web e criação das rotas/API
  Uvicorn      Servidor ASGI utilizado para executar a aplicação
  SQLAlchemy   ORM e comunicação entre Python e banco de dados
  SQLite       Banco de dados local
  Pydantic     Validação dos dados recebidos pela API
  Jinja2       Renderização dos templates HTML
  HTML         Estrutura das páginas
  CSS          Interface e identidade visual
  JavaScript   Interações do frontend e comunicação com a API

As dependências declaradas atualmente em `requirements.txt` são:

``` text
fastapi
uvicorn
sqlalchemy
pydantic
jinja2
```

------------------------------------------------------------------------

## 4. Estrutura do projeto

``` text
SpyTeam/
│
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── img/
│   │   ├── logo-spy-team.png
│   │   └── logo-spy-team.svg
│   └── js/
│       └── aluno.js
│
├── templates/
│   ├── alunos/
│   │   ├── alunos.html
│   │   └── novo_aluno.html
│   ├── treinos/
│   │   ├── novo_treino.html
│   │   └── novo_treino_base.html
│   ├── aluno.html
│   ├── home.html
│   ├── login.html
│   └── planejamento_semanal.html
│
├── assessoria.db
├── banco_de_dados.db
├── requirements.txt
└── .gitignore
```

> A aplicação configurada em `app/database.py` utiliza
> **`assessoria.db`**. O arquivo `banco_de_dados.db` não é o banco
> apontado pela configuração atual.

------------------------------------------------------------------------

# 5. Backend

## `app/main.py`

É o arquivo principal da aplicação.

Suas responsabilidades incluem:

-   criar a aplicação FastAPI;
-   montar a pasta `/static`;
-   configurar o Jinja2;
-   criar as tabelas do SQLAlchemy;
-   abrir e fechar sessões com o banco;
-   identificar o usuário autenticado;
-   controlar permissões de professor e aluno;
-   criar o professor inicial;
-   renderizar as páginas HTML;
-   implementar as rotas da API;
-   cadastrar e excluir alunos;
-   criar e distribuir treinos;
-   processar planejamento semanal;
-   receber feedback dos alunos.

A aplicação é criada com:

``` python
app = FastAPI(title="SpyTeam")
```

Os arquivos estáticos são disponibilizados em:

``` python
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
```

E os templates são carregados de:

``` python
templates = Jinja2Templates(
    directory="templates"
)
```

------------------------------------------------------------------------

## `app/database.py`

Responsável pela conexão com o SQLite.

O código calcula o caminho absoluto da pasta do projeto e aponta para:

``` text
assessoria.db
```

A URL utilizada pelo SQLAlchemy possui o formato:

``` text
sqlite:///CAMINHO_DO_PROJETO/assessoria.db
```

Também são definidos:

-   `engine`: conexão principal do SQLAlchemy;
-   `SessionLocal`: fábrica de sessões;
-   `Base`: classe base dos modelos ORM.

O SQLite é configurado com:

``` python
connect_args={
    "check_same_thread": False
}
```

Isso permite o uso da conexão no contexto da aplicação FastAPI.

------------------------------------------------------------------------

## `app/models.py`

Define as tabelas do banco através do SQLAlchemy ORM.

### Aluno

Tabela:

``` text
alunos
```

Campos:

  Campo          Tipo      Descrição
  -------------- --------- ----------------------
  `id`           Integer   Chave primária
  `nome`         String    Nome do aluno
  `nivel`        String    Nível esportivo
  `modalidade`   String    Modalidade praticada

------------------------------------------------------------------------

### Usuario

Tabela:

``` text
usuarios
```

Campos:

  Campo          Descrição
  -------------- --------------------------------------------------------
  `id`           Identificador
  `usuario`      Nome utilizado no login
  `senha_hash`   Senha protegida por hash
  `tipo`         `professor` ou `aluno`
  `aluno_id`     Liga uma conta de aluno ao registro da tabela `alunos`

A relação principal é:

``` text
Usuario
   │
   └── aluno_id
          │
          ▼
        Aluno
```

Uma conta de professor pode ter `aluno_id` nulo.

------------------------------------------------------------------------

### TreinoBase

Tabela:

``` text
treinos_base
```

Representa um modelo reutilizável de treino.

Campos:

  Campo          Descrição
  -------------- ---------------------------
  `id`           Identificador
  `titulo`       Nome do treino
  `modalidade`   Modalidade correspondente
  `descricao`    Instruções do treino
  `ritmo_alvo`   Ritmo/meta opcional

Exemplo conceitual:

``` text
Título: Corrida intervalada
Modalidade: Corrida
Descrição: 6 x 400 m com recuperação
Ritmo alvo: 4:30 min/km
```

O treino base não pertence diretamente a um aluno. Ele funciona como um
modelo que posteriormente pode ser agendado.

------------------------------------------------------------------------

### TreinoAgendado

Tabela:

``` text
treinos_agendados
```

É a ligação entre:

``` text
Aluno + Treino Base + Data
```

Campos principais:

  Campo              Descrição
  ------------------ -----------------------------
  `id`               Identificador
  `aluno_id`         Aluno que receberá o treino
  `treino_base_id`   Treino utilizado
  `data_planejada`   Data programada
  `concluido`        Indica se o aluno concluiu

Também armazena o feedback:

  Campo                    Descrição
  ------------------------ -----------------------
  `feedback_nota`          Nota do treino
  `feedback_comentario`    Comentário do aluno
  `feedback_dificuldade`   Dificuldade informada

------------------------------------------------------------------------

## 6. Relacionamento do banco

De forma simplificada:

``` text
┌──────────────┐
│    ALUNOS    │
│──────────────│
│ id           │
│ nome         │
│ nivel        │
│ modalidade   │
└──────┬───────┘
       │
       │ 1
       │
       │
       ▼
┌───────────────────┐
│ TREINOS_AGENDADOS │
│───────────────────│
│ id                │
│ aluno_id          │
│ treino_base_id    │
│ data_planejada    │
│ concluido         │
│ feedback_*        │
└─────────┬─────────┘
          │
          │ N:1
          ▼
┌───────────────────┐
│   TREINOS_BASE    │
│───────────────────│
│ id                │
│ titulo            │
│ modalidade        │
│ descricao         │
│ ritmo_alvo        │
└───────────────────┘

ALUNOS
   │
   │ 1:1
   ▼
USUARIOS
```

------------------------------------------------------------------------

# 7. Schemas e validação

## `app/schemas.py`

Os schemas Pydantic determinam o formato dos dados aceitos pela API.

### `Login`

Recebe:

``` json
{
  "usuario": "nome_usuario",
  "senha": "senha"
}
```

### `AlunoCreate`

Recebe:

``` json
{
  "nome": "Nome do aluno",
  "nivel": "Intermediário",
  "modalidade": "Corrida",
  "usuario": "aluno01",
  "senha": "senha123"
}
```

O usuário precisa possuir pelo menos 3 caracteres e a senha pelo menos
4, conforme as validações atuais.

### `TreinoBaseCreate`

Recebe título, modalidade, descrição e ritmo alvo opcional.

### `TreinoAgendadoCreate`

Recebe:

-   `aluno_id`;
-   `treino_base_id`;
-   `data_planejada`.

### `TreinoEmMassaCreate`

Recebe um treino base e uma data para distribuição.

### `TreinoDiaSemana`

Utilizado no planejamento semanal.

O campo `dia` segue:

``` text
0 = segunda
1 = terça
2 = quarta
3 = quinta
4 = sexta
5 = sábado
6 = domingo
```

A rota de planejamento semanal aceita apenas **0 a 4**, portanto
trabalha de segunda a sexta.

### `FeedbackTreinoCreate`

Recebe:

``` json
{
  "nota": 5,
  "dificuldade": "Moderado",
  "comentario": "Treino realizado normalmente."
}
```

------------------------------------------------------------------------

# 8. Sistema de autenticação

## `app/auth.py`

O SPY TEAM implementa autenticação própria baseada em:

-   hash de senha;
-   PBKDF2-HMAC-SHA256;
-   salt aleatório;
-   token assinado;
-   cookie HTTP-only.

### Proteção das senhas

As senhas não são armazenadas diretamente.

A função:

``` python
hash_senha()
```

gera um salt aleatório e utiliza:

``` text
PBKDF2 + SHA-256
```

com **310.000 iterações**.

O valor armazenado contém:

``` text
iterações$salt$hash
```

A função:

``` python
verificar_senha()
```

recalcula o hash e utiliza `hmac.compare_digest()` para realizar a
comparação.

------------------------------------------------------------------------

## Sessão

Após o login, `criar_token()` cria um token contendo:

``` json
{
  "sub": 1,
  "tipo": "professor",
  "exp": "..."
}
```

Onde:

-   `sub` = ID do usuário;
-   `tipo` = professor ou aluno;
-   `exp` = expiração.

A sessão possui duração configurada de **1 dia**.

O cookie utilizado chama-se:

``` text
spyteam_session
```

Ele é criado como `httponly=True` e `samesite="lax"`.

Na configuração atual, `secure=False`, apropriado para desenvolvimento
local sem HTTPS. Para implantação em produção, essa configuração deve
ser revista.

------------------------------------------------------------------------

## Chave secreta

A aplicação procura a variável:

``` text
SPYTEAM_SECRET
```

Caso não exista, utiliza uma chave de desenvolvimento definida no
código.

Para produção, deve ser definida uma chave secreta forte por variável de
ambiente.

------------------------------------------------------------------------

# 9. Controle de acesso

Existem três dependências importantes.

### `get_current_user`

Lê o cookie, valida o token e busca o usuário no banco.

### `require_professor`

Permite acesso somente quando:

``` python
usuario.tipo == "professor"
```

Caso contrário, retorna HTTP `403`.

### `require_aluno`

Exige:

``` python
usuario.tipo == "aluno"
```

e um `aluno_id` associado.

Isso impede que uma conta de professor utilize endpoints exclusivos do
aluno e vice-versa.

------------------------------------------------------------------------

# 10. Professor inicial

Quando a aplicação inicia, `seed_professor()` verifica se existe algum
professor.

Se não existir, cria automaticamente uma conta.

Por padrão:

``` text
Usuário: professor
Senha: 1234
```

Esses valores podem ser substituídos pelas variáveis:

``` text
PROFESSOR_USUARIO
PROFESSOR_SENHA
```

> Em um ambiente real, não é recomendado manter as credenciais padrão.

------------------------------------------------------------------------

# 11. Páginas do sistema

## `/login`

Renderiza:

``` text
templates/login.html
```

Se já existir uma sessão válida, o usuário é redirecionado
automaticamente.

------------------------------------------------------------------------

## `/home`

Painel do professor.

Arquivo:

``` text
templates/home.html
```

Somente professores podem acessar.

------------------------------------------------------------------------

## `/aluno`

Painel pessoal do aluno.

Arquivo:

``` text
templates/aluno.html
```

Somente alunos autenticados podem acessar.

------------------------------------------------------------------------

## `/novo-aluno`

Tela para cadastro de aluno.

``` text
templates/alunos/novo_aluno.html
```

------------------------------------------------------------------------

## `/alunos`

Lista e gerenciamento dos alunos.

``` text
templates/alunos/alunos.html
```

------------------------------------------------------------------------

## `/novo-treino`

Tela de agendamento.

``` text
templates/treinos/novo_treino.html
```

------------------------------------------------------------------------

## `/novo-treino-base`

Tela para criação de um modelo de treino.

``` text
templates/treinos/novo_treino_base.html
```

------------------------------------------------------------------------

## `/planejamento-semanal`

Interface de planejamento dos treinos de segunda a sexta.

``` text
templates/planejamento_semanal.html
```

------------------------------------------------------------------------

# 12. API

## Autenticação

### `POST /api/login`

Autentica o usuário e cria o cookie de sessão.

### `POST /api/logout`

Remove o cookie.

### `GET /api/me`

Retorna informações da conta atualmente autenticada.

Quando a conta pertence a um aluno, também retorna informações do aluno
vinculado.

------------------------------------------------------------------------

## Alunos

### `POST /api/alunos`

Cadastra um aluno e cria sua conta de acesso.

**Permissão:** professor.

### `GET /api/alunos`

Lista os alunos cadastrados e suas respectivas contas.

**Permissão:** professor.

### `DELETE /api/alunos/{aluno_id}`

Exclui:

1.  treinos agendados do aluno;
2.  conta de usuário vinculada;
3.  registro do aluno.

A ordem evita deixar registros relacionados apontando para um aluno
removido.

**Permissão:** professor.

------------------------------------------------------------------------

## Treinos

### `POST /api/treinos`

Agenda um treino para um aluno específico.

**Permissão:** professor.

### `GET /api/treinos`

Lista todos os treinos agendados, incluindo:

-   aluno;
-   treino;
-   modalidade;
-   descrição;
-   ritmo;
-   data;
-   conclusão;
-   feedback.

**Permissão:** professor.

### `GET /api/alunos/{aluno_id}/treinos`

Lista os treinos de um aluno específico.

**Permissão:** professor.

------------------------------------------------------------------------

## Treinos base

### `GET /api/treinos-base`

Lista os modelos de treino existentes.

### `POST /api/treinos-base`

Cria um novo treino base.

Ambas são rotas exclusivas do professor.

------------------------------------------------------------------------

# 13. Distribuição em massa

## `POST /api/treinos/em-massa`

Essa rota recebe:

``` json
{
  "treino_base_id": 1,
  "data_planejada": "2026-09-15"
}
```

Na implementação atual dessa rota específica, o sistema cria um
`TreinoAgendado` para **cada aluno cadastrado**.

Ela é diferente da rota de planejamento semanal por modalidade explicada
a seguir.

------------------------------------------------------------------------

# 14. Planejamento semanal por modalidade

## `POST /api/treinos/semana`

É uma das principais funcionalidades do projeto.

O professor informa:

-   a segunda-feira que inicia a semana;
-   os treinos escolhidos para os dias;
-   o ID de cada treino base.

Exemplo conceitual:

``` text
Segunda → Corrida leve
Terça   → Natação técnica
Quarta  → Intervalado
Quinta  → Natação resistência
Sexta   → Corrida longa
```

O backend primeiro valida se `data_segunda` realmente representa uma
segunda-feira.

Depois, para cada dia:

1.  localiza o treino base;
2.  identifica sua modalidade;
3.  calcula a data do treino;
4.  procura os alunos;
5.  compara a modalidade do aluno com a modalidade do treino;
6.  agenda o treino somente para os alunos correspondentes;
7.  verifica se aquele mesmo agendamento já existe;
8.  evita duplicações;
9.  salva os novos agendamentos.

------------------------------------------------------------------------

## Normalização de modalidade

Para evitar problemas como:

``` text
Natação
natacao
NATAÇÃO
```

o backend utiliza:

``` python
normalizar_modalidade()
```

A função:

-   remove acentos;
-   remove espaços externos;
-   converte para minúsculas.

Assim, valores equivalentes podem ser comparados com maior segurança.

------------------------------------------------------------------------

# 15. Fluxo do planejamento semanal

``` text
PROFESSOR
    │
    ▼
Escolhe a segunda-feira
    │
    ▼
Escolhe treino para cada dia
    │
    ▼
Backend busca o TreinoBase
    │
    ▼
Identifica a modalidade
    │
    ├──────── Corrida ────────► alunos de Corrida
    │
    └──────── Natação ────────► alunos de Natação
                                  │
                                  ▼
                           TreinoAgendado
                                  │
                                  ▼
                            Painel do aluno
```

------------------------------------------------------------------------

# 16. Painel do aluno

O frontend do aluno utiliza:

``` text
static/js/aluno.js
```

Ao carregar a página, o JavaScript consulta:

``` text
GET /api/me
GET /api/me/treinos
```

O aluno **não informa seu próprio ID na URL**.

O backend utiliza:

``` python
usuario.aluno_id
```

obtido diretamente da sessão autenticada.

Isso é importante para evitar que um aluno simplesmente troque um ID no
navegador e consulte os treinos de outra pessoa.

------------------------------------------------------------------------

# 17. Semana do aluno

O JavaScript calcula a segunda-feira da semana atual e cria sete cards:

``` text
Segunda
Terça
Quarta
Quinta
Sexta
Sábado
Domingo
```

Depois compara a data de cada treino com a data de cada card e mostra o
treino no dia correspondente.

O painel também calcula:

-   total de treinos;
-   treinos pendentes;
-   treinos concluídos.

------------------------------------------------------------------------

# 18. Conclusão e feedback

## `PATCH /api/treinos/{treino_id}/concluir`

Ao concluir um treino, o aluno envia:

-   nota;
-   dificuldade;
-   comentário opcional.

Antes de salvar, o backend verifica se:

1.  o treino existe;
2.  o treino pertence ao aluno autenticado;
3.  ele ainda não foi concluído;
4.  a nota está entre 1 e 5.

Depois:

``` python
treino.feedback_nota = feedback.nota
treino.feedback_dificuldade = feedback.dificuldade
treino.feedback_comentario = feedback.comentario
treino.concluido = True
```

O feedback fica armazenado no próprio registro de `TreinoAgendado`.

------------------------------------------------------------------------

# 19. Segurança no frontend

O arquivo `aluno.js` possui a função:

``` javascript
escapeHtml()
```

Ela substitui caracteres HTML especiais antes de inserir determinados
conteúdos recebidos da API na página.

Isso reduz o risco de conteúdo textual ser interpretado indevidamente
como HTML.

------------------------------------------------------------------------

# 20. Identidade visual

Os recursos visuais ficam em:

``` text
static/
```

A folha de estilos principal é:

``` text
static/css/style.css
```

Os arquivos do logo presentes no projeto são:

``` text
static/img/logo-spy-team.svg
static/img/logo-spy-team.png
```

Para uso web, o SVG é a opção indicada quando o arquivo vetorial está
funcionando corretamente, pois mantém a qualidade independentemente do
tamanho de exibição.

------------------------------------------------------------------------

# 21. Como executar o projeto

## Pré-requisitos

É necessário possuir:

-   Python instalado;
-   `pip`;
-   terminal ou PowerShell.

Recomenda-se utilizar um ambiente virtual.

### 1. Entrar na pasta

``` bash
cd SpyTeam
```

### 2. Criar ambiente virtual

Windows:

``` bash
python -m venv venv
```

### 3. Ativar

PowerShell:

``` powershell
.\venv\Scripts\Activate.ps1
```

Prompt de Comando:

``` cmd
venv\Scripts\activate
```

### 4. Instalar dependências

``` bash
pip install -r requirements.txt
```

### 5. Executar

A partir da raiz do projeto:

``` bash
uvicorn app.main:app --reload
```

O terminal deverá informar o endereço local do servidor. Normalmente o
Uvicorn utiliza a porta `8000` quando nenhuma outra configuração é
fornecida.

------------------------------------------------------------------------

# 22. Primeiro acesso

Na configuração padrão, se ainda não existir professor no banco:

``` text
Usuário: professor
Senha: 1234
```

Depois do login, o professor pode começar cadastrando alunos e treinos
base.

------------------------------------------------------------------------

# 23. Fluxo recomendado de utilização

``` text
1. Iniciar aplicação
        ↓
2. Login do professor
        ↓
3. Cadastrar alunos
        ↓
4. Definir modalidade dos alunos
        ↓
5. Criar treinos base
        ↓
6. Montar planejamento semanal
        ↓
7. Sistema distribui por modalidade
        ↓
8. Aluno faz login
        ↓
9. Aluno visualiza o treino
        ↓
10. Aluno executa o treino
        ↓
11. Marca como concluído
        ↓
12. Envia feedback
        ↓
13. Professor consulta o resultado
```

------------------------------------------------------------------------

# 24. Códigos HTTP utilizados

A API utiliza códigos HTTP para indicar o resultado das operações.

  Código   Significado no projeto
  -------- -------------------------------------------
  `200`    Operação realizada
  `303`    Redirecionamento entre páginas
  `400`    Dados ou operação inválida
  `401`    Usuário não autenticado ou login inválido
  `403`    Usuário autenticado sem permissão
  `404`    Registro não encontrado

------------------------------------------------------------------------

# 25. Variáveis de ambiente

O projeto reconhece:

  Variável              Função
  --------------------- -------------------------------------------
  `SPYTEAM_SECRET`      Chave utilizada na assinatura das sessões
  `PROFESSOR_USUARIO`   Usuário do professor criado inicialmente
  `PROFESSOR_SENHA`     Senha do professor inicial

Exemplo no PowerShell:

``` powershell
$env:SPYTEAM_SECRET="uma-chave-secreta-grande-e-aleatoria"
$env:PROFESSOR_USUARIO="admin"
$env:PROFESSOR_SENHA="uma-senha-forte"
uvicorn app.main:app --reload
```

------------------------------------------------------------------------

# 26. Pontos importantes da implementação atual

### `create_all()` não é sistema de migração

O projeto executa:

``` python
models.Base.metadata.create_all(bind=engine)
```

Isso cria tabelas que ainda não existem, mas **não adiciona
automaticamente novas colunas a tabelas SQLite já existentes**.

Por isso, quando um novo campo é acrescentado a um model, como aconteceu
com `modalidade`, bancos antigos podem precisar de uma
migração/alteração de schema.

Para evolução do projeto, uma opção futura é adotar **Alembic** para
controlar migrações.

### Datas são armazenadas como `String`

Atualmente `data_planejada` é uma coluna `String`.

O sistema utiliza o padrão:

``` text
YYYY-MM-DD
```

Isso funciona na implementação atual, mas uma evolução possível é
utilizar o tipo `Date` do SQLAlchemy.

### A rota `/api/treinos/em-massa` envia para todos

O endpoint de treino em massa atualmente percorre todos os alunos, sem
filtro por modalidade.

Já o endpoint:

``` text
/api/treinos/semana
```

faz a distribuição **por modalidade**.

Essa diferença é importante para manutenção futura.

------------------------------------------------------------------------

# 27. Melhorias futuras

Algumas evoluções possíveis para o projeto:

-   implementar Alembic para migrações;
-   criar edição de alunos;
-   criar edição e exclusão de treinos base;
-   permitir cancelar/remover um agendamento;
-   adicionar filtros por modalidade;
-   criar navegação entre semanas no painel do aluno;
-   adicionar estatísticas de desempenho;
-   criar gráficos de evolução;
-   permitir ao professor responder ao feedback;
-   criar recuperação de senha;
-   utilizar HTTPS e configurações de produção;
-   adicionar testes automatizados;
-   adicionar logs;
-   validar de forma mais rígida os valores de dificuldade;
-   utilizar `Date` para datas;
-   melhorar tratamento de erros no frontend;
-   criar deploy em servidor/nuvem.

Essas são sugestões de evolução; não representam funcionalidades já
existentes.

------------------------------------------------------------------------

# 28. Resumo da arquitetura

``` text
┌─────────────────────────────────────────┐
│                FRONTEND                 │
│                                         │
│ HTML + CSS + JavaScript + Jinja2        │
└───────────────────┬─────────────────────┘
                    │
                    │ HTTP / JSON
                    ▼
┌─────────────────────────────────────────┐
│                 FASTAPI                 │
│                                         │
│ Rotas + autenticação + regras de negócio│
└───────────────────┬─────────────────────┘
                    │
                    │ SQLAlchemy ORM
                    ▼
┌─────────────────────────────────────────┐
│                 SQLite                  │
│                                         │
│ alunos                                  │
│ usuarios                                │
│ treinos_base                            │
│ treinos_agendados                       │
└─────────────────────────────────────────┘
```

------------------------------------------------------------------------

# 29. Resumo dos arquivos principais

  -------------------------------------------------------------------------------
  Arquivo                                     Responsabilidade
  ------------------------------------------- -----------------------------------
  `app/main.py`                               Aplicação FastAPI, páginas, API e
                                              regras de negócio

  `app/auth.py`                               Senhas, tokens e sessão

  `app/database.py`                           Conexão SQLAlchemy/SQLite

  `app/models.py`                             Estrutura das tabelas

  `app/schemas.py`                            Validação das entradas da API

  `templates/login.html`                      Tela de login

  `templates/home.html`                       Painel do professor

  `templates/aluno.html`                      Painel do aluno

  `templates/alunos/alunos.html`              Gerenciamento de alunos

  `templates/alunos/novo_aluno.html`          Cadastro de aluno

  `templates/treinos/novo_treino.html`        Agendamento de treino

  `templates/treinos/novo_treino_base.html`   Cadastro de treino base

  `templates/planejamento_semanal.html`       Planejamento de segunda a sexta

  `static/js/aluno.js`                        Lógica dinâmica do painel do aluno

  `static/css/style.css`                      Estilos da interface

  `assessoria.db`                             Banco SQLite utilizado pela
                                              aplicação

  `requirements.txt`                          Dependências Python
  -------------------------------------------------------------------------------

------------------------------------------------------------------------

# 30. Sobre o projeto

O SPY TEAM foi estruturado como uma aplicação web com separação entre:

-   **interface**;
-   **API**;
-   **validação**;
-   **autenticação**;
-   **modelos de banco**;
-   **persistência dos dados**.

A principal regra de negócio é permitir que o professor organize o
treinamento de seus alunos e que cada aluno tenha acesso individual aos
próprios treinos, com distribuição semanal por modalidade e retorno por
meio de feedback após a conclusão.

------------------------------------------------------------------------

## SPY TEAM

**Planejamento, organização e acompanhamento de treinos em uma única
plataforma.**
