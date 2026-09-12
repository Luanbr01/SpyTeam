from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Define o arquivo do banco de dados local
SQLALCHEMY_DATABASE_URL = "sqlite:///./database/assessoria.db"

# Cria o motor de conexão
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Cria a sessão que usaremos para conversar com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe base para criarmos as nossas tabelas
Base = declarative_base()