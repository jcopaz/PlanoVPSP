# database/client.py — Conexão com o banco (SQLite local ou PostgreSQL/Neon)
#
# Onde fica o banco (primeira opção encontrada vence):
#   1. st.secrets["database"]["url"]   → produção (Streamlit Cloud + Neon)
#   2. variável de ambiente PLANO_DB_URL
#   3. sqlite:///dados/plano.db         → uso local (pasta dados/ fora do Git)
#
# Neon na rede MRS: a porta 5432 só passa com SSL "direto". A URL fica
#   postgresql+psycopg2://USUARIO:SENHA@HOST/BANCO?sslmode=require&sslnegotiation=direct
# (mesmo achado do VIA WMS, out/2026). Senha só nos secrets, nunca no código.
#
# Na 1ª conexão: cria as tabelas (database/schema.py) e semeia config,
# coordenações e listas padrão (database/queries.py::semear_padroes).

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

RAIZ = Path(__file__).resolve().parent.parent
SQLITE_PADRAO = RAIZ / "dados" / "plano.db"


def _normalizar(url: str) -> str:
    """Aceita a URL como o Neon entrega (postgresql://, postgres://) ou com outro
    driver (postgresql+psycopg://) e força o psycopg2, que é o instalado."""
    url = url.strip().strip('"').strip("'")
    for prefixo in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg2://" + url[len(prefixo):]
    return url


def _url() -> str:
    try:
        import streamlit as st
        url = st.secrets.get("database", {}).get("url")
        if url:
            return _normalizar(url)
    except Exception:  # noqa: BLE001 — sem secrets.toml / fora do Streamlit
        pass
    return _normalizar(os.environ.get("PLANO_DB_URL") or f"sqlite:///{SQLITE_PADRAO.as_posix()}")


def descricao_banco() -> str:
    """Texto curto para a tela (sem senha)."""
    url = _url()
    if url.startswith("sqlite"):
        return f"SQLite local ({SQLITE_PADRAO.name})"
    return "PostgreSQL · " + url.split("@")[-1].split("?")[0]


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Engine único por processo (o Streamlit reaproveita entre reruns)."""
    from database import queries, schema

    url = _url()
    if url.startswith("sqlite"):
        SQLITE_PADRAO.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=300)
    schema.criar_tabelas(engine)
    queries.semear_padroes(engine)
    return engine
