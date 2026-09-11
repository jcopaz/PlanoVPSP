# -*- coding: utf-8 -*-
"""Carga do plano do trimestre.

Reaproveita a "busca dinâmica de cabeçalho" da v1 (as planilhas que os
colaboradores preenchem costumam ter linhas de título antes do cabeçalho real)
e o mapeamento flexível de nomes de coluna.
"""
from __future__ import annotations

import re

import pandas as pd

from . import config

# Nome canônico -> variações aceitas (minúsculas, sem espaços duplicados)
MAPA_DIARIO = {
    "Origem Programação": ["origem programação", "origem programacao", "origem", "tipo de programação"],
    "Depto": ["depto", "departamento"],
    "Chave Peso": ["chave peso", "chave_peso"],
    "Data Planejada": ["data planejada", "data_planejada", "data"],
    "Semana": ["semana", "sem"],
    "Coordenação": ["coordenação", "coordenacao", "coord"],
    "Equipe": ["equipe", "turma"],
    "Grupo": ["grupo"],
    "Descrição Meta": ["descrição meta", "descricao meta", "descrição", "meta", "atividade"],
    "Número do Material": ["número do material", "numero do material", "nº do material / nº do serviço",
                           "n° do material / n° do serviço", "cod material", "código do material"],
    "Peso Planejado Linha": ["peso planejado linha", "peso planejado"],
    "Plano": ["plano"],
    "Peso Realizado Linha": ["peso realizado linha", "peso realizado"],
    "Peso Extra Linha": ["peso extra linha", "peso extra"],
    "QUANTIDADE REALIZADA": ["quantidade realizada", "qtd realizada", "realizado"],
    "Quantidade Programada": ["quantidade programada", "qtd programada", "programado", "plano trimestral"],
    "Justificativa Padrão": ["justificativa padrão", "justificativa padrao", "justificativa"],
    "Observação": ["observação", "observacao", "obs"],
}

PALAVRAS_CABECALHO = ["semana", "equipe", "peso", "meta", "plano", "data", "quantidade", "origem"]


def _acha_linha_cabecalho(df_bruto: pd.DataFrame, minimo: int = 3) -> int:
    for i, row in df_bruto.iterrows():
        valores = [str(v).lower() for v in row.tolist()]
        acertos = sum(1 for p in PALAVRAS_CABECALHO if any(p in v for v in valores))
        if acertos >= minimo:
            return i
    return 0


def _limpa_cols(cols) -> list[str]:
    return (
        pd.Index(cols).astype(str).str.strip().str.replace(r"\s+", " ", regex=True).tolist()
    )


def _renomeia(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    for canonico, variacoes in mapa.items():
        for c in list(df.columns):
            if str(c).lower().strip() in variacoes and c != canonico:
                df = df.rename(columns={c: canonico})
                break
    return df


def carregar_plano(p: config.Parametros):
    """Retorna (df_diario_merge, df_peso, avisos:list[str])."""
    avisos: list[str] = []
    arq = config.caminho(p.g("arquivo_plano", str, ""))

    bruto = pd.read_excel(arq, sheet_name=p.g("aba_diario", str, "Diário"), header=None, nrows=25)
    h = _acha_linha_cabecalho(bruto)
    dia = pd.read_excel(arq, sheet_name=p.g("aba_diario", str, "Diário"), header=h)
    dia.columns = _limpa_cols(dia.columns)
    dia = _renomeia(dia, MAPA_DIARIO)

    # ---- Planilha de Peso -------------------------------------------------- #
    try:
        bruto_p = pd.read_excel(arq, sheet_name=p.g("aba_peso", str, "Planilha de Peso"),
                                header=None, nrows=20)
        hp = 0
        for i, row in bruto_p.iterrows():
            vals = [str(v).lower() for v in row.tolist()]
            if any("chave" in v and "peso" in v for v in vals) or \
               any("descrição meta" in v or "descricao meta" in v for v in vals):
                hp = i
                break
        peso = pd.read_excel(arq, sheet_name=p.g("aba_peso", str, "Planilha de Peso"), header=hp)
        peso.columns = _limpa_cols(peso.columns)
        ren = {}
        for c in peso.columns:
            cl = c.lower().strip()
            if cl in ("chave peso", "chave_peso"):
                ren[c] = "Chave Peso"
            elif cl in ("unidade", "unid"):
                ren[c] = "Unidade"
            elif cl == "sla":
                ren[c] = "SLA"
            elif cl in ("descrição meta", "descricao meta"):
                ren[c] = "Descrição Meta"
            elif cl in ("coordenação2", "coordenacao2", "coordenação"):
                ren[c] = "Coordenação Peso"
            elif "peso item redist ger" in cl:
                ren[c] = "Peso Item Ger"
            elif "peso item redist" in cl:
                ren[c] = "Peso Item"
            elif cl in ("plano trimestral",):
                ren[c] = "Plano Trimestral"
        peso = peso.rename(columns=ren)
        cols_peso = [c for c in ["Chave Peso", "Unidade", "SLA", "Descrição Meta",
                                 "Coordenação Peso", "Peso Item", "Peso Item Ger",
                                 "Plano Trimestral"] if c in peso.columns]
        if "Chave Peso" in dia.columns and "Chave Peso" in peso.columns:
            dia = dia.merge(peso[cols_peso].drop_duplicates("Chave Peso"),
                            on="Chave Peso", how="left", suffixes=("", "_peso"))
    except Exception as e:  # noqa: BLE001
        peso = pd.DataFrame()
        avisos.append(f"Planilha de Peso não pôde ser lida ({e}). Unidade/SLA ficarão em branco.")

    if "Unidade" not in dia.columns:
        dia["Unidade"] = "-"
    if "SLA" not in dia.columns:
        dia["SLA"] = "-"

    # ---- tipagem --------------------------------------------------------- #
    if "Data Planejada" in dia.columns:
        dia["Data Planejada"] = pd.to_datetime(dia["Data Planejada"], errors="coerce")
    if "Semana" in dia.columns:
        dia["Semana"] = pd.to_numeric(dia["Semana"], errors="coerce").fillna(0).astype(int)
    for c in ["Peso Planejado Linha", "Peso Realizado Linha", "Peso Extra Linha",
              "QUANTIDADE REALIZADA", "Quantidade Programada"]:
        if c in dia.columns:
            dia[c] = pd.to_numeric(dia[c], errors="coerce").fillna(0.0)
    for c in ["Origem Programação", "Plano", "Coordenação", "Descrição Meta"]:
        if c in dia.columns:
            dia[c] = dia[c].astype("string").str.strip()

    if "Origem Programação" not in dia.columns:
        raise KeyError(
            "Coluna 'Origem Programação' (ou similar) não encontrada. "
            f"Colunas lidas: {list(dia.columns)}"
        )

    return dia, peso, avisos
