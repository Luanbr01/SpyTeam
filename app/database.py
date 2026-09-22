# ============================================================
# DATABASE.PY
# Conexão com o banco de dados do SpyTeam
#
# IMPORTANTE:
# Em produção no Railway, o SQLite DEVE ficar dentro do Volume
# persistente. Se o Railway for detectado sem Volume, a aplicação
# interrompe a inicialização para evitar perda silenciosa de dados
# a cada deploy.
# ============================================================

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


PASTA_APP = os.path.dirname(os.path.abspath(__file__))
PASTA_PROJETO = os.path.dirname(PASTA_APP)


def _esta_no_railway() -> bool:
    """Detecta se a aplicação está sendo executada dentro do Railway."""
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
    """Retorna True se caminho estiver dentro de pasta."""
    try:
        caminho = os.path.abspath(caminho)
        pasta = os.path.abspath(pasta)
        return os.path.commonpath([caminho, pasta]) == pasta
    except (ValueError, OSError):
        return False


def obter_caminho_banco() -> str:
    """
    Ordem de prioridade:

    1. DATABASE_PATH, se configurado manualmente.
    2. RAILWAY_VOLUME_MOUNT_PATH, quando o Volume estiver conectado.
    3. assessoria.db na raiz do projeto, SOMENTE para desenvolvimento local.

    Proteção:
    - Se estivermos no Railway e nenhum Volume estiver conectado,
      a aplicação NÃO inicia.
    - Se DATABASE_PATH estiver configurado no Railway, ele precisa apontar
      para dentro do Volume persistente.
    """

    no_railway = _esta_no_railway()
    caminho_manual = os.getenv("DATABASE_PATH")
    volume_railway = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")

    # --------------------------------------------------------
    # PROTEÇÃO CONTRA BANCO EFÊMERO NO RAILWAY
    # --------------------------------------------------------
    if no_railway and not volume_railway:
        raise RuntimeError(
            "Railway detectado, mas nenhum Volume persistente está conectado. "
            "O SpyTeam se recusa a usar SQLite no filesystem efêmero porque "
            "alunos e treinos seriam perdidos a cada deploy. "
            "Conecte um Railway Volume ao serviço e use mount path /data."
        )

    # --------------------------------------------------------
    # CAMINHO DO BANCO
    # --------------------------------------------------------
    if caminho_manual:
        caminho = os.path.abspath(caminho_manual)

        if no_railway and volume_railway:
            volume_abs = os.path.abspath(volume_railway)

            if not _esta_dentro_da_pasta(caminho, volume_abs):
                raise RuntimeError(
                    "DATABASE_PATH está fora do Railway Volume. "
                    f"DATABASE_PATH={caminho!r}; "
                    f"RAILWAY_VOLUME_MOUNT_PATH={volume_abs!r}. "
                    "Use, por exemplo, DATABASE_PATH=/data/assessoria.db."
                )

    elif volume_railway:
        caminho = os.path.join(
            os.path.abspath(volume_railway),
            "assessoria.db",
        )

    else:
        # Desenvolvimento local
        caminho = os.path.join(
            PASTA_PROJETO,
            "assessoria.db",
        )

    pasta_banco = os.path.dirname(caminho)

    if pasta_banco:
        os.makedirs(
            pasta_banco,
            exist_ok=True,
        )

    return caminho


CAMINHO_BANCO = obter_caminho_banco()

# A linha abaixo é proposital: permite confirmar nos logs de produção
# exatamente qual arquivo SQLite está sendo usado.
print(f"[SpyTeam] Banco de dados ativo: {CAMINHO_BANCO}")


SQLALCHEMY_DATABASE_URL = (
    f"sqlite:///{CAMINHO_BANCO}"
)


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
