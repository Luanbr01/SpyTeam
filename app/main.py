# ============================================================
# MAIN.PY
# API principal do SpyTeam
# ============================================================

import os
import re
import time
import unicodedata

from fastapi import FastAPI, Depends, HTTPException, Request, status

from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse
)

from fastapi.staticfiles import StaticFiles

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import (
    engine,
    SessionLocal
)

from . import models
from . import schemas

from .auth import (
    COOKIE_NAME,
    criar_token,
    criar_token_recuperacao,
    hash_senha,
    hash_token_recuperacao,
    ler_token,
    verificar_senha
)

from .email_service import (
    enviar_email_recuperacao
)

# ============================================================
# CRIA AS TABELAS
# ============================================================
#
# Se a tabela ainda não existir, ela será criada.
#
# IMPORTANTE:
# Isso NÃO apaga seu banco.
#
# ============================================================

models.Base.metadata.create_all(
    bind=engine
)


# ============================================================
# MIGRAÇÃO LEVE DO SQLITE
# ============================================================

def migrar_banco():
    """Adiciona colunas novas sem apagar os dados existentes."""

    with engine.begin() as conexao:
        colunas = {
            linha[1]
            for linha in conexao.exec_driver_sql(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        if "email" not in colunas:
            conexao.exec_driver_sql(
                "ALTER TABLE usuarios ADD COLUMN email VARCHAR"
            )

        conexao.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            ux_usuarios_email_nocase
            ON usuarios(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email <> ''
            """
        )


migrar_banco()


# ============================================================
# FASTAPI
# ============================================================

from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="SpyTeam"
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(
    directory="templates"
)


# ============================================================
# CONFIGURAÇÃO DE PRODUÇÃO
# ============================================================

def _env_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)

    if valor is None:
        return padrao

    return valor.strip().lower() in {
        "1", "true", "sim", "yes", "on"
    }


EM_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT_NAME")
)

COOKIE_SECURE = _env_bool(
    "COOKIE_SECURE",
    padrao=EM_RAILWAY
)

# ============================================================
# NORMALIZAR MODALIDADE
# ============================================================
def normalizar_modalidade(valor: str) -> str:
    """Compara modalidades sem diferença de maiúsculas/acentos."""
    return (
        unicodedata.normalize("NFD", str(valor or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


# ============================================================
# NORMALIZAR USUÁRIO E E-MAIL
# ============================================================

def normalizar_usuario(valor: str) -> str:
    """
    Usuários não diferenciam maiúsculas/minúsculas.
    Espaços no começo/fim são ignorados e espaços internos
    não são permitidos.
    """

    usuario = str(valor or "").strip()

    if not usuario:
        raise ValueError("Usuário inválido.")

    if any(caractere.isspace() for caractere in usuario):
        raise ValueError(
            "O usuário não pode conter espaços."
        )

    return usuario.casefold()


EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalizar_email(valor: str) -> str:
    email = str(valor or "").strip().casefold()

    if not EMAIL_REGEX.fullmatch(email):
        raise ValueError("Informe um e-mail válido.")

    return email


def aluno_sem_email(usuario: models.Usuario) -> bool:
    return not str(usuario.email or "").strip()


# ============================================================
# CONEXÃO COM BANCO
# ============================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()


# ============================================================
# IDENTIFICAR USUÁRIO LOGADO
# ============================================================

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    # Pega o cookie salvo no navegador
    token = request.cookies.get(
        COOKIE_NAME
    )

    # Verifica se o token é válido
    payload = ler_token(
        token
    )

    # Não existe login
    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Não autenticado."
        )

    # Procura o usuário no banco
    usuario = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.id
            == int(payload["sub"])
        )
        .first()
    )

    # Usuário não existe
    if not usuario:

        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado."
        )

    return usuario


# ============================================================
# EXIGIR PROFESSOR
# ============================================================

def require_professor(
    usuario: models.Usuario =
    Depends(get_current_user)
):

    # Verifica o tipo da conta
    if usuario.tipo != "professor":

        raise HTTPException(
            status_code=403,
            detail=(
                "Acesso permitido somente "
                "para professores."
            )
        )

    return usuario


# ============================================================
# EXIGIR ALUNO
# ============================================================

def require_aluno(
    usuario: models.Usuario =
    Depends(get_current_user)
):

    # Precisa ser aluno
    #
    # E também precisa ter aluno_id
    if (
        usuario.tipo != "aluno"
        or usuario.aluno_id is None
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Acesso permitido somente "
                "para alunos."
            )
        )

    return usuario


# ============================================================
# EXIGIR ALUNO COM E-MAIL CADASTRADO
# ============================================================

def require_aluno_com_email(
    usuario: models.Usuario =
    Depends(require_aluno)
):

    if aluno_sem_email(usuario):
        raise HTTPException(
            status_code=428,
            detail=(
                "Cadastre seu e-mail antes "
                "de continuar."
            )
        )

    return usuario


# ============================================================
# PROFESSOR INICIAL
# ============================================================

def seed_professor():
    """
    Cria um professor automaticamente caso nenhum professor exista.

    Em produção, usuário e senha precisam estar nas variáveis:
    PROFESSOR_USUARIO e PROFESSOR_SENHA.
    """

    db = SessionLocal()

    try:
        existe = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.tipo == "professor"
            )
            .first()
        )

        # Banco migrado com professor existente: não altera nada.
        if existe:
            return

        usuario = os.getenv("PROFESSOR_USUARIO")
        senha = os.getenv("PROFESSOR_SENHA")

        # No ambiente local mantemos os valores de desenvolvimento.
        if not EM_RAILWAY:
            usuario = usuario or "professor"
            senha = senha or "1234"

        # Em produção, não cria credenciais padrão conhecidas.
        if not usuario or not senha:
            print(
                "[SpyTeam] Professor inicial não criado. "
                "Configure PROFESSOR_USUARIO e PROFESSOR_SENHA."
            )
            return

        try:
            usuario_normalizado = normalizar_usuario(
                usuario
            )
        except ValueError as erro:
            print(
                "[SpyTeam] PROFESSOR_USUARIO inválido:",
                erro
            )
            return

        db.add(
            models.Usuario(
                usuario=usuario_normalizado,
                senha_hash=hash_senha(senha),
                tipo="professor"
            )
        )

        db.commit()

    finally:
        db.close()


# Executa criação do professor
seed_professor()


# ============================================================
# HEALTHCHECK
# ============================================================

@app.get("/health", include_in_schema=False)
def health():
    return {
        "status": "ok",
        "app": "SpyTeam"
    }


# ============================================================
# ROTA RAIZ
# ============================================================

@app.get("/")
def index(
    request: Request,
    db: Session = Depends(get_db)
):

    # Recupera login atual
    payload = ler_token(
        request.cookies.get(
            COOKIE_NAME
        )
    )

    # Não está logado
    if not payload:

        return RedirectResponse(
            "/login",
            status_code=303
        )

    # Professor
    if payload.get("tipo") == "professor":

        return RedirectResponse(
            "/home",
            status_code=303
        )

    # Aluno
    usuario_db = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.id
            == int(payload["sub"])
        )
        .first()
    )

    if (
        usuario_db
        and usuario_db.tipo == "aluno"
        and aluno_sem_email(usuario_db)
    ):
        return RedirectResponse(
            "/aluno/cadastrar-email",
            status_code=303
        )

    return RedirectResponse(
        "/aluno",
        status_code=303
    )


# ============================================================
# PÁGINA DE LOGIN
# ============================================================

@app.get("/login")
def pagina_login(
    request: Request
):

    # Verifica se já está logado
    payload = ler_token(
        request.cookies.get(
            COOKIE_NAME
        )
    )

    # Se já estiver logado,
    # não precisa mostrar login novamente
    if payload:

        if payload.get("tipo") == "professor":

            return RedirectResponse(
                "/home",
                status_code=303
            )

        return RedirectResponse(
            "/aluno",
            status_code=303
        )

    # Mostra login
    return templates.TemplateResponse(
    request=request,
    name="login.html"
)
    


# ============================================================
# RECUPERAÇÃO DE SENHA - PÁGINAS PÚBLICAS
# ============================================================

@app.get("/esqueci-senha")
def pagina_esqueci_senha(
    request: Request
):
    return templates.TemplateResponse(
        request=request,
        name="esqueci_senha.html"
    )


@app.get("/redefinir-senha")
def pagina_redefinir_senha(
    request: Request
):
    return templates.TemplateResponse(
        request=request,
        name="redefinir_senha.html"
    )


# ============================================================
# PRIMEIRO ACESSO - CADASTRAR E-MAIL
# ============================================================

@app.get("/aluno/cadastrar-email")
def pagina_cadastrar_email(
    request: Request,
    usuario: models.Usuario =
    Depends(require_aluno)
):

    if not aluno_sem_email(usuario):
        return RedirectResponse(
            "/aluno",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="Aluno/cadastrar_email.html"
    )


# ============================================================
# HOME DO PROFESSOR
# ============================================================

@app.get("/home")
def home(
    request: Request,
    usuario: models.Usuario =
    Depends(require_professor)
):

    return templates.TemplateResponse(
    request=request,
    name="Professor/home.html"
)


# ============================================================
# PAINEL DO ALUNO
# ============================================================

@app.get("/aluno")
def aluno(
    request: Request,
    usuario: models.Usuario =
    Depends(require_aluno)
):

    if aluno_sem_email(usuario):
        return RedirectResponse(
            "/aluno/cadastrar-email",
            status_code=303
        )

    return templates.TemplateResponse(
    request=request,
    name="Aluno/home.html"
)


# ============================================================
# HISTÓRICO DO ALUNO
# ============================================================

@app.get("/aluno/historico")
def aluno_historico(
    request: Request,
    usuario: models.Usuario =
    Depends(require_aluno)
):

    if aluno_sem_email(usuario):
        return RedirectResponse(
            "/aluno/cadastrar-email",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="Aluno/historico.html"
    )


# ============================================================
# PERFIL DO ALUNO
# ============================================================

@app.get("/aluno/perfil")
def aluno_perfil(
    request: Request,
    usuario: models.Usuario =
    Depends(require_aluno)
):

    if aluno_sem_email(usuario):
        return RedirectResponse(
            "/aluno/cadastrar-email",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="Aluno/perfil.html"
    )


# ============================================================
# NOVO ALUNO
# ============================================================

@app.get("/novo-aluno")
def pagina_novo_aluno(
    request: Request,
    usuario: models.Usuario =
    Depends(require_professor)
):

    return templates.TemplateResponse(
    request=request,
    name="Professor/novo_aluno.html"
)
# ============================================================
# PÁGINA DE ALUNOS
# ============================================================

@app.get("/alunos")
def pagina_alunos(

    request: Request,

    professor: models.Usuario =
        Depends(require_professor)

):

    return templates.TemplateResponse(

        request=request,

        name="Professor/alunos.html"
    )


# ============================================================
# NOVO TREINO
# ============================================================

@app.get("/novo-treino")
def pagina_novo_treino(
    request: Request,
    usuario: models.Usuario =
    Depends(require_professor)
):

    return templates.TemplateResponse(
    request=request,
    name="Professor/treinos/novo_treino.html"
)


# ============================================================
# NOVO TREINO BASE
# ============================================================

@app.get("/novo-treino-base")
def pagina_novo_treino_base(
    request: Request,
    usuario: models.Usuario =
    Depends(require_professor)
):

    return templates.TemplateResponse(
    request=request,
    name="Professor/treinos/novo_treino_base.html"
)

# ============================================================
# GERENCIAR TREINOS BASE
# ============================================================

@app.get("/treinos-base")
def pagina_treinos_base(

    request: Request,

    usuario: models.Usuario =
        Depends(require_professor)

):

    return templates.TemplateResponse(

        request=request,

        name="Professor/treinos/treinos_base.html"
    )

# ============================================================
# EDITAR TREINO BASE - PÁGINA
# ============================================================

@app.get("/editar-treino-base/{treino_base_id}")
def pagina_editar_treino_base(

    treino_base_id: int,

    request: Request,

    usuario: models.Usuario =
        Depends(require_professor)

):

    return templates.TemplateResponse(

        request=request,

        name="Professor/treinos/editar_treino_base.html"
    )

@app.get("/planejamento-semanal")
def pagina_planejamento_semanal(
    request: Request,
    usuario: models.Usuario = Depends(require_professor)
):
    return templates.TemplateResponse(
        request=request,
        name="Professor/planejamento_semanal.html",
        context={
            "request": request
        }
    )

# ============================================================
# LOGIN
# ============================================================

@app.post("/api/login")
def login(
    dados: schemas.Login,
    db: Session = Depends(get_db)
):

    # Usuário é case-insensitive e não aceita espaços internos.
    try:
        usuario_normalizado = normalizar_usuario(
            dados.usuario
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos."
        )

    usuario = (
        db.query(models.Usuario)
        .filter(
            func.lower(
                func.trim(
                    models.Usuario.usuario
                )
            )
            == usuario_normalizado
        )
        .first()
    )

    # Usuário inexistente ou senha errada
    if (
        not usuario
        or not verificar_senha(
            dados.senha,
            usuario.senha_hash
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos."
        )

    # Cria token
    token = criar_token(
        usuario.id,
        usuario.tipo
    )

    # Define para onde o usuário será enviado
    if usuario.tipo == "professor":

        destino = "/home"

    else:

        destino = (
            "/aluno/cadastrar-email"
            if aluno_sem_email(usuario)
            else "/aluno"
        )

    # Retorna resposta
    resposta = JSONResponse(
        {
            "mensagem":
                "Login realizado com sucesso!",

            "tipo":
                usuario.tipo,

            "usuario":
                usuario.usuario,

            "redirect":
                destino
        }
    )

    # Salva o cookie
    resposta.set_cookie(
        key=COOKIE_NAME,

        value=token,

        httponly=True,

        samesite="lax",

        # False localmente e True no Railway/HTTPS
        secure=COOKIE_SECURE,

        # 1 dia
        max_age=60 * 60 * 24
    )

    return resposta


# ============================================================
# LOGOUT
# ============================================================

@app.post("/api/logout")
def logout():

    resposta = JSONResponse(
        {
            "mensagem":
                "Logout realizado."
        }
    )

    # Apaga o cookie
    resposta.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    return resposta


# ============================================================
# INFORMAÇÕES DO USUÁRIO LOGADO
# ============================================================

@app.get("/api/me")
def me(
    usuario: models.Usuario =
    Depends(get_current_user),

    db: Session =
    Depends(get_db)
):

    # Dados básicos
    dados = {

        "id":
            usuario.id,

        "usuario":
            usuario.usuario,

        "tipo":
            usuario.tipo,

        "email":
            usuario.email,

        "email_cadastrado":
            not aluno_sem_email(usuario)
    }

    # Se for aluno,
    # também buscamos os dados do aluno
    if (
        usuario.tipo == "aluno"
        and usuario.aluno_id
    ):

        aluno_db = (
            db.query(models.Aluno)
            .filter(
                models.Aluno.id
                == usuario.aluno_id
            )
            .first()
        )

        if aluno_db:

            dados["aluno"] = {

                "id":
                    aluno_db.id,

                "nome":
                    aluno_db.nome,

                "nivel":
                    aluno_db.nivel,

                "modalidade":
                    aluno_db.modalidade
            }

    return dados




# ============================================================
# CADASTRAR E-MAIL NO PRIMEIRO ACESSO
# ============================================================

@app.patch("/api/me/email")
def cadastrar_email_aluno(
    dados: schemas.CadastroEmailAluno,
    db: Session = Depends(get_db),
    aluno_logado: models.Usuario =
    Depends(require_aluno)
):

    if not aluno_sem_email(aluno_logado):
        raise HTTPException(
            status_code=400,
            detail="O e-mail já foi cadastrado."
        )

    try:
        email = normalizar_email(
            dados.email
        )
        confirmar = normalizar_email(
            dados.confirmar_email
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    if email != confirmar:
        raise HTTPException(
            status_code=400,
            detail="Os e-mails não conferem."
        )

    existente = (
        db.query(models.Usuario)
        .filter(
            func.lower(models.Usuario.email)
            == email,
            models.Usuario.id
            != aluno_logado.id
        )
        .first()
    )

    if existente:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este e-mail já está vinculado "
                "a outra conta."
            )
        )

    aluno_logado.email = email
    db.commit()

    return {
        "mensagem": "E-mail cadastrado com sucesso.",
        "redirect": "/aluno"
    }


# ============================================================
# ESQUECI MINHA SENHA
# ============================================================

MENSAGEM_RECUPERACAO = (
    "Se existir uma conta associada a este e-mail, "
    "enviaremos as instruções de recuperação."
)


@app.post("/api/senha/esqueci")
def solicitar_recuperacao_senha(
    dados: schemas.SolicitarRecuperacaoSenha,
    db: Session = Depends(get_db)
):

    try:
        email = normalizar_email(dados.email)
    except ValueError:
        return {
            "mensagem": MENSAGEM_RECUPERACAO
        }

    usuario = (
        db.query(models.Usuario)
        .filter(
            func.lower(models.Usuario.email)
            == email,
            models.Usuario.tipo == "aluno"
        )
        .first()
    )

    if not usuario:
        return {
            "mensagem": MENSAGEM_RECUPERACAO
        }

    agora = int(time.time())

    ultimo = (
        db.query(models.RecuperacaoSenha)
        .filter(
            models.RecuperacaoSenha.usuario_id
            == usuario.id
        )
        .order_by(
            models.RecuperacaoSenha.criado_em.desc()
        )
        .first()
    )

    # Evita disparos repetidos de e-mail em sequência.
    if (
        ultimo
        and agora - ultimo.criado_em < 60
    ):
        return {
            "mensagem": MENSAGEM_RECUPERACAO
        }

    # Tokens antigos deixam de valer assim que um novo é gerado.
    (
        db.query(models.RecuperacaoSenha)
        .filter(
            models.RecuperacaoSenha.usuario_id
            == usuario.id,
            models.RecuperacaoSenha.usado
            == False
        )
        .update({
            models.RecuperacaoSenha.usado: True
        })
    )

    token = criar_token_recuperacao()

    recuperacao = models.RecuperacaoSenha(
        usuario_id=usuario.id,
        token_hash=hash_token_recuperacao(token),
        criado_em=agora,
        expira_em=agora + 15 * 60,
        usado=False
    )

    db.add(recuperacao)
    db.commit()
    db.refresh(recuperacao)

    try:
        enviar_email_recuperacao(
            usuario.email,
            token
        )
    except Exception as erro:
        recuperacao.usado = True
        db.commit()
        print(
            "[SpyTeam] Falha no envio do e-mail "
            "de recuperação:",
            erro
        )

    return {
        "mensagem": MENSAGEM_RECUPERACAO
    }


@app.post("/api/senha/redefinir")
def redefinir_senha_por_token(
    dados: schemas.RedefinirSenha,
    db: Session = Depends(get_db)
):

    if dados.nova_senha != dados.confirmar_senha:
        raise HTTPException(
            status_code=400,
            detail="A confirmação da nova senha não confere."
        )

    agora = int(time.time())
    token_hash = hash_token_recuperacao(
        dados.token.strip()
    )

    recuperacao = (
        db.query(models.RecuperacaoSenha)
        .filter(
            models.RecuperacaoSenha.token_hash
            == token_hash,
            models.RecuperacaoSenha.usado
            == False
        )
        .first()
    )

    if (
        not recuperacao
        or recuperacao.expira_em < agora
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Este link é inválido ou expirou. "
                "Solicite uma nova recuperação."
            )
        )

    usuario = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.id
            == recuperacao.usuario_id
        )
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=400,
            detail="Link de recuperação inválido."
        )

    usuario.senha_hash = hash_senha(
        dados.nova_senha
    )

    (
        db.query(models.RecuperacaoSenha)
        .filter(
            models.RecuperacaoSenha.usuario_id
            == usuario.id,
            models.RecuperacaoSenha.usado
            == False
        )
        .update({
            models.RecuperacaoSenha.usado: True
        })
    )

    db.commit()

    return {
        "mensagem": "Senha redefinida com sucesso.",
        "redirect": "/login"
    }


# ============================================================
# ALTERAR SENHA DO ALUNO LOGADO
# ============================================================

@app.patch("/api/me/senha")
def alterar_senha_aluno(
    dados: schemas.AlterarSenhaAluno,

    db: Session =
    Depends(get_db),

    aluno_logado: models.Usuario =
    Depends(require_aluno_com_email)
):

    usuario_db = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.id
            == aluno_logado.id
        )
        .first()
    )

    if not usuario_db:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado."
        )

    if not verificar_senha(
        dados.senha_atual,
        usuario_db.senha_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Senha atual incorreta."
        )

    if (
        dados.nova_senha
        != dados.confirmar_senha
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "A confirmação da nova senha "
                "não confere."
            )
        )

    if verificar_senha(
        dados.nova_senha,
        usuario_db.senha_hash
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "A nova senha precisa ser "
                "diferente da senha atual."
            )
        )

    usuario_db.senha_hash = hash_senha(
        dados.nova_senha
    )

    db.commit()

    return {
        "mensagem":
            "Senha alterada com sucesso."
    }


# ============================================================
# CRIAR ALUNO
# ============================================================

@app.post("/api/alunos")
def criar_aluno(

    aluno: schemas.AlunoCreate,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    # Usuário não diferencia maiúsculas/minúsculas e não aceita espaços.
    try:
        usuario_normalizado = normalizar_usuario(
            aluno.usuario
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    usuario_existente = (
        db.query(models.Usuario)
        .filter(
            func.lower(
                func.trim(
                    models.Usuario.usuario
                )
            )
            == usuario_normalizado
        )
        .first()
    )

    if usuario_existente:

        raise HTTPException(
            status_code=400,
            detail=(
                "Esse usuário já está cadastrado."
            )
        )

    # Cria aluno
    novo_aluno = models.Aluno(

        nome=aluno.nome,

        nivel=aluno.nivel,

        modalidade=aluno.modalidade
    )

    db.add(
        novo_aluno
    )

    # O flush gera o ID
    # antes do commit
    db.flush()

    # Cria conta de login
    novo_usuario = models.Usuario(

        usuario=usuario_normalizado,

        senha_hash=
            hash_senha(aluno.senha),

        tipo="aluno",

        aluno_id=
            novo_aluno.id
    )

    db.add(
        novo_usuario
    )

    # Salva tudo
    db.commit()

    # Atualiza objeto
    db.refresh(
        novo_aluno
    )

    return {

        "id":
            novo_aluno.id,

        "nome":
            novo_aluno.nome,

        "nivel":
            novo_aluno.nivel,

        "usuario":
            usuario_normalizado
    }


# ============================================================
# LISTAR ALUNOS
# ============================================================

@app.get("/api/alunos")
def listar_alunos(

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    alunos = (
        db.query(models.Aluno)
        .all()
    )

    resultado = []

    for aluno in alunos:

        # Procura o login desse aluno
        usuario = (
            db.query(models.Usuario)
            .filter(
                models.Usuario.aluno_id
                == aluno.id
            )
            .first()
        )

        resultado.append({

            "id":
                aluno.id,

            "nome":
                aluno.nome,

            "nivel":
                aluno.nivel,

            "modalidade":
                aluno.modalidade,

            "usuario":
                usuario.usuario
                if usuario
                else None
        })

    return resultado


# ============================================================
# EXCLUIR ALUNO
# SOMENTE PROFESSOR
# ============================================================

@app.delete("/api/alunos/{aluno_id}")
def excluir_aluno(
    aluno_id: int,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    # --------------------------------------------------------
    # BUSCAR O ALUNO
    # --------------------------------------------------------

    aluno = (
        db.query(models.Aluno)
        .filter(
            models.Aluno.id == aluno_id
        )
        .first()
    )

    if not aluno:

        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado."
        )

    # --------------------------------------------------------
    # REMOVER OS TREINOS AGENDADOS DO ALUNO
    #
    # Os treinos possuem uma chave estrangeira para alunos.
    # Por isso removemos primeiro os registros relacionados.
    # Os feedbacks estão dentro de TreinoAgendado e também
    # serão removidos junto com o treino.
    # --------------------------------------------------------

    db.query(models.TreinoAgendado).filter(
        models.TreinoAgendado.aluno_id == aluno_id
    ).delete(
        synchronize_session=False
    )

    # --------------------------------------------------------
    # REMOVER A CONTA DE LOGIN DO ALUNO
    # --------------------------------------------------------

    db.query(models.Usuario).filter(
        models.Usuario.aluno_id == aluno_id
    ).delete(
        synchronize_session=False
    )

    # --------------------------------------------------------
    # REMOVER O ALUNO
    # --------------------------------------------------------

    db.delete(aluno)

    db.commit()

    return {
        "mensagem": "Aluno excluído com sucesso.",
        "id": aluno_id
    }


# ============================================================
# AGENDAR TREINO
# ============================================================

@app.post("/api/treinos")
def agendar_treino(

    treino: schemas.TreinoAgendadoCreate,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    # Verifica aluno
    aluno = (
        db.query(models.Aluno)
        .filter(
            models.Aluno.id
            == treino.aluno_id
        )
        .first()
    )

    if not aluno:

        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado."
        )

    # Verifica treino base
    treino_base = (
        db.query(models.TreinoBase)
        .filter(
            models.TreinoBase.id
            == treino.treino_base_id
        )
        .first()
    )

    if not treino_base:

        raise HTTPException(
            status_code=404,
            detail=
                "Treino base não encontrado."
        )

    # Cria agendamento
    novo_treino = models.TreinoAgendado(

    aluno_id=
        treino.aluno_id,

    treino_base_id=
        treino.treino_base_id,

    titulo=
        treino_base.titulo,

    modalidade=
        treino_base.modalidade,

    descricao=
        treino_base.descricao,

    ritmo_alvo=
        treino_base.ritmo_alvo,

    data_planejada=
        treino.data_planejada
)

    db.add(
        novo_treino
    )

    db.commit()

    db.refresh(
        novo_treino
    )

    return novo_treino


# ============================================================
# LISTAR TODOS OS TREINOS
# USADO PELO PROFESSOR
# ============================================================

@app.get("/api/treinos")
def listar_treinos_agendados(

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    # --------------------------------------------------------
    # BUSCAR TODOS OS TREINOS AGENDADOS
    # --------------------------------------------------------

    treinos = (

        db.query(
            models.TreinoAgendado
        )

        .order_by(
            models.TreinoAgendado
            .data_planejada
            .asc()
        )

        .all()
    )


    # --------------------------------------------------------
    # MONTAR RESPOSTA
    # --------------------------------------------------------

    return [

        {

            # ID do agendamento
            "id":
                t.id,

            # ID do aluno
            "aluno_id":
                t.aluno_id,

            # Nome do aluno
            "aluno":
                t.aluno.nome,

            # ID do treino base
            "treino_base_id":
                t.treino_base_id,

            # Nome do treino
            "treino":
                t.titulo,

            "modalidade":
                t.modalidade,

            "descricao":
                t.descricao,

            "ritmo_alvo":
                t.ritmo_alvo,

            # Data planejada
            "data_planejada":
                t.data_planejada,

            # Status
            "concluido":
                t.concluido,


            # =================================================
            # FEEDBACK DO ALUNO
            # =================================================

            "feedback_nota":
                t.feedback_nota,

            "feedback_dificuldade":
                t.feedback_dificuldade,

            "feedback_comentario":
                t.feedback_comentario

        }

        for t in treinos
    ]

# ============================================================
# LISTAR TREINOS BASE
# USADO PELO PROFESSOR
# ============================================================

@app.get("/api/treinos-base")
def listar_treinos_base(

    db: Session =
        Depends(get_db),

    professor: models.Usuario =
        Depends(require_professor)

):

    # Busca todos os treinos base
    treinos = (

        db.query(
            models.TreinoBase
        )

        .order_by(
            models.TreinoBase.id.asc()
        )

        .all()
    )


    # Retorna os treinos
    return [

        {

            "id":
                treino.id,

            "titulo":
                treino.titulo,

            "modalidade":
                treino.modalidade,

            "descricao":
                treino.descricao,

            "ritmo_alvo":
                treino.ritmo_alvo

        }

        for treino in treinos
    ]
# ============================================================
# CRIAR TREINO BASE
# ============================================================

@app.post("/api/treinos-base")
def criar_treino_base(

    treino: schemas.TreinoBaseCreate,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    novo_treino = models.TreinoBase(

        titulo=
            treino.titulo,

        modalidade=
            treino.modalidade,

        descricao=
            treino.descricao,

        ritmo_alvo=
            treino.ritmo_alvo
    )

    db.add(
        novo_treino
    )

    db.commit()

    db.refresh(
        novo_treino
    )

    return novo_treino

# ============================================================
# EDITAR TREINO BASE
# ============================================================

@app.patch("/api/treinos-base/{treino_base_id}")
def editar_treino_base(

    treino_base_id: int,

    dados: schemas.TreinoBaseCreate,

    db: Session =
        Depends(get_db),

    professor: models.Usuario =
        Depends(require_professor)

):

    # Busca o treino base
    treino_base = (
        db.query(
            models.TreinoBase
        )
        .filter(
            models.TreinoBase.id
            == treino_base_id
        )
        .first()
    )

    # Treino não encontrado
    if not treino_base:

        raise HTTPException(
            status_code=404,
            detail="Treino base não encontrado."
        )

    # Atualiza os dados do treino base
    treino_base.titulo = dados.titulo

    treino_base.modalidade = dados.modalidade

    treino_base.descricao = dados.descricao

    treino_base.ritmo_alvo = dados.ritmo_alvo

    # Salva alterações
    db.commit()

    # Atualiza o objeto
    db.refresh(
        treino_base
    )

    return treino_base

# ============================================================
# EXCLUIR TREINO BASE
# ============================================================

@app.delete("/api/treinos-base/{treino_base_id}")
def excluir_treino_base(

    treino_base_id: int,

    db: Session =
        Depends(get_db),

    professor: models.Usuario =
        Depends(require_professor)

):

    # Busca o treino base
    treino_base = (
        db.query(
            models.TreinoBase
        )
        .filter(
            models.TreinoBase.id
            == treino_base_id
        )
        .first()
    )

    # Treino não encontrado
    if not treino_base:

        raise HTTPException(
            status_code=404,
            detail="Treino base não encontrado."
        )

    # Verifica se o treino já foi utilizado
    agendamento = (
        db.query(
            models.TreinoAgendado
        )
        .filter(
            models.TreinoAgendado.treino_base_id
            == treino_base_id
        )
        .first()
    )

    # Não permite excluir um treino já utilizado
    if agendamento:

        raise HTTPException(
            status_code=400,
            detail=(
                "Este treino base já foi utilizado "
                "em um ou mais agendamentos e não "
                "pode ser excluído."
            )
        )

    # Exclui o treino base
    db.delete(
        treino_base
    )

    db.commit()

    return {
        "mensagem":
            "Treino base excluído com sucesso."
    }

# ============================================================
# TREINO EM MASSA
# ============================================================

@app.post("/api/treinos/em-massa")
def enviar_treino_em_massa(

    dados:
        schemas.TreinoEmMassaCreate,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    # Procura treino base
    treino_base = (
        db.query(models.TreinoBase)
        .filter(
            models.TreinoBase.id
            == dados.treino_base_id
        )
        .first()
    )

    if not treino_base:

        raise HTTPException(
            status_code=404,
            detail=
                "Treino base não encontrado."
        )

    # Busca alunos
    alunos = (
        db.query(models.Aluno)
        .all()
    )

    if not alunos:

        return {

            "mensagem":
                "Nenhum aluno cadastrado "
                "para receber o treino.",

            "total_enviados":
                0
        }

    # Cria treino para cada aluno
    for aluno in alunos:

        db.add(
            models.TreinoAgendado(

                aluno_id=
                    aluno.id,

                treino_base_id=
                    treino_base.id,

                titulo=
                    treino_base.titulo,

                modalidade=
                    treino_base.modalidade,

                descricao=
                    treino_base.descricao,

                ritmo_alvo=
                    treino_base.ritmo_alvo,

                data_planejada=
                    dados.data_planejada
            )
        )

    db.commit()

    return {

        "mensagem":
            f"Treino enviado com sucesso "
            f"para {len(alunos)} alunos!",

        "total_enviados":
            len(alunos)
    }

# ============================================================
# PLANEJAMENTO SEMANAL
# ============================================================
#
# O professor informa os treinos de segunda a sexta.
#
# O sistema identifica a modalidade do treino base.
#
# Depois procura todos os alunos daquela modalidade
# e cria um TreinoAgendado para cada um.
#
# ============================================================

@app.post("/api/treinos/semana")
def enviar_planejamento_semanal(

    dados: list[schemas.TreinoDiaSemana],

    data_segunda: str,

    db: Session =
        Depends(get_db),

    professor: models.Usuario =
        Depends(require_professor)

):

    # --------------------------------------------------------
    # IMPORTAR DATE
    # --------------------------------------------------------

    from datetime import datetime, timedelta


    # --------------------------------------------------------
    # CONVERTER A SEGUNDA-FEIRA
    # --------------------------------------------------------

    try:

        segunda = datetime.strptime(
            data_segunda,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        raise HTTPException(

            status_code=400,

            detail=
                "Data da segunda-feira inválida."
        )


    # --------------------------------------------------------
    # VERIFICAR SE É SEGUNDA
    # --------------------------------------------------------

    if segunda.weekday() != 0:

        raise HTTPException(

            status_code=400,

            detail=
                "A data escolhida deve ser uma segunda-feira."
        )


    total_enviados = 0


    # --------------------------------------------------------
    # PROCESSAR CADA DIA
    # --------------------------------------------------------

    for item in dados:

        # Verifica dia
        if item.dia < 0 or item.dia > 4:

            raise HTTPException(

                status_code=400,

                detail=
                    "O dia deve estar entre 0 e 4 (segunda a sexta)."
            )


        # ----------------------------------------------------
        # BUSCAR TREINO BASE
        # ----------------------------------------------------

        treino_base = (

            db.query(
                models.TreinoBase
            )

            .filter(

                models.TreinoBase.id
                == item.treino_base_id

            )

            .first()
        )


        if not treino_base:

            raise HTTPException(

                status_code=404,

                detail=
                    f"Treino base {item.treino_base_id} "
                    f"não encontrado."
            )


        # ----------------------------------------------------
        # DATA DO TREINO
        # ----------------------------------------------------

        data_treino = (
            segunda
            + timedelta(
                days=item.dia
            )
        )


        # ----------------------------------------------------
        # BUSCAR ALUNOS DA MODALIDADE
        # ----------------------------------------------------

        # O SQLite não remove acentos automaticamente.
        # Por isso normalizamos a modalidade em Python.
        todos_alunos = (
            db.query(models.Aluno)
            .all()
        )

        alunos = [
            aluno
            for aluno in todos_alunos
            if normalizar_modalidade(aluno.modalidade)
            == normalizar_modalidade(treino_base.modalidade)
        ]


        # ----------------------------------------------------
        # ENVIAR PARA CADA ALUNO
        # ----------------------------------------------------

        for aluno in alunos:

            # Evita duplicar exatamente o mesmo treino
            # para o mesmo aluno no mesmo dia.

            existente = (

                db.query(
                    models.TreinoAgendado
                )

                .filter(

                    models.TreinoAgendado.aluno_id
                    == aluno.id,

                    models.TreinoAgendado
                    .treino_base_id
                    == treino_base.id,

                    models.TreinoAgendado
                    .data_planejada
                    == data_treino.isoformat()

                )

                .first()
            )


            # Se já existir, não cria novamente
            if existente:

                continue


            # Cria treino
            novo_treino = (
            models.TreinoAgendado(

                aluno_id=
                    aluno.id,

                treino_base_id=
                    treino_base.id,

                titulo=
                    treino_base.titulo,

                modalidade=
                    treino_base.modalidade,

                descricao=
                    treino_base.descricao,

                ritmo_alvo=
                    treino_base.ritmo_alvo,

                data_planejada=
                    data_treino.isoformat()
            )
        )


            db.add(
                novo_treino
            )


            total_enviados += 1


    # --------------------------------------------------------
    # SALVAR
    # --------------------------------------------------------

    db.commit()


    return {

        "mensagem":
            "Planejamento semanal enviado com sucesso!",

        "total_enviados":
            total_enviados
    }


# ============================================================
# MEUS TREINOS
# ============================================================
#
# Essa rota é muito importante.
#
# O aluno NÃO envia seu aluno_id.
#
# O sistema pega:
#
# usuario.aluno_id
#
# diretamente da sessão.
#
# ============================================================

@app.get("/api/me/treinos")
def meus_treinos(

    db: Session =
    Depends(get_db),

    usuario: models.Usuario =
    Depends(require_aluno_com_email)
):

    # Busca somente os treinos
    # pertencentes ao aluno logado
    treinos = (

        db.query(
            models.TreinoAgendado
        )

        .filter(

            models.TreinoAgendado.aluno_id
            == usuario.aluno_id

        )

        .order_by(
            models.TreinoAgendado
            .data_planejada
            .asc()
        )

        .all()
    )

    return [

    {

        "id":
            t.id,

        "data_planejada":
            t.data_planejada,

        "concluido":
            t.concluido,

        "feedback_nota":
            t.feedback_nota,

        "feedback_dificuldade":
            t.feedback_dificuldade,

        "feedback_comentario":
            t.feedback_comentario,

        "treino": {

            "id":
                t.treino_base_id,

            "titulo":
                t.titulo,

            "modalidade":
                t.modalidade,

            "descricao":
                t.descricao,

            "ritmo_alvo":
                t.ritmo_alvo
            }
        }

    for t in treinos

]


# ============================================================
# LISTAR TREINOS DE UM ALUNO
# SOMENTE PROFESSOR
# ============================================================

@app.get("/api/alunos/{aluno_id}/treinos")
def listar_treinos_do_aluno(

    aluno_id: int,

    db: Session =
        Depends(get_db),

    professor: models.Usuario =
        Depends(require_professor)

):

    # --------------------------------------------------------
    # VERIFICAR SE O ALUNO EXISTE
    # --------------------------------------------------------

    aluno = (

        db.query(
            models.Aluno
        )

        .filter(
            models.Aluno.id == aluno_id
        )

        .first()
    )


    # Se o aluno não existir
    if not aluno:

        raise HTTPException(

            status_code=404,

            detail="Aluno não encontrado."
        )


    # --------------------------------------------------------
    # BUSCAR TREINOS DO ALUNO
    # --------------------------------------------------------

    treinos = (

        db.query(
            models.TreinoAgendado
        )

        .filter(

            models.TreinoAgendado.aluno_id
            == aluno_id

        )

        .order_by(

            models.TreinoAgendado
            .data_planejada
            .asc()

        )

        .all()
    )


    # --------------------------------------------------------
    # MONTAR RESPOSTA
    # --------------------------------------------------------

    resultado = []


    # Percorre cada treino
    for t in treinos:

        # ----------------------------------------------------
        # VERIFICAR SE O TREINO BASE EXISTE
        # ----------------------------------------------------

        if t.treino_base is None:

            resultado.append({

                "id":
                    t.id,

                "aluno_id":
                    t.aluno_id,

                "treino_base_id":
                    t.treino_base_id,

                "treino":
                    t.titulo,

                "modalidade":
                    t.modalidade,

                "descricao":
                    t.descricao,

                "ritmo_alvo":
                    t.ritmo_alvo,

                "data_planejada":
                    t.data_planejada,

                "concluido":
                    t.concluido,

                "feedback_nota":
                    t.feedback_nota,

                "feedback_dificuldade":
                    t.feedback_dificuldade,

                "feedback_comentario":
                    t.feedback_comentario
            })

            continue


        # ----------------------------------------------------
        # TREINO BASE EXISTE
        # ----------------------------------------------------

        resultado.append({

            "id":
                t.id,

            "aluno_id":
                t.aluno_id,

            "treino_base_id":
                t.treino_base_id,

            "treino":
                t.titulo,

            "modalidade":
                t.modalidade,

            "descricao":
                t.descricao,

            "ritmo_alvo":
                t.ritmo_alvo,

            "data_planejada":
                t.data_planejada,

            "concluido":
                t.concluido,

            # ------------------------------------------------
            # FEEDBACK DO ALUNO
            # ------------------------------------------------

            "feedback_nota":
                t.feedback_nota,

            "feedback_dificuldade":
                t.feedback_dificuldade,

            "feedback_comentario":
                t.feedback_comentario
        })


    # --------------------------------------------------------
    # RETORNAR RESULTADO
    # --------------------------------------------------------

    return resultado
# ============================================================
# CONCLUIR TREINO
# ============================================================

@app.patch("/api/treinos/{treino_id}/concluir")
def concluir_treino(

    treino_id: int,

    feedback:
        schemas.FeedbackTreinoCreate,

    db: Session =
        Depends(get_db),

    usuario: models.Usuario =
        Depends(require_aluno_com_email)

):

    treino = db.query(
        models.TreinoAgendado
    ).filter(
        models.TreinoAgendado.id == treino_id
    ).first()

    if not treino:
        raise HTTPException(
            status_code=404,
            detail="Treino não encontrado."
        )
# ============================================================
# SEGURANÇA
# ============================================================
#
# O aluno só pode concluir um treino
# que realmente pertence a ele.
#

    if treino.aluno_id != usuario.aluno_id:

        raise HTTPException(

        status_code=403,

        detail=
            "Você não pode concluir este treino."
    )

    if treino.concluido:
        raise HTTPException(
            status_code=400,
            detail="Este treino já foi concluído."
        )

    # Validação da nota
    if feedback.nota < 1 or feedback.nota > 5:
        raise HTTPException(
            status_code=400,
            detail="A nota deve estar entre 1 e 5."
        )

    # Salva feedback
    treino.feedback_nota = feedback.nota
    treino.feedback_dificuldade = feedback.dificuldade
    treino.feedback_comentario = feedback.comentario

    # Marca treino como concluído
    treino.concluido = True

    db.commit()
    db.refresh(treino)

    return {
        "mensagem": "Treino concluído e feedback salvo!",
        "treino": treino
    }

