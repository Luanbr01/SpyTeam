# ============================================================
# DATABASE.PY
# Conexão com o banco de dados do SPY TEAM
#
# PRODUÇÃO:
# - PostgreSQL via DATABASE_URL (recomendado no Railway)
#
# DESENVOLVIMENTO / COMPATIBILIDADE:
# - SQLite quando DATABASE_URL não estiver configurado
# - No Railway, SQLite continua protegido por Volume persistente
# ============================================================

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


PASTA_APP = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETO = os.path.dirname(PASTA_APP)


def _esta_no_railway() -> bool:
    chaves = (
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_NAME",
        "RAILWAY_SERVICE_NAME",
        "RAILWAY_ENVIRONMENT_NAME",
    )
    return any(os.getenv(chave) for chave in chaves)


def _esta_dentro_da_pasta(caminho: str, pasta: str) -> bool:
    try:
        caminho = os.path.abspath(caminho)
        pasta = os.path.abspath(pasta)
        return os.path.commonpath([caminho, pasta]) == pasta
    except (ValueError, OSError):
        return False


def _normalizar_database_url(url: str) -> str:
    """Normaliza URLs PostgreSQL para o driver psycopg 3."""
    valor = str(url or "").strip()

    if valor.startswith("postgres://"):
        return "postgresql+psycopg://" + valor[len("postgres://"):]

    if valor.startswith("postgresql://"):
        return "postgresql+psycopg://" + valor[len("postgresql://"):]

    return valor


def obter_pasta_dados_persistentes() -> str:
    """
    Pasta usada para arquivos persistentes que NÃO ficam no banco,
    como fotos de perfil.

    No Railway, continua usando o Volume (/data). Mesmo após migrar o
    banco relacional para PostgreSQL, o Volume permanece útil para uploads.
    """
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

    if volume:
        pasta = os.path.abspath(volume)
    elif _esta_no_railway():
        raise RuntimeError(
            "Railway detectado sem Volume persistente. "
            "Mesmo usando PostgreSQL, o SPY TEAM precisa do Volume para "
            "arquivos enviados, como fotos de perfil."
        )
    else:
        pasta = PASTA_PROJETO

    os.makedirs(pasta, exist_ok=True)
    return pasta


def obter_caminho_sqlite() -> str:
    """Resolve o arquivo SQLite usado quando DATABASE_URL não existe."""
    no_railway = _esta_no_railway()
    caminho_manual = os.getenv("DATABASE_PATH")
    volume_railway = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

    if no_railway and not volume_railway:
        raise RuntimeError(
            "Railway detectado sem DATABASE_URL e sem Volume persistente. "
            "Configure PostgreSQL em DATABASE_URL ou conecte um Volume para SQLite."
        )

    if caminho_manual:
        caminho = os.path.abspath(caminho_manual)

        if no_railway and volume_railway:
            volume_abs = os.path.abspath(volume_railway)
            if not _esta_dentro_da_pasta(caminho, volume_abs):
                raise RuntimeError(
                    "DATABASE_PATH está fora do Railway Volume. "
                    f"DATABASE_PATH={caminho!r}; "
                    f"RAILWAY_VOLUME_MOUNT_PATH={volume_abs!r}."
                )

    elif volume_railway:
        caminho = os.path.join(os.path.abspath(volume_railway), "assessoria.db")

    else:
        caminho = os.path.join(PASTA_PROJETO, "assessoria.db")

    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    return caminho


PASTA_DADOS_PERSISTENTES = obter_pasta_dados_persistentes()
DATABASE_URL_AMBIENTE = str(os.getenv("DATABASE_URL") or "").strip()

if DATABASE_URL_AMBIENTE:
    SQLALCHEMY_DATABASE_URL = _normalizar_database_url(DATABASE_URL_AMBIENTE)
    BANCO_TIPO = "postgresql" if SQLALCHEMY_DATABASE_URL.startswith("postgresql") else "externo"
    CAMINHO_BANCO = None
else:
    CAMINHO_BANCO = obter_caminho_sqlite()
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{CAMINHO_BANCO}"
    BANCO_TIPO = "sqlite"


if BANCO_TIPO == "postgresql":
    print("[SpyTeam] Banco de dados ativo: PostgreSQL (DATABASE_URL)")
else:
    print(f"[SpyTeam] Banco de dados ativo: SQLite ({CAMINHO_BANCO})")

print(f"[SpyTeam] Pasta persistente de arquivos: {PASTA_DADOS_PERSISTENTES}")


if BANCO_TIPO == "sqlite":
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()
