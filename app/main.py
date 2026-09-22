# ============================================================
# MAIN.PY
# API principal do SpyTeam
# ============================================================

import json
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone

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

from .security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    LOGIN_RATE_WINDOW_SECONDS,
    RECOVERY_RATE_WINDOW_SECONDS,
    criar_token_csrf,
    validar_token_csrf,
    registrar_auditoria_login,
    verificar_rate_limit_login,
    registrar_e_verificar_rate_limit_recuperacao,
    registrar_acao_admin
)

# ============================================================
# MODALIDADES OFICIAIS DO SPY TEAM
# ============================================================

MODALIDADES_PERMITIDAS = (
    "Corrida",
    "Natação",
    "Musculação",
)


def _normalizar_modalidade_texto(valor: str) -> str:
    return (
        unicodedata.normalize("NFD", str(valor or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


MODALIDADES_POR_CHAVE = {
    _normalizar_modalidade_texto(nome): nome
    for nome in MODALIDADES_PERMITIDAS
}

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

        if "session_version" not in colunas:
            conexao.exec_driver_sql(
                "ALTER TABLE usuarios "
                "ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"
            )

        colunas_treinos = {
            linha[1]
            for linha in conexao.exec_driver_sql(
                "PRAGMA table_info(treinos_agendados)"
            ).fetchall()
        }

        if "concluido_em" not in colunas_treinos:
            conexao.exec_driver_sql(
                "ALTER TABLE treinos_agendados "
                "ADD COLUMN concluido_em INTEGER"
            )

        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS "
            "ix_treinos_agendados_concluido_em "
            "ON treinos_agendados(concluido_em)"
        )

        conexao.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            ux_usuarios_email_nocase
            ON usuarios(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email <> ''
            """
        )

        # Migração de modalidade única -> múltiplas modalidades.
        # A tabela aluno_modalidades é criada pelo SQLAlchemy antes daqui.
        alunos_legados = conexao.exec_driver_sql(
            "SELECT id, modalidade FROM alunos "
            "WHERE modalidade IS NOT NULL AND TRIM(modalidade) <> ''"
        ).fetchall()

        for aluno_id, modalidade_legada in alunos_legados:
            chave = _normalizar_modalidade_texto(modalidade_legada)
            modalidade_oficial = MODALIDADES_POR_CHAVE.get(chave)

            # Ciclismo/Triathlon e outros valores antigos não são migrados,
            # pois deixaram de fazer parte das modalidades oficiais.
            if not modalidade_oficial:
                continue

            conexao.exec_driver_sql(
                """
                INSERT OR IGNORE INTO aluno_modalidades
                    (aluno_id, modalidade)
                VALUES (?, ?)
                """,
                (aluno_id, modalidade_oficial)
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
# ERROS DE AUTENTICAÇÃO NAS PÁGINAS HTML
# ============================================================

@app.exception_handler(HTTPException)
async def tratar_http_exception(request: Request, exc: HTTPException):
    """
    Mantém os erros da API em JSON, mas trata as páginas HTML de forma
    amigável. Se alguém abrir uma página protegida sem sessão válida,
    redireciona para /login em vez de exibir o JSON de erro 401.

    Isso também cobre sessão expirada, cookie inválido e sessão invalidada
    após troca/redefinição de senha.
    """
    caminho = request.url.path
    eh_api = caminho.startswith("/api/")

    if exc.status_code == 401 and not eh_api:
        resposta = RedirectResponse(
            url="/login",
            status_code=303
        )

        # Remove um cookie antigo/inválido para que o próximo login comece
        # com uma sessão limpa.
        resposta.delete_cookie(
            key=COOKIE_NAME,
            path="/"
        )

        return resposta

    # APIs continuam respondendo exatamente como API: status + JSON.
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
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
# PROTEÇÃO CSRF EXPLÍCITA
# ============================================================

@app.middleware("http")
async def proteger_csrf(request: Request, call_next):
    """
    Aplica double-submit cookie a todas as rotas mutáveis da API.

    O navegador recebe um cookie aleatório e o JavaScript do próprio
    SpyTeam precisa reenviar o mesmo valor no cabeçalho X-CSRF-Token.
    Sites externos não conseguem ler esse cookie por causa da política
    de mesma origem do navegador.
    """
    token_cookie = request.cookies.get(CSRF_COOKIE_NAME)

    metodo_mutavel = request.method.upper() in {
        "POST", "PUT", "PATCH", "DELETE"
    }

    if metodo_mutavel and request.url.path.startswith("/api/"):
        token_header = request.headers.get(CSRF_HEADER_NAME)

        if not validar_token_csrf(token_cookie, token_header):
            resposta = JSONResponse(
                status_code=403,
                content={
                    "detail": (
                        "Validação de segurança expirada ou inválida. "
                        "Atualize a página e tente novamente."
                    )
                }
            )

            # Facilita a recuperação do cliente sem reduzir a proteção:
            # a próxima página carregada terá um token novo.
            if not token_cookie:
                resposta.set_cookie(
                    key=CSRF_COOKIE_NAME,
                    value=criar_token_csrf(),
                    httponly=False,
                    secure=COOKIE_SECURE,
                    samesite="lax",
                    max_age=60 * 60 * 24,
                    path="/"
                )

            return resposta

    resposta = await call_next(request)

    if not token_cookie:
        resposta.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=criar_token_csrf(),
            httponly=False,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=60 * 60 * 24,
            path="/"
        )

    return resposta


# ============================================================
# NORMALIZAR MODALIDADE
# ============================================================
def normalizar_modalidade(valor: str) -> str:
    """Compara modalidades sem diferença de maiúsculas/acentos."""
    return _normalizar_modalidade_texto(valor)


def canonicalizar_modalidade(valor: str) -> str:
    """Retorna o nome oficial da modalidade ou gera erro de validação."""
    chave = normalizar_modalidade(valor)
    modalidade = MODALIDADES_POR_CHAVE.get(chave)

    if not modalidade:
        raise ValueError(
            "Modalidade inválida. Use somente Corrida, Natação ou Musculação."
        )

    return modalidade


def validar_modalidades(valores) -> list[str]:
    """Valida, remove duplicidades e mantém a ordem oficial das modalidades."""
    if not valores:
        raise ValueError("Selecione pelo menos uma modalidade.")

    escolhidas = {
        canonicalizar_modalidade(valor)
        for valor in valores
    }

    return [
        modalidade
        for modalidade in MODALIDADES_PERMITIDAS
        if modalidade in escolhidas
    ]


def obter_modalidades_aluno(db: Session, aluno_id: int) -> list[str]:
    registros = (
        db.query(models.AlunoModalidade)
        .filter(models.AlunoModalidade.aluno_id == aluno_id)
        .all()
    )

    existentes = {registro.modalidade for registro in registros}

    return [
        modalidade
        for modalidade in MODALIDADES_PERMITIDAS
        if modalidade in existentes
    ]


def definir_modalidades_aluno(
    db: Session,
    aluno_db: models.Aluno,
    modalidades
) -> list[str]:
    modalidades_validas = validar_modalidades(modalidades)

    db.query(models.AlunoModalidade).filter(
        models.AlunoModalidade.aluno_id == aluno_db.id
    ).delete(synchronize_session=False)

    for modalidade in modalidades_validas:
        db.add(
            models.AlunoModalidade(
                aluno_id=aluno_db.id,
                modalidade=modalidade
            )
        )

    # Compatibilidade com versões antigas do banco/código.
    aluno_db.modalidade = modalidades_validas[0]

    return modalidades_validas


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

def obter_usuario_da_sessao(
    request: Request,
    db: Session
):
    """
    Retorna (usuario, payload) somente se a assinatura, expiração e
    versão da sessão forem válidas.

    A versão da sessão é incrementada quando a senha muda. Dessa forma,
    todos os navegadores que possuírem tokens antigos são desconectados.
    """
    payload = ler_token(
        request.cookies.get(COOKIE_NAME)
    )

    if not payload:
        return None, None

    try:
        usuario_id = int(payload["sub"])
        versao_token = int(payload.get("ver", 0))
    except (KeyError, TypeError, ValueError):
        return None, None

    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.id == usuario_id)
        .first()
    )

    if not usuario:
        return None, None

    versao_banco = int(usuario.session_version or 0)

    if versao_token != versao_banco:
        return None, None

    # Não confia apenas no tipo presente no token.
    if payload.get("tipo") != usuario.tipo:
        return None, None

    return usuario, payload


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    usuario, _ = obter_usuario_da_sessao(
        request,
        db
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail=(
                "Sessão inválida ou expirada. "
                "Entre novamente."
            )
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

    usuario, payload = obter_usuario_da_sessao(
        request,
        db
    )

    if not usuario or not payload:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    if usuario.tipo == "professor":
        return RedirectResponse(
            "/home",
            status_code=303
        )

    if aluno_sem_email(usuario):
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
    request: Request,
    db: Session = Depends(get_db)
):

    usuario, _ = obter_usuario_da_sessao(
        request,
        db
    )

    if usuario:
        if usuario.tipo == "professor":
            return RedirectResponse(
                "/home",
                status_code=303
            )

        if aluno_sem_email(usuario):
            return RedirectResponse(
                "/aluno/cadastrar-email",
                status_code=303
            )

        return RedirectResponse(
            "/aluno",
            status_code=303
        )

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
        name="Professor/home.html",
        context={
            "request": request,
            "professor_usuario": usuario.usuario
        }
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
# SEGURANÇA E AUDITORIA - PROFESSOR
# ============================================================

@app.get("/seguranca")
def pagina_seguranca(
    request: Request,
    professor: models.Usuario = Depends(require_professor)
):
    return templates.TemplateResponse(
        request=request,
        name="Professor/seguranca.html"
    )


@app.get("/api/auditoria/logins")
def listar_auditoria_logins(
    limite: int = 100,
    db: Session = Depends(get_db),
    professor: models.Usuario = Depends(require_professor)
):
    limite = max(1, min(int(limite), 500))

    registros = (
        db.query(models.AuditoriaLogin)
        .order_by(models.AuditoriaLogin.criado_em.desc())
        .limit(limite)
        .all()
    )

    return [
        {
            "id": item.id,
            "usuario_id": item.usuario_id,
            "usuario": item.usuario_informado,
            "sucesso": bool(item.sucesso),
            "motivo": item.motivo,
            "ip": item.ip,
            "user_agent": item.user_agent,
            "criado_em": item.criado_em
        }
        for item in registros
    ]


@app.get("/api/auditoria/administrativa")
def listar_auditoria_administrativa(
    limite: int = 100,
    db: Session = Depends(get_db),
    professor: models.Usuario = Depends(require_professor)
):
    limite = max(1, min(int(limite), 500))

    registros = (
        db.query(models.AuditoriaAdministrativa)
        .order_by(
            models.AuditoriaAdministrativa.criado_em.desc()
        )
        .limit(limite)
        .all()
    )

    resultado = []

    for item in registros:
        detalhes = None

        if item.dados_json:
            try:
                detalhes = json.loads(item.dados_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                detalhes = None

        resultado.append({
            "id": item.id,
            "professor_id": item.professor_id,
            "professor": item.professor_usuario,
            "acao": item.acao,
            "entidade": item.entidade,
            "entidade_id": item.entidade_id,
            "descricao": item.descricao,
            "detalhes": detalhes,
            "ip": item.ip,
            "user_agent": item.user_agent,
            "criado_em": item.criado_em
        })

    return resultado


# ============================================================
# DASHBOARD ANALÍTICO DO PROFESSOR
# ============================================================


def _data_planejada_segura(valor):
    """Converte YYYY-MM-DD / ISO para date sem quebrar registros antigos."""
    if not valor:
        return None

    try:
        return datetime.strptime(
            str(valor).split("T")[0],
            "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        return None


def _timestamp_data_referencia(valor_data):
    """Timestamp UTC ao meio-dia, usado só como fallback histórico."""
    data_ref = _data_planejada_segura(valor_data)

    if not data_ref:
        return None

    return int(
        datetime.combine(
            data_ref,
            datetime.min.time()
        ).replace(
            hour=12,
            tzinfo=timezone.utc
        ).timestamp()
    )


def _percentual(parte, total):
    if not total:
        return 0.0

    return round((parte / total) * 100, 1)


@app.get("/api/dashboard/professor")
def dashboard_professor(
    semanas: int = 4,
    db: Session = Depends(get_db),
    professor: models.Usuario = Depends(require_professor)
):
    """
    Resumo operacional do professor.

    Regras principais:
    - Taxa de conclusão: treinos planejados no período até hoje.
    - Aderência 30 dias: média da taxa individual de conclusão dos
      alunos que tiveram ao menos um treino devido nos últimos 30 dias.
    - Ativo: login bem-sucedido ou treino concluído nos últimos 7 dias.
    - Inativo: nenhuma dessas atividades nos últimos 7 dias.
    """

    semanas = max(1, min(int(semanas or 4), 12))

    hoje = date.today()
    agora_ts = int(time.time())
    inicio_periodo = hoje - timedelta(days=(semanas * 7) - 1)
    inicio_30 = hoje - timedelta(days=29)
    limite_atividade_ts = agora_ts - (7 * 24 * 60 * 60)

    alunos = (
        db.query(models.Aluno)
        .order_by(models.Aluno.nome.asc())
        .all()
    )

    usuarios_alunos = (
        db.query(models.Usuario)
        .filter(models.Usuario.tipo == "aluno")
        .all()
    )

    treinos = db.query(models.TreinoAgendado).all()

    usuario_por_id = {
        usuario.id: usuario
        for usuario in usuarios_alunos
    }

    usuario_por_aluno = {
        usuario.aluno_id: usuario
        for usuario in usuarios_alunos
        if usuario.aluno_id
    }

    nome_aluno = {
        aluno.id: aluno.nome
        for aluno in alunos
    }

    modalidades_por_aluno = {
        aluno.id: []
        for aluno in alunos
    }

    for vinculo in db.query(models.AlunoModalidade).all():
        if vinculo.aluno_id in modalidades_por_aluno:
            modalidades_por_aluno[vinculo.aluno_id].append(
                vinculo.modalidade
            )

    # Compatibilidade com bancos migrados onde a relação ainda não
    # tenha sido preenchida por algum registro antigo.
    for aluno in alunos:
        if not modalidades_por_aluno[aluno.id] and aluno.modalidade:
            try:
                modalidade = canonicalizar_modalidade(aluno.modalidade)
                modalidades_por_aluno[aluno.id] = [modalidade]
            except ValueError:
                pass

    data_por_treino = {
        treino.id: _data_planejada_segura(treino.data_planejada)
        for treino in treinos
    }

    treinos_periodo = [
        treino
        for treino in treinos
        if (
            data_por_treino[treino.id]
            and inicio_periodo <= data_por_treino[treino.id] <= hoje
        )
    ]

    treinos_30 = [
        treino
        for treino in treinos
        if (
            data_por_treino[treino.id]
            and inicio_30 <= data_por_treino[treino.id] <= hoje
        )
    ]

    concluidos_periodo = [
        treino
        for treino in treinos_periodo
        if treino.concluido
    ]

    taxa_conclusao = _percentual(
        len(concluidos_periodo),
        len(treinos_periodo)
    )

    # Média da aderência individual, evitando que alunos com grande
    # quantidade de treinos pesem mais que os demais.
    taxas_individuais = []

    for aluno in alunos:
        devidos = [
            treino
            for treino in treinos_30
            if treino.aluno_id == aluno.id
        ]

        if not devidos:
            continue

        concluidos = sum(
            1 for treino in devidos
            if treino.concluido
        )

        taxas_individuais.append(
            _percentual(concluidos, len(devidos))
        )

    aderencia_30 = round(
        sum(taxas_individuais) / len(taxas_individuais),
        1
    ) if taxas_individuais else 0.0

    # Última atividade = login bem-sucedido OU conclusão de treino.
    ultima_atividade = {
        aluno.id: None
        for aluno in alunos
    }

    logins = (
        db.query(models.AuditoriaLogin)
        .filter(models.AuditoriaLogin.sucesso.is_(True))
        .all()
    )

    for login in logins:
        usuario = usuario_por_id.get(login.usuario_id)

        if not usuario or not usuario.aluno_id:
            continue

        atual = ultima_atividade.get(usuario.aluno_id)

        if atual is None or login.criado_em > atual:
            ultima_atividade[usuario.aluno_id] = login.criado_em

    for treino in treinos:
        if not treino.concluido:
            continue

        timestamp = (
            treino.concluido_em
            or _timestamp_data_referencia(treino.data_planejada)
        )

        if timestamp is None:
            continue

        atual = ultima_atividade.get(treino.aluno_id)

        if atual is None or timestamp > atual:
            ultima_atividade[treino.aluno_id] = timestamp

    alunos_ativos = []
    alunos_inativos = []

    for aluno in alunos:
        timestamp = ultima_atividade.get(aluno.id)

        if timestamp is not None and timestamp >= limite_atividade_ts:
            alunos_ativos.append(aluno)
        else:
            alunos_inativos.append(aluno)

    alunos_atencao = []

    for aluno in alunos_inativos:
        timestamp = ultima_atividade.get(aluno.id)
        dias = None

        if timestamp is not None:
            dias = max(
                0,
                int((agora_ts - timestamp) // (24 * 60 * 60))
            )

        alunos_atencao.append({
            "id": aluno.id,
            "nome": aluno.nome,
            "nivel": aluno.nivel,
            "modalidades": modalidades_por_aluno.get(aluno.id, []),
            "dias_sem_atividade": dias,
            "ultima_atividade": timestamp
        })

    alunos_atencao.sort(
        key=lambda item: (
            item["dias_sem_atividade"] is None,
            item["dias_sem_atividade"] or 0
        ),
        reverse=True
    )

    # Frequência semanal: número de treinos efetivamente concluídos.
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    primeira_segunda = segunda_atual - timedelta(
        weeks=semanas - 1
    )

    frequencia_semanal = []

    for indice in range(semanas):
        inicio_semana = primeira_segunda + timedelta(weeks=indice)
        fim_semana = inicio_semana + timedelta(days=6)
        total = 0

        for treino in treinos:
            if not treino.concluido:
                continue

            data_conclusao = None

            if treino.concluido_em:
                data_conclusao = datetime.fromtimestamp(
                    treino.concluido_em,
                    tz=timezone.utc
                ).date()
            else:
                data_conclusao = data_por_treino.get(treino.id)

            if (
                data_conclusao
                and inicio_semana <= data_conclusao <= fim_semana
            ):
                total += 1

        frequencia_semanal.append({
            "indice": indice + 1,
            "rotulo": f"Sem {indice + 1}",
            "inicio": inicio_semana.isoformat(),
            "fim": fim_semana.isoformat(),
            "concluidos": total
        })

    # Distribuição dos treinos agendados por modalidade no período.
    modalidades = []
    total_modalidades = len(treinos_periodo)

    for modalidade in MODALIDADES_PERMITIDAS:
        itens = [
            treino
            for treino in treinos_periodo
            if _normalizar_modalidade_texto(treino.modalidade)
            == _normalizar_modalidade_texto(modalidade)
        ]

        quantidade_alunos = sum(
            1
            for lista in modalidades_por_aluno.values()
            if modalidade in lista
        )

        modalidades.append({
            "nome": modalidade,
            "treinos": len(itens),
            "concluidos": sum(1 for item in itens if item.concluido),
            "percentual": _percentual(len(itens), total_modalidades),
            "alunos": quantidade_alunos
        })

    # Avaliações deixadas pelos alunos no período selecionado.
    avaliados = [
        treino
        for treino in treinos_periodo
        if treino.feedback_nota is not None
    ]

    total_avaliacoes = len(avaliados)
    media_avaliacao = round(
        sum(treino.feedback_nota for treino in avaliados)
        / total_avaliacoes,
        1
    ) if total_avaliacoes else 0.0

    distribuicao_avaliacao = {}

    for nota in range(5, 0, -1):
        quantidade = sum(
            1
            for treino in avaliados
            if treino.feedback_nota == nota
        )

        distribuicao_avaliacao[str(nota)] = {
            "quantidade": quantidade,
            "percentual": _percentual(
                quantidade,
                total_avaliacoes
            )
        }

    # Atividade recente combina ações administrativas e conclusões.
    atividades = []

    for item in (
        db.query(models.AuditoriaAdministrativa)
        .order_by(models.AuditoriaAdministrativa.criado_em.desc())
        .limit(20)
        .all()
    ):
        atividades.append({
            "tipo": "administrativa",
            "acao": item.acao,
            "descricao": item.descricao,
            "timestamp": item.criado_em
        })

    for treino in treinos:
        if not treino.concluido:
            continue

        timestamp = (
            treino.concluido_em
            or _timestamp_data_referencia(treino.data_planejada)
        )

        if timestamp is None:
            continue

        aluno_nome = nome_aluno.get(
            treino.aluno_id,
            "Aluno"
        )

        atividades.append({
            "tipo": "treino_concluido",
            "acao": "concluir_treino",
            "descricao": (
                f"{aluno_nome} concluiu {treino.titulo} "
                f"({treino.modalidade})."
            ),
            "timestamp": timestamp,
            "aluno_id": treino.aluno_id,
            "treino_id": treino.id
        })

    atividades.sort(
        key=lambda item: item["timestamp"],
        reverse=True
    )

    return {
        "periodo": {
            "semanas": semanas,
            "inicio": inicio_periodo.isoformat(),
            "fim": hoje.isoformat()
        },
        "resumo": {
            "total_alunos": len(alunos),
            "alunos_ativos": len(alunos_ativos),
            "taxa_conclusao": taxa_conclusao,
            "aderencia_30_dias": aderencia_30,
            "alunos_inativos": len(alunos_inativos),
            "avaliacao_media": media_avaliacao
        },
        "frequencia_semanal": frequencia_semanal,
        "modalidades": modalidades,
        "alunos_atencao": alunos_atencao[:6],
        "avaliacoes": {
            "media": media_avaliacao,
            "total": total_avaliacoes,
            "distribuicao": distribuicao_avaliacao
        },
        "atividade_recente": atividades[:8]
    }


# ============================================================
# LOGIN
# ============================================================

@app.post("/api/login")
def login(
    request: Request,
    dados: schemas.Login,
    db: Session = Depends(get_db)
):
    # Chave usada para rate limit/auditoria. Nunca armazenamos a senha.
    usuario_informado = str(
        dados.usuario or ""
    ).strip().casefold()[:100]

    # Rate limit é verificado antes do hash de senha, reduzindo também
    # consumo de CPU em tentativas automatizadas.
    if verificar_rate_limit_login(
        db,
        request,
        usuario_informado
    ):
        registrar_auditoria_login(
            db=db,
            request=request,
            usuario_informado=usuario_informado,
            sucesso=False,
            motivo="rate_limit"
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "Muitas tentativas de login. "
                "Aguarde alguns minutos e tente novamente."
            ),
            headers={
                "Retry-After": str(LOGIN_RATE_WINDOW_SECONDS)
            }
        )

    # Usuário é case-insensitive e não aceita espaços internos.
    try:
        usuario_normalizado = normalizar_usuario(
            dados.usuario
        )
    except ValueError:
        registrar_auditoria_login(
            db=db,
            request=request,
            usuario_informado=usuario_informado,
            sucesso=False,
            motivo="usuario_invalido"
        )

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

    # Usuário inexistente ou senha errada.
    if (
        not usuario
        or not verificar_senha(
            dados.senha,
            usuario.senha_hash
        )
    ):
        registrar_auditoria_login(
            db=db,
            request=request,
            usuario_informado=usuario_normalizado,
            sucesso=False,
            motivo="credenciais_invalidas",
            usuario_id=(
                usuario.id if usuario else None
            )
        )

        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos."
        )

    registrar_auditoria_login(
        db=db,
        request=request,
        usuario_informado=usuario_normalizado,
        sucesso=True,
        motivo="sucesso",
        usuario_id=usuario.id
    )

    token = criar_token(
        usuario.id,
        usuario.tipo,
        usuario.session_version or 0
    )

    if usuario.tipo == "professor":
        destino = "/home"
    else:
        destino = (
            "/aluno/cadastrar-email"
            if aluno_sem_email(usuario)
            else "/aluno"
        )

    resposta = JSONResponse(
        {
            "mensagem": "Login realizado com sucesso!",
            "tipo": usuario.tipo,
            "usuario": usuario.usuario,
            "redirect": destino
        }
    )

    resposta.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=60 * 60 * 24,
        path="/"
    )

    # Rotaciona o CSRF depois que a autenticação muda de estado.
    resposta.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=criar_token_csrf(),
        httponly=False,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=60 * 60 * 24,
        path="/"
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

    # Rotaciona o token CSRF após o logout.
    resposta.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=criar_token_csrf(),
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/"
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

                "modalidades":
                    obter_modalidades_aluno(db, aluno_db.id),

                # Mantido para compatibilidade com telas antigas.
                "modalidade":
                    " • ".join(
                        obter_modalidades_aluno(db, aluno_db.id)
                    )
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
    request: Request,
    dados: schemas.SolicitarRecuperacaoSenha,
    db: Session = Depends(get_db)
):
    # O rate limit é aplicado antes de descobrir se o e-mail existe.
    # Assim, endereços inexistentes também consomem a cota e a resposta
    # não revela quais contas estão cadastradas.
    identificador_rate = str(
        dados.email or ""
    ).strip().casefold()

    if registrar_e_verificar_rate_limit_recuperacao(
        db,
        request,
        identificador_rate
    ):
        raise HTTPException(
            status_code=429,
            detail=(
                "Muitas solicitações de recuperação. "
                "Aguarde alguns minutos e tente novamente."
            ),
            headers={
                "Retry-After": str(
                    RECOVERY_RATE_WINDOW_SECONDS
                )
            }
        )

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

    # Proteção adicional por conta para não disparar vários e-mails
    # consecutivos mesmo dentro dos limites globais.
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

    # Invalida imediatamente todas as sessões existentes.
    usuario.session_version = int(
        usuario.session_version or 0
    ) + 1

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

    resposta = JSONResponse({
        "mensagem": "Senha redefinida com sucesso.",
        "redirect": "/login"
    })

    # Mesmo que o usuário tenha aberto o link em um navegador onde
    # estava logado, a sessão local também é removida.
    resposta.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    resposta.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=criar_token_csrf(),
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/"
    )

    return resposta


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

    # Invalida esta sessão e qualquer outra sessão aberta da conta.
    usuario_db.session_version = int(
        usuario_db.session_version or 0
    ) + 1

    db.commit()

    resposta = JSONResponse({
        "mensagem": (
            "Senha alterada com sucesso. "
            "Entre novamente para continuar."
        ),
        "redirect": "/login"
    })

    resposta.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    resposta.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=criar_token_csrf(),
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/"
    )

    return resposta


# ============================================================
# CRIAR ALUNO
# ============================================================

@app.post("/api/alunos")
def criar_aluno(

    request: Request,

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

    # Valida as modalidades antes de criar qualquer registro.
    try:
        modalidades_validas = validar_modalidades(
            aluno.modalidades
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    # Cria aluno. A coluna modalidade guarda somente a primeira
    # opção por compatibilidade; a tabela aluno_modalidades é a fonte
    # oficial para múltiplas modalidades.
    novo_aluno = models.Aluno(

        nome=aluno.nome,

        nivel=aluno.nivel,

        modalidade=modalidades_validas[0]
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

    definir_modalidades_aluno(
        db,
        novo_aluno,
        modalidades_validas
    )

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="criar_aluno",
        entidade="aluno",
        entidade_id=novo_aluno.id,
        descricao=f"Aluno {novo_aluno.nome} cadastrado.",
        detalhes={
            "nome": novo_aluno.nome,
            "nivel": novo_aluno.nivel,
            "modalidades": modalidades_validas,
            "usuario": usuario_normalizado
        }
    )

    # Salva aluno, conta e histórico na mesma transação.
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

        "modalidades":
            modalidades_validas,

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

        modalidades = obter_modalidades_aluno(
            db,
            aluno.id
        )

        resultado.append({

            "id":
                aluno.id,

            "nome":
                aluno.nome,

            "nivel":
                aluno.nivel,

            "modalidades":
                modalidades,

            "modalidade":
                " • ".join(modalidades),

            "usuario":
                usuario.usuario
                if usuario
                else None
        })

    return resultado


# ============================================================
# ATUALIZAR MODALIDADES DO ALUNO
# SOMENTE PROFESSOR
# ============================================================

@app.patch("/api/alunos/{aluno_id}/modalidades")
def atualizar_modalidades_aluno(
    aluno_id: int,
    dados: schemas.AlunoModalidadesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    professor: models.Usuario = Depends(require_professor)
):
    aluno_db = (
        db.query(models.Aluno)
        .filter(models.Aluno.id == aluno_id)
        .first()
    )

    if not aluno_db:
        raise HTTPException(
            status_code=404,
            detail="Aluno não encontrado."
        )

    antes = obter_modalidades_aluno(db, aluno_id)

    try:
        depois = definir_modalidades_aluno(
            db,
            aluno_db,
            dados.modalidades
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="atualizar_modalidades_aluno",
        entidade="aluno",
        entidade_id=aluno_id,
        descricao=f"Modalidades de {aluno_db.nome} atualizadas.",
        detalhes={
            "antes": antes,
            "depois": depois
        }
    )

    db.commit()

    return {
        "mensagem": "Modalidades atualizadas com sucesso.",
        "id": aluno_id,
        "modalidades": depois,
        "modalidade": " • ".join(depois)
    }


# ============================================================
# EXCLUIR ALUNO
# SOMENTE PROFESSOR
# ============================================================

@app.delete("/api/alunos/{aluno_id}")
def excluir_aluno(
    aluno_id: int,

    request: Request,

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

    usuario_aluno = (
        db.query(models.Usuario)
        .filter(models.Usuario.aluno_id == aluno_id)
        .first()
    )

    dados_auditoria_aluno = {
        "nome": aluno.nome,
        "nivel": aluno.nivel,
        "modalidades": obter_modalidades_aluno(db, aluno.id),
        "usuario": (
            usuario_aluno.usuario
            if usuario_aluno else None
        )
    }

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
    # REMOVER VÍNCULOS DE MODALIDADE
    # --------------------------------------------------------

    db.query(models.AlunoModalidade).filter(
        models.AlunoModalidade.aluno_id == aluno_id
    ).delete(synchronize_session=False)

    # --------------------------------------------------------
    # REMOVER O ALUNO
    # --------------------------------------------------------

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="excluir_aluno",
        entidade="aluno",
        entidade_id=aluno_id,
        descricao=f"Aluno {aluno.nome} excluído.",
        detalhes=dados_auditoria_aluno
    )

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

    request: Request,

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
    db.flush()

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="agendar_treino",
        entidade="treino_agendado",
        entidade_id=novo_treino.id,
        descricao=(
            f"Treino {treino_base.titulo} agendado "
            f"para {aluno.nome}."
        ),
        detalhes={
            "aluno_id": aluno.id,
            "aluno": aluno.nome,
            "treino_base_id": treino_base.id,
            "treino": treino_base.titulo,
            "modalidade": treino_base.modalidade,
            "data_planejada": treino.data_planejada
        }
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

        .filter(
            models.TreinoBase.modalidade.in_(MODALIDADES_PERMITIDAS)
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

    request: Request,

    treino: schemas.TreinoBaseCreate,

    db: Session =
    Depends(get_db),

    professor: models.Usuario =
    Depends(require_professor)
):

    try:
        modalidade_valida = canonicalizar_modalidade(
            treino.modalidade
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    novo_treino = models.TreinoBase(

        titulo=
            treino.titulo,

        modalidade=
            modalidade_valida,

        descricao=
            treino.descricao,

        ritmo_alvo=
            treino.ritmo_alvo
    )

    db.add(
        novo_treino
    )
    db.flush()

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="criar_treino_base",
        entidade="treino_base",
        entidade_id=novo_treino.id,
        descricao=f"Treino base {novo_treino.titulo} criado.",
        detalhes={
            "titulo": novo_treino.titulo,
            "modalidade": novo_treino.modalidade,
            "descricao": novo_treino.descricao,
            "ritmo_alvo": novo_treino.ritmo_alvo
        }
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

    request: Request,

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

    antes = {
        "titulo": treino_base.titulo,
        "modalidade": treino_base.modalidade,
        "descricao": treino_base.descricao,
        "ritmo_alvo": treino_base.ritmo_alvo
    }

    try:
        modalidade_valida = canonicalizar_modalidade(
            dados.modalidade
        )
    except ValueError as erro:
        raise HTTPException(
            status_code=400,
            detail=str(erro)
        )

    # Atualiza os dados do treino base
    treino_base.titulo = dados.titulo

    treino_base.modalidade = modalidade_valida

    treino_base.descricao = dados.descricao

    treino_base.ritmo_alvo = dados.ritmo_alvo

    depois = {
        "titulo": treino_base.titulo,
        "modalidade": treino_base.modalidade,
        "descricao": treino_base.descricao,
        "ritmo_alvo": treino_base.ritmo_alvo
    }

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="editar_treino_base",
        entidade="treino_base",
        entidade_id=treino_base.id,
        descricao=f"Treino base {treino_base.titulo} editado.",
        detalhes={
            "antes": antes,
            "depois": depois
        }
    )

    # Salva alteração e histórico juntos.
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

    request: Request,

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

    dados_excluidos = {
        "titulo": treino_base.titulo,
        "modalidade": treino_base.modalidade,
        "descricao": treino_base.descricao,
        "ritmo_alvo": treino_base.ritmo_alvo
    }

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="excluir_treino_base",
        entidade="treino_base",
        entidade_id=treino_base.id,
        descricao=f"Treino base {treino_base.titulo} excluído.",
        detalhes=dados_excluidos
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

    request: Request,

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

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="enviar_treino_em_massa",
        entidade="treino_agendado",
        descricao=(
            f"Treino {treino_base.titulo} enviado "
            f"para {len(alunos)} alunos."
        ),
        detalhes={
            "treino_base_id": treino_base.id,
            "treino": treino_base.titulo,
            "modalidade": treino_base.modalidade,
            "data_planejada": dados.data_planejada,
            "total_enviados": len(alunos)
        }
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

    request: Request,

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

        try:
            modalidade_treino = canonicalizar_modalidade(
                treino_base.modalidade
            )
        except ValueError as erro:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"O treino base '{treino_base.titulo}' possui "
                    f"uma modalidade que não é mais aceita: {erro}"
                )
            )

        # Um aluno pode estar em mais de uma modalidade.
        # Basta existir um vínculo na tabela aluno_modalidades para
        # receber o treino daquela modalidade.
        alunos = (
            db.query(models.Aluno)
            .join(
                models.AlunoModalidade,
                models.AlunoModalidade.aluno_id == models.Aluno.id
            )
            .filter(
                models.AlunoModalidade.modalidade == modalidade_treino
            )
            .all()
        )


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
    # SALVAR + AUDITAR
    # --------------------------------------------------------

    registrar_acao_admin(
        db=db,
        request=request,
        professor=professor,
        acao="enviar_planejamento_semanal",
        entidade="planejamento_semanal",
        descricao=(
            f"Planejamento da semana {data_segunda} enviado "
            f"com {total_enviados} agendamentos."
        ),
        detalhes={
            "data_segunda": data_segunda,
            "total_enviados": total_enviados,
            "itens": [
                {
                    "dia": item.dia,
                    "treino_base_id": item.treino_base_id
                }
                for item in dados
            ]
        }
    )

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

        "concluido_em":
            t.concluido_em,

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

    # Marca treino como concluído e registra o momento real da conclusão.
    treino.concluido = True
    treino.concluido_em = int(time.time())

    db.commit()
    db.refresh(treino)

    return {
        "mensagem": "Treino concluído e feedback salvo!",
        "treino": treino
    }

