# modules/comum.py — Funções compartilhadas pelas telas
#
# Cache: as leituras do banco usam st.cache_data com a "versão dos dados"
# (config._versao_dados, incrementada a cada gravação) na chave. Assim cada
# rerun faz só 1 consulta leve (a versão) e o resto vem do cache até alguém
# gravar algo — economiza o tráfego do Neon (lição do Gestão_OS, out/2026).

from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from auth.session import get_trimestre_id, set_trimestre_id
from core import motor
from database import queries as q


# region ====================== SESSÃO 1: Leituras em cache ======================

@st.cache_data(ttl=900, show_spinner=False)
def _dados_trimestre(tid: int, versao: int):
    pesos, plano, lanc = q.carregar_dados(tid)
    return pesos, plano, lanc


@st.cache_data(ttl=900, show_spinner=False)
def _cadastros(versao: int):
    return q.ler_config(), q.listar_coordenacoes(), q.listar_catalogo(), q.listar_listas()


@st.cache_data(ttl=900, show_spinner=False)
def _trimestres(versao: int) -> pd.DataFrame:
    return q.listar_trimestres()


@st.cache_data(ttl=900, show_spinner="Calculando o plano...")
def _resultado(tid: int, versao: int):
    t = q.obter_trimestre(tid)
    pesos, plano, lanc = _dados_trimestre(tid, versao)
    cfg, coords, catalogo, _ = _cadastros(versao)
    p = motor.parametros(cfg, coords, t["ano"], t["trimestre"], t["semana_inicio"], t["semana_fim"])
    return motor.calcular_trimestre(pesos, plano, lanc, catalogo, p)


def versao() -> int:
    return q.versao_dados()


def dados_trimestre(tid: int):
    return _dados_trimestre(tid, versao())


def cadastros():
    """(config dict, coordenações, catálogo SLA, listas)."""
    return _cadastros(versao())


def trimestres() -> pd.DataFrame:
    return _trimestres(versao())


def resultado(tid: int) -> motor.ResultadoTrimestre:
    return _resultado(tid, versao())


def limpar_cache() -> None:
    """Depois de gravar: a versão muda sozinha, mas limpar libera memória."""
    st.cache_data.clear()

# endregion


# region ====================== SESSÃO 2: Trimestre ativo ======================

def trimestre_ativo() -> dict | None:
    """Trimestre escolhido no menu lateral (padrão: o mais recente)."""
    tri = trimestres()
    if tri.empty:
        return None
    tid = get_trimestre_id()
    if tid not in set(tri["id"]):
        tid = int(tri.iloc[-1]["id"])
        set_trimestre_id(tid)
    return tri.loc[tri["id"] == tid].iloc[0].to_dict()


def exige_trimestre() -> dict:
    t = trimestre_ativo()
    if t is None:
        st.info("📭 Ainda não há trimestre no sistema. Vá em **Dados → Upload** e importe o plano do PCM "
                "(ou uma planilha de trimestre passado).")
        st.stop()
    return t


def deptos_cadastrados() -> list[str]:
    _, coords, _, _ = cadastros()
    return sorted(coords["depto"].tolist()) if not coords.empty else []


def coord_por_depto() -> dict:
    _, coords, _, _ = cadastros()
    return dict(zip(coords["depto"], coords["coordenacao"])) if not coords.empty else {}

# endregion


# region ====================== SESSÃO 3: Upload ======================

def salvar_temporario(arquivo_enviado) -> str:
    """Grava o arquivo do st.file_uploader num temporário (o pandas relê o
    Excel várias vezes; com caminho em disco isso é seguro)."""
    sufixo = os.path.splitext(arquivo_enviado.name)[1] or ".xlsx"
    fd, caminho = tempfile.mkstemp(suffix=sufixo)
    with os.fdopen(fd, "wb") as f:
        f.write(arquivo_enviado.getvalue())
    return caminho

# endregion
