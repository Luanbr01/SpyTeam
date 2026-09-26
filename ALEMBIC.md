# Alembic no SPY TEAM

O SPY TEAM usa Alembic para versionar o schema do PostgreSQL e do SQLite de desenvolvimento.

## Estrutura

```text
alembic.ini
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 20260925_01_baseline_spyteam.py
    └── 20260925_02_indices_email.py

scripts/
└── aplicar_migracoes.py
```

## Primeiro deploy em um banco que já existe

O PostgreSQL atual já possui dados. Por isso o primeiro deploy não tenta criar as tabelas novamente.

`scripts/aplicar_migracoes.py`:

1. verifica se existe `alembic_version`;
2. detecta as tabelas atuais;
3. valida todas as tabelas e colunas do modelo;
4. se tudo estiver compatível, marca `20260925_01` como baseline;
5. executa `alembic upgrade head`, que aplica as revisões posteriores, incluindo `20260925_02`;
6. inicia o FastAPI somente depois do sucesso.

Nenhum registro é recriado ou apagado durante o stamp.

## Deploy normal

O Dockerfile executa:

```bash
python scripts/aplicar_migracoes.py && python -m uvicorn ...
```

Se houver nova revisão em `alembic/versions`, ela é aplicada antes do servidor começar a receber tráfego.

Se uma migração falhar, o Uvicorn não inicia. Isso evita rodar código novo sobre um schema parcialmente atualizado.

## Desenvolvimento local

Antes de iniciar o servidor:

```powershell
python scripts/aplicar_migracoes.py
python -m uvicorn app.main:app --reload
```

Ver versão atual:

```powershell
alembic current
```

Ver histórico:

```powershell
alembic history
```

## Criar uma nova migração

1. Edite `app/models.py`.
2. Garanta que o banco local está na revisão mais recente.
3. Gere a revisão:

```powershell
alembic revision --autogenerate -m "adicionar campo exemplo"
```

4. Abra o arquivo criado em `alembic/versions/` e revise o `upgrade()` e `downgrade()`.
5. Aplique localmente:

```powershell
alembic upgrade head
```

6. Teste o sistema.
7. Faça commit do arquivo de migração junto com o código que depende dele.

## Downgrade

Quando a migração tiver reversão segura:

```powershell
alembic downgrade -1
```

Não use downgrade automaticamente em produção. Mudanças que removem colunas, tabelas ou dados devem ter backup e revisão manual.

## Regra do projeto

A partir desta versão, não adicionar `ALTER TABLE`, `CREATE TABLE` ou `Base.metadata.create_all()` no startup do FastAPI para mudanças normais de schema.

Toda mudança estrutural deve receber uma nova revisão em `alembic/versions/`.
