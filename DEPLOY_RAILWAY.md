# SPY TEAM — Deploy no Railway com PostgreSQL

## Arquitetura de produção

```text
Navegador / PWA
      ↓
FastAPI / Uvicorn
      ↓
PostgreSQL (dados relacionais)

Railway Volume /data
      ↓
Fotos e arquivos persistentes
```

O PostgreSQL é o banco principal de produção. O Volume continua conectado porque a aplicação usa `/data` para fotos de perfil e outros arquivos persistentes.

## Variáveis principais

```env
SPYTEAM_SECRET=<chave longa>
COOKIE_SECURE=true
DATABASE_URL=${{Postgres.DATABASE_URL}}
RESEND_API_KEY=<chave>
EMAIL_FROM=SPY TEAM <noreply@spyteam.com.br>
APP_URL=https://www.spyteam.com.br
EMAIL_MODE=resend
```

PWA/Web Push:

```env
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_SUBJECT=mailto:noreply@spyteam.com.br
```

## PostgreSQL

No projeto Railway:

```text
+ New
→ Database
→ PostgreSQL
```

No serviço SpyTeam crie a referência:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

## Volume

Mantenha o Volume conectado ao serviço SpyTeam com mount path:

```text
/data
```

O Volume não é mais o banco relacional, mas continua armazenando uploads.

## Dockerfile

O projeto instala as dependências via `requirements.txt` e inicia com:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

Deixe Build Command e Start Command personalizados vazios quando estiver usando o Dockerfile do projeto.

## Healthcheck

Configure:

```text
/health
```

Em PostgreSQL o retorno esperado inclui:

```json
{"status":"ok","app":"SpyTeam","database":"postgresql"}
```

## Migração do SQLite existente

Não ative `DATABASE_URL` antes de copiar os dados atuais.

Siga:

```text
MIGRACAO_POSTGRESQL.md
```

O processo usa `POSTGRES_MIGRATION_URL` temporariamente para copiar `/data/assessoria.db` para PostgreSQL antes do cutover.
