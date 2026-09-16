# SPY TEAM — Deploy no Railway

Este pacote foi preparado para publicar o SpyTeam sem depender do computador local.

## O que foi preparado

- FastAPI escutando a porta fornecida pelo Railway.
- SQLite compatível com Volume persistente.
- `/health` para verificação do serviço.
- Cookies seguros em HTTPS.
- `SPYTEAM_SECRET` obrigatório no Railway.
- Bancos `.db`, `venv` e arquivos locais não são enviados ao GitHub.
- O logo e o visual atual do SpyTeam foram preservados.

## 1. Coloque esta versão no GitHub

Na pasta do projeto:

    git add .
    git commit -m "Preparar SpyTeam para deploy no Railway"
    git push

## 2. Crie o projeto no Railway

1. Entre no Railway.
2. New Project.
3. Deploy from GitHub repo.
4. Escolha o repositório SpyTeam.

O primeiro deploy pode ficar aguardando/falhar enquanto as variáveis ainda não estiverem configuradas. Isso é esperado.

## 3. Configure as variáveis

Na aba Variables do serviço, crie:

    SPYTEAM_SECRET=<chave longa e aleatória>
    PROFESSOR_USUARIO=<seu usuário>
    PROFESSOR_SENHA=<sua senha forte>
    COOKIE_SECURE=true

Para gerar uma chave pelo Windows/PowerShell:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Não publique essa chave no GitHub.

## 4. Configure o Start Command

Em Settings > Deploy > Start Command:

    uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'

O projeto também inclui um Procfile com esse comando.

## 5. Crie o Volume para o SQLite

No Railway, adicione um Volume ao serviço e use:

    /data

O SpyTeam detecta automaticamente `RAILWAY_VOLUME_MOUNT_PATH` e passa a usar:

    /data/assessoria.db

Sem o Volume, um banco SQLite salvo no filesystem do container pode ser perdido em redeploys.

## 6A. Se quiser começar com banco novo

Não faça upload de nenhum `.db`.

Ao iniciar, o SpyTeam cria as tabelas. Se não houver professor no banco, usa
`PROFESSOR_USUARIO` e `PROFESSOR_SENHA` para criar a conta inicial.

## 6B. Se quiser manter seu banco atual

NÃO coloque `assessoria.db` no GitHub.

Instale a Railway CLI no Windows:

    npm i -g @railway/cli

Depois:

    railway login

Na pasta local do SpyTeam:

    railway link

Escolha o projeto, ambiente e serviço corretos.

Com o Volume já conectado, envie o banco diretamente para ele:

    railway volume files upload ./assessoria.db /assessoria.db

Depois:

    railway restart

O banco ficará disponível para a aplicação como:

    /data/assessoria.db

## 7. Healthcheck

No Railway, configure o Healthcheck Path como:

    /health

Ao abrir:

    https://SEU-DOMINIO/health

o retorno esperado é:

    {"status":"ok","app":"SpyTeam"}

## 8. Gere a URL pública

No serviço:

Settings > Networking > Public Networking > Generate Domain

O Railway fornecerá uma URL semelhante a:

    https://spyteam-xxxx.up.railway.app

## 9. Depois do deploy

Teste:

- login do professor;
- login de um aluno;
- cadastro de aluno;
- exclusão de aluno;
- criação de treino;
- planejamento semanal;
- feedback/conclusão de treino;
- logout;
- logo e arquivos CSS/JS.

## Domínio próprio

Depois que a URL do Railway estiver funcionando, você pode adicionar um domínio
próprio em Settings > Networking > Custom Domain.
