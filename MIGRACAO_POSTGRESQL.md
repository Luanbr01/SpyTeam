# SPY TEAM — Migração segura de SQLite para PostgreSQL no Railway

Este guia migra o banco atual `/data/assessoria.db` para PostgreSQL sem apagar o SQLite original.

## Antes de começar

Mantenha o Railway Volume conectado em:

```text
/data
```

Mesmo depois da migração, o SPY TEAM continua usando o Volume para arquivos persistentes, como fotos de perfil.

Durante a migração, evite cadastrar alunos, concluir treinos ou alterar contas. O script bloqueia escritas no SQLite durante a cópia para obter um snapshot consistente, mas a troca final deve ser feita logo em seguida.

---

## 1. Faça o deploy desta versão primeiro

Não crie `DATABASE_URL` ainda.

Depois do push, o sistema continuará usando o SQLite atual porque `DATABASE_URL` ainda não existe.

O deploy instala o driver:

```text
psycopg 3
```

---

## 2. Adicione PostgreSQL ao projeto Railway

No projeto Railway:

```text
+ New
→ Database
→ PostgreSQL
```

Aguarde o serviço PostgreSQL ficar ativo.

---

## 3. Crie somente a variável temporária de migração

No serviço **SpyTeam**, abra:

```text
Variables
```

Adicione:

```env
POSTGRES_MIGRATION_URL=${{Postgres.DATABASE_URL}}
```

Se o serviço de banco tiver outro nome, substitua `Postgres` pelo nome real do serviço.

Neste momento, **não configure `DATABASE_URL`** no SpyTeam.

Assim:

```text
Aplicação em produção → continua no SQLite
Script de migração    → consegue acessar PostgreSQL
```

---

## 4. Faça um backup do SQLite

Abra o shell do serviço:

```powershell
railway ssh
```

Dentro do container:

```bash
cp /data/assessoria.db /data/assessoria-pre-postgres.db
```

Confira:

```bash
ls -lh /data/assessoria*.db
```

Você deve ver pelo menos:

```text
/data/assessoria.db
/data/assessoria-pre-postgres.db
```

---

## 5. Execute a migração

Ainda dentro do `railway ssh`:

```bash
python scripts/migrar_sqlite_para_postgres.py
```

O script:

1. conecta ao PostgreSQL;
2. verifica se o destino está vazio;
3. verifica e-mails duplicados;
4. cria a estrutura atual;
5. bloqueia temporariamente escritas no SQLite;
6. copia as tabelas preservando IDs;
7. ajusta as sequences do PostgreSQL;
8. compara as contagens finais.

No final deve aparecer:

```text
[migracao] MIGRAÇÃO CONCLUÍDA COM SUCESSO.
[migracao] O SQLite original NÃO foi apagado.
```

Se ocorrer qualquer erro, **não crie `DATABASE_URL`**. O site continuará usando SQLite normalmente.

---

## 6. Troque o SPY TEAM para PostgreSQL

Somente depois da mensagem de sucesso, volte para:

```text
Railway
→ SpyTeam
→ Variables
```

Adicione:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

O Railway fará um novo deploy/restart com a variável.

`DATABASE_URL` tem prioridade sobre `DATABASE_PATH`, portanto o SPY TEAM passará a usar PostgreSQL.

---

## 7. Confirme pelos logs

No início do container deve aparecer:

```text
[SpyTeam] Banco de dados ativo: PostgreSQL (DATABASE_URL)
[SpyTeam] Pasta persistente de arquivos: /data
```

E não:

```text
Banco de dados ativo: SQLite
```

---

## 8. Confira o healthcheck

Abra:

```text
https://www.spyteam.com.br/health
```

Retorno esperado:

```json
{
  "status": "ok",
  "app": "SpyTeam",
  "database": "postgresql"
}
```

---

## 9. Testes obrigatórios após a troca

Teste antes de considerar a migração concluída:

```text
[ ] login professor
[ ] login aluno
[ ] lista de alunos
[ ] modalidades dos alunos
[ ] treinos base
[ ] treinos agendados
[ ] conclusão de treino
[ ] feedback
[ ] planejamento semanal
[ ] calendário mensal
[ ] notificações PWA
[ ] recuperação de senha
[ ] verificação/troca de e-mail
[ ] foto de perfil
[ ] dashboard professor
[ ] dashboard aluno
```

---

## 10. Depois de validar

Você pode remover a variável temporária:

```text
POSTGRES_MIGRATION_URL
```

`DATABASE_PATH=/data/assessoria.db` pode também ser removida para evitar confusão, pois `DATABASE_URL` passa a ser o banco principal.

**Não remova o Railway Volume.** Ele continua guardando fotos e outros arquivos persistentes.

Também não apague imediatamente:

```text
/data/assessoria-pre-postgres.db
```

Mantenha o backup até ter certeza de que tudo está estável.

---

# Rollback rápido

Se logo após a troca surgir um problema grave:

1. remova `DATABASE_URL` do serviço SpyTeam;
2. confirme que `DATABASE_PATH=/data/assessoria.db` ainda existe ou que o Volume está em `/data`;
3. redeploy/restart.

O SPY TEAM voltará a usar o SQLite antigo.

Atenção: dados gravados **depois** da troca para PostgreSQL não estarão no SQLite antigo. Por isso faça os testes imediatamente após a migração antes de liberar novas alterações no sistema.
