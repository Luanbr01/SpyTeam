# ============================================================
# DATABASE.PY
# Conexão com o banco de dados do SpyTeam
# ============================================================

import os

from sqlalchemy import create_engine

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)


# ============================================================
# LOCALIZAÇÃO DO BANCO
# ============================================================

# __file__ aponta para:
#
# SpyTeam/app/database.py
#
# Então:
#
# dirname(__file__)     -> SpyTeam/app
#
# dirname(dirname(...)) -> SpyTeam
#
# Dessa forma conseguimos chegar ao banco
# mesmo que o Uvicorn seja iniciado pela raiz
# ou de outra pasta.

PASTA_APP = os.path.dirname(
    os.path.abspath(__file__)
)


PASTA_PROJETO = os.path.dirname(
    PASTA_APP
)


CAMINHO_BANCO = os.path.join(
    PASTA_PROJETO,
    "assessoria.db"
)


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