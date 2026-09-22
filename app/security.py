# ============================================================
# SECURITY.PY
# Proteções adicionais de segurança do SpyTeam
# ============================================================

import hashlib
import hmac
import json
import os
import secrets
import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models


# ============================================================
# CONFIGURAÇÃO
# ============================================================

CSRF_COOKIE_NAME = "spyteam_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def _env_int(nome: str, padrao: int, minimo: int = 1) -> int:
    """Lê um inteiro do ambiente sem deixar configuração inválida quebrar a aplicação."""
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except (TypeError, ValueError):
        return padrao

    return max(minimo, valor)


# Login: janela de 15 minutos por padrão.
LOGIN_RATE_WINDOW_SECONDS = _env_int(
    "LOGIN_RATE_WINDOW_SECONDS",
    15 * 60
)
LOGIN_RATE_MAX_IP = _env_int(
    "LOGIN_RATE_MAX_IP",
    30
)
LOGIN_RATE_MAX_USER_IP = _env_int(
    "LOGIN_RATE_MAX_USER_IP",
    5
)
LOGIN_RATE_MAX_USER = _env_int(
    "LOGIN_RATE_MAX_USER",
    20
)

# Recuperação: limites por e-mail, IP e aplicação inteira.
RECOVERY_RATE_WINDOW_SECONDS = _env_int(
    "RECOVERY_RATE_WINDOW_SECONDS",
    15 * 60
)
RECOVERY_RATE_MAX_IP = _env_int(
    "RECOVERY_RATE_MAX_IP",
    10
)
RECOVERY_RATE_MAX_IDENTIFIER = _env_int(
    "RECOVERY_RATE_MAX_IDENTIFIER",
    3
)
RECOVERY_RATE_MAX_GLOBAL = _env_int(
    "RECOVERY_RATE_MAX_GLOBAL",
    100
)


# ============================================================
# CSRF
# ============================================================

def criar_token_csrf() -> str:
    """Token aleatório usado no padrão double-submit cookie."""
    return secrets.token_urlsafe(32)


def validar_token_csrf(
    token_cookie: str | None,
    token_header: str | None
) -> bool:
    """Compara token do cookie com token enviado no cabeçalho."""
    if not token_cookie or not token_header:
        return False

    try:
        return hmac.compare_digest(
            str(token_cookie),
            str(token_header)
        )
    except TypeError:
        return False


# ============================================================
# DADOS DA REQUISIÇÃO
# ============================================================

def obter_ip_cliente(request) -> str:
    """
    O Uvicorn do projeto é iniciado com --proxy-headers no Railway,
    então request.client.host recebe o IP encaminhado pelo proxy.
    """
    try:
        if request.client and request.client.host:
            return str(request.client.host)[:64]
    except Exception:
        pass

    return "desconhecido"


def obter_user_agent(request) -> str:
    return str(
        request.headers.get("user-agent", "")
    )[:500]


def _hash_identificador(valor: str) -> str:
    return hashlib.sha256(
        str(valor or "")
        .strip()
        .casefold()
        .encode("utf-8")
    ).hexdigest()


# ============================================================
# AUDITORIA DE LOGIN
# ============================================================

def registrar_auditoria_login(
    db: Session,
    request,
    usuario_informado: str,
    sucesso: bool,
    motivo: str,
    usuario_id: int | None = None
) -> None:
    """Registra tentativa de login sem armazenar senha."""
    registro = models.AuditoriaLogin(
        usuario_id=usuario_id,
        usuario_informado=str(
            usuario_informado or ""
        )[:100],
        sucesso=bool(sucesso),
        motivo=str(motivo or "")[:80],
        ip=obter_ip_cliente(request),
        user_agent=obter_user_agent(request),
        criado_em=int(time.time())
    )

    db.add(registro)
    db.commit()


def verificar_rate_limit_login(
    db: Session,
    request,
    usuario_informado: str
) -> bool:
    """
    Protege contra força bruta combinando três limites:
    - falhas do mesmo IP;
    - falhas do mesmo IP + usuário;
    - falhas contra o mesmo usuário.

    Tentativas já bloqueadas não contam novamente, para não alongar
    indefinidamente o bloqueio apenas porque alguém continua insistindo.
    """
    agora = int(time.time())
    inicio = agora - LOGIN_RATE_WINDOW_SECONDS
    ip = obter_ip_cliente(request)
    usuario = str(usuario_informado or "")[:100]

    base = (
        db.query(models.AuditoriaLogin)
        .filter(
            models.AuditoriaLogin.criado_em >= inicio,
            models.AuditoriaLogin.sucesso == False,
            models.AuditoriaLogin.motivo != "rate_limit"
        )
    )

    falhas_ip = (
        base.filter(
            models.AuditoriaLogin.ip == ip
        ).count()
    )

    falhas_usuario_ip = (
        base.filter(
            models.AuditoriaLogin.ip == ip,
            models.AuditoriaLogin.usuario_informado == usuario
        ).count()
    )

    # Usuário vazio/claramente inválido não precisa de bloqueio global
    # por identificador; o limite por IP continua protegendo a rota.
    falhas_usuario = 0
    if usuario:
        falhas_usuario = (
            base.filter(
                models.AuditoriaLogin.usuario_informado == usuario
            ).count()
        )

    return any((
        falhas_ip >= LOGIN_RATE_MAX_IP,
        falhas_usuario_ip >= LOGIN_RATE_MAX_USER_IP,
        bool(usuario) and falhas_usuario >= LOGIN_RATE_MAX_USER
    ))


# ============================================================
# RATE LIMIT DA RECUPERAÇÃO DE SENHA
# ============================================================

def registrar_e_verificar_rate_limit_recuperacao(
    db: Session,
    request,
    identificador: str
) -> bool:
    """
    Retorna True quando a solicitação deve ser bloqueada.

    A proteção considera:
    - o mesmo IP;
    - o mesmo e-mail/identificador (armazenado apenas como SHA-256);
    - o total global de solicitações na janela.

    Isso também conta endereços inexistentes/errados, evitando que a
    proteção seja contornada usando e-mails aleatórios.
    """
    agora = int(time.time())
    inicio = agora - RECOVERY_RATE_WINDOW_SECONDS
    ip = obter_ip_cliente(request)
    chave_hash = _hash_identificador(identificador)

    # A tabela de rate limit é operacional. Eventos antigos não precisam
    # crescer para sempre; mantemos 24 horas para diagnóstico.
    db.query(models.EventoRateLimit).filter(
        models.EventoRateLimit.criado_em < agora - 24 * 60 * 60
    ).delete(synchronize_session=False)

    base = (
        db.query(models.EventoRateLimit)
        .filter(
            models.EventoRateLimit.tipo == "recuperacao_senha",
            models.EventoRateLimit.criado_em >= inicio,
            models.EventoRateLimit.bloqueado == False
        )
    )

    total_global = base.count()
    total_ip = base.filter(
        models.EventoRateLimit.ip == ip
    ).count()
    total_identificador = base.filter(
        models.EventoRateLimit.chave_hash == chave_hash
    ).count()

    bloqueado = any((
        total_global >= RECOVERY_RATE_MAX_GLOBAL,
        total_ip >= RECOVERY_RATE_MAX_IP,
        total_identificador >= RECOVERY_RATE_MAX_IDENTIFIER
    ))

    db.add(
        models.EventoRateLimit(
            tipo="recuperacao_senha",
            chave_hash=chave_hash,
            ip=ip,
            bloqueado=bloqueado,
            criado_em=agora
        )
    )
    db.commit()

    return bloqueado


# ============================================================
# HISTÓRICO ADMINISTRATIVO
# ============================================================

def registrar_acao_admin(
    db: Session,
    request,
    professor: models.Usuario,
    acao: str,
    entidade: str,
    descricao: str,
    entidade_id: int | None = None,
    detalhes: dict | list | None = None
) -> None:
    """
    Adiciona uma alteração administrativa à mesma transação da ação.
    O chamador é responsável pelo db.commit().
    """
    dados_json = None

    if detalhes is not None:
        dados_json = json.dumps(
            detalhes,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str
        )

    db.add(
        models.AuditoriaAdministrativa(
            professor_id=professor.id,
            professor_usuario=str(
                professor.usuario or ""
            )[:100],
            acao=str(acao or "")[:80],
            entidade=str(entidade or "")[:80],
            entidade_id=entidade_id,
            descricao=str(descricao or "")[:500],
            dados_json=dados_json,
            ip=obter_ip_cliente(request),
            user_agent=obter_user_agent(request),
            criado_em=int(time.time())
        )
    )
