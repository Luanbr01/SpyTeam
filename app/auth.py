# ============================================================
# AUTH.PY
# Sistema de autenticação do SpyTeam
# ============================================================

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Chave utilizada para assinar o token de login.
#
# Em desenvolvimento podemos deixar essa chave.
# Em produção, troque por uma chave grande e aleatória.
_secret_configurado = os.getenv("SPYTEAM_SECRET")

# No Railway, nunca usamos a chave padrão de desenvolvimento.
if not _secret_configurado and os.getenv("RAILWAY_ENVIRONMENT_NAME"):
    raise RuntimeError(
        "SPYTEAM_SECRET não configurado. "
        "Adicione essa variável na aba Variables do Railway."
    )

SECRET = (
    _secret_configurado
    or "spyteam-chave-dev-troque-em-producao"
).encode()


# Nome do cookie que será salvo no navegador
COOKIE_NAME = "spyteam_session"


# Tempo de validade da sessão
# 1 dia = 24 horas
SESSION_DAYS = 1


# Número de repetições do PBKDF2.
# Isso dificulta ataques de força bruta contra as senhas.
ITERATIONS = 310_000


# ============================================================
# HASH DA SENHA
# ============================================================

def hash_senha(senha: str) -> str:
    """
    Recebe a senha normal e devolve uma versão protegida.

    A senha NÃO será salva diretamente no banco.
    """

    # Cria um salt aleatório
    salt = secrets.token_bytes(16)

    # Gera o hash usando PBKDF2 + SHA256
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        salt,
        ITERATIONS
    )

    # Salvamos:
    # quantidade de iterações
    # salt
    # hash
    #
    # separados por $
    return (
        f"{ITERATIONS}"
        f"${salt.hex()}"
        f"${digest.hex()}"
    )


# ============================================================
# VERIFICAR SENHA
# ============================================================

def verificar_senha(
    senha: str,
    senha_hash: str
) -> bool:

    try:

        # Separa os valores salvos
        iterations, salt_hex, digest_hex = (
            senha_hash.split("$", 2)
        )

        # Converte novamente o salt
        salt = bytes.fromhex(salt_hex)

        # Converte o hash esperado
        esperado = bytes.fromhex(digest_hex)

        # Gera novamente o hash utilizando
        # a senha digitada
        atual = hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            salt,
            int(iterations)
        )

        # Compara de forma segura
        return hmac.compare_digest(
            atual,
            esperado
        )

    except (ValueError, TypeError):

        return False


# ============================================================
# BASE64
# ============================================================

def _b64(data: bytes) -> str:

    return base64.urlsafe_b64encode(
        data
    ).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:

    return base64.urlsafe_b64decode(
        data + "=" * (-len(data) % 4)
    )


# ============================================================
# CRIAR TOKEN
# ============================================================

def criar_token(
    usuario_id: int,
    tipo: str
) -> str:

    # Informações que serão colocadas dentro do token
    payload = {

        # ID do usuário
        "sub": usuario_id,

        # Tipo:
        # professor
        # aluno
        "tipo": tipo,

        # Data de expiração
        "exp": int(time.time())
        + SESSION_DAYS * 24 * 60 * 60
    }

    # Transforma o JSON em bytes
    corpo = _b64(
        json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")
    )

    # Cria uma assinatura para impedir
    # que alguém altere o token
    assinatura = _b64(
        hmac.new(
            SECRET,
            corpo.encode("ascii"),
            hashlib.sha256
        ).digest()
    )

    # Token final:
    #
    # corpo.assinatura
    return f"{corpo}.{assinatura}"


# ============================================================
# LER TOKEN
# ============================================================

def ler_token(
    token: str | None
) -> dict | None:

    # Não existe token
    if not token:
        return None

    # Token precisa conter "."
    if "." not in token:
        return None

    try:

        # Divide o token
        corpo, assinatura = token.split(
            ".",
            1
        )

        # Calcula a assinatura novamente
        assinatura_esperada = _b64(
            hmac.new(
                SECRET,
                corpo.encode("ascii"),
                hashlib.sha256
            ).digest()
        )

        # Verifica se a assinatura é válida
        if not hmac.compare_digest(
            assinatura,
            assinatura_esperada
        ):
            return None

        # Recupera os dados
        payload = json.loads(
            _unb64(corpo)
        )

        # Verifica expiração
        if int(payload["exp"]) < int(time.time()):
            return None

        return payload

    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ):

        return None

# ============================================================
# TOKEN DE RECUPERAÇÃO DE SENHA
# ============================================================

def criar_token_recuperacao() -> str:
    """Cria um token aleatório que pode ser enviado por e-mail."""
    return secrets.token_urlsafe(32)


def hash_token_recuperacao(token: str) -> str:
    """Guarda apenas o hash do token no banco."""
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
