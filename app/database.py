# ============================================================
# DATABASE.PY
# Conexão com o banco de dados do SpyTeam
# ============================================================

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# ============================================================
# LOCALIZAÇÃO DO BANCO
# ============================================================

PASTA_APP = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETO = os.path.dirname(PASTA_APP)


def obter_caminho_banco() -> str:
    """
    Ordem de prioridade:

    1. DATABASE_PATH, se configurado manualmente.
    2. Volume persistente do Railway, quando existir.
    3. assessoria.db na raiz do projeto para desenvolvimento local.
    """

    caminho_manual = os.getenv("DATABASE_PATH")

    if caminho_manual:
        caminho = os.path.abspath(caminho_manual)

    else:
        volume_railway = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

        if volume_railway:
            caminho = os.path.join(
                volume_railway,
                "assessoria.db"
            )
        else:
            caminho = os.path.join(
                PASTA_PROJETO,
                "assessoria.db"
            )

    pasta_banco = os.path.dirname(caminho)

    if pasta_banco:
        os.makedirs(
            pasta_banco,
            exist_ok=True
        )

    return caminho


CAMINHO_BANCO = obter_caminho_banco()


# ============================================================
# URL SQLITE
# ============================================================

SQLALCHEMY_DATABASE_URL = (
    f"sqlite:///{CAMINHO_BANCO}"
)


# ============================================================
# ENGINE
# ============================================================

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


# ============================================================
# SESSÃO
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================
# BASE
# ============================================================

Base = declarative_base()
