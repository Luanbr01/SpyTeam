# SPY TEAM — Login com Google

## Objetivo

Permitir que professor ou aluno entre com Google **somente quando o e-mail da Conta Google já estiver cadastrado no SPY TEAM**.

O recurso não cria usuários automaticamente e não altera a regra atual de cadastro de alunos.

## 1. Criar o Client ID no Google Cloud

No Google Cloud / Google Auth Platform:

1. crie ou selecione um projeto;
2. abra a área de clientes OAuth;
3. crie um cliente do tipo **Web application**;
4. em **Authorized JavaScript origins**, adicione:

```text
https://www.spyteam.com.br
```

Para testes locais, opcionalmente:

```text
http://localhost:8000
http://127.0.0.1:8000
```

Esta implementação usa o modo popup/callback do Google Identity Services e não precisa de redirect URI próprio.

## 2. Railway

No serviço `SpyTeam` adicione:

```text
GOOGLE_CLIENT_ID=SEU_CLIENT_ID.apps.googleusercontent.com
```

Não adicione o Client ID do exemplo literalmente.

**Não é necessário `GOOGLE_CLIENT_SECRET` nesta implementação.**

Depois faça redeploy.

## 3. Regra de vínculo

O SPY TEAM compara o e-mail do ID token do Google com:

```text
usuarios.email
```

Exemplo:

```text
SPY TEAM: aluno@gmail.com
Google:   aluno@gmail.com
=> login permitido
```

```text
SPY TEAM: aluno@gmail.com
Google:   outro@gmail.com
=> login recusado
```

Não existe cadastro automático pelo Google.

## 4. Segurança

O backend valida o ID token usando `google-auth` e o `GOOGLE_CLIENT_ID` esperado.

Além disso:

- exige `email_verified` do Google;
- aceita Gmail ou Google Workspace;
- rejeita e-mails externos usados como Conta Google quando o Google não é autoridade atual sobre o endereço;
- recusa e-mail duplicado no banco;
- reutiliza a sessão HttpOnly já existente do SPY TEAM;
- registra sucesso/falha na auditoria de login;
- o POST passa pela proteção CSRF já existente.

## 5. Teste

1. confirme que o usuário possui um e-mail Gmail ou Workspace cadastrado no SPY TEAM;
2. abra `/login` em uma janela anônima;
3. clique em **Fazer login com o Google**;
4. selecione a conta com o mesmo e-mail;
5. confirme que professor vai para `/home` e aluno vai para `/aluno`.

Teste também uma Conta Google com e-mail diferente. O acesso deve ser recusado.
