# -*- coding: utf-8 -*-
"""Carga do plano do trimestre.

Aceita dois formatos (detectado pelas abas):
- **modelo v3** (``Pesos`` / ``Plano_PCM`` / ``Lancamentos``, sem fórmulas) - ver
  ``core/modelo.py``; aqui se calculam semana, coordenação e pesos.
- **antigo** (``Diário`` + ``Planilha de Peso``, com as fórmulas do Excel).

Para o formato antigo, reaproveita a "busca dinâmica de cabeçalho" da v1 (as planilhas que os
colaboradores preenchem costumam ter linhas de título antes do cabeçalho real)
e o mapeamento flexível de nomes de coluna.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config, modelo

# Nome canônico -> variações aceitas (minúsculas, sem espaços duplicados)
MAPA_DIARIO = {
    "Origem Programação": ["origem programação", "origem programacao", "origem promagramação", "origem",
                           "tipo de programação"],
    "Depto": ["depto", "departamento"],
    "Chave Peso": ["chave peso", "chave_peso"],
    "Data Planejada": ["data planejada", "data_planejada", "data"],
    "Semana": ["semana", "sem"],
    "Coordenação": ["coordenação", "coordenacao", "coord"],
    "Equipe": ["equipe", "turma"],
    "Grupo": ["grupo"],
    "Descrição Meta": ["descrição meta", "descricao meta", "descricaometa", "descrição", "meta", "atividade"],
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


def para_data(valores) -> pd.Series:
    """Datas vindas de Excel/tela/texto. Texto ISO (2026-10-05) é lido como ano-mês-dia;
    o resto como dia/mês/ano (padrão brasileiro). Sem isso, "2026-10-05" virava 10/05."""
    s = pd.Series(valores)
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    iso = s.astype("string").str.match(r"^\s*\d{4}-\d{2}-\d{2}").fillna(False).astype(bool)
    out = pd.to_datetime(s.where(~iso), errors="coerce", dayfirst=True)
    if iso.any():
        out[iso] = pd.to_datetime(s[iso].astype(str).str.strip().str[:10], format="%Y-%m-%d", errors="coerce")
    return out


def semana_excel(datas: pd.Series) -> pd.Series:
    """Equivalente ao =WEEKNUM(data) do Excel (semana começa no domingo; 1/jan = semana 1)."""
    d = pd.to_datetime(datas, errors="coerce")
    doy = d.dt.dayofyear
    dom_d = (d.dt.dayofweek + 1) % 7                 # domingo = 0
    desloc = (dom_d - (doy - 1)) % 7                 # dia da semana de 1/jan (domingo = 0)
    sem = (doy - 1 + desloc) // 7 + 1
    return sem.fillna(0).astype(int)


def _sim_nao(valor, s_sim: str, s_nao: str):
    v = str(valor).strip().lower()
    if v in ("sim", "s", "x", "yes", "1", "true"):
        return s_sim
    if v in ("não", "nao", "n", "no", "0", "false"):
        return s_nao
    return pd.NA


def _le_aba_modelo(xls: pd.ExcelFile, nome: str, colunas: list[str]) -> pd.DataFrame:
    real = next(n for n in xls.sheet_names if n.strip().lower() == nome.lower())
    df = pd.read_excel(xls, real)
    df.columns = _limpa_cols(df.columns)
    for c in colunas:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[colunas]
    return df.dropna(how="all")


def _texto(s: pd.Series, maiusculo: bool = False) -> pd.Series:
    s = s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    return s.str.upper() if maiusculo else s


def ler_abas_modelo(xls: pd.ExcelFile) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(pesos, plano, lancamentos) de uma planilha no modelo v3."""
    return (_le_aba_modelo(xls, modelo.ABA_PESOS, modelo.COLS_PESOS),
            _le_aba_modelo(xls, modelo.ABA_PLANO, modelo.COLS_PLANO),
            _le_aba_modelo(xls, modelo.ABA_LANC, modelo.COLS_LANC))


def _carregar_modelo(xls: pd.ExcelFile, p: config.Parametros):
    """Lê o modelo v3 (Pesos/Plano_PCM/Lancamentos) e devolve o formato canônico."""
    return montar_canonico(*ler_abas_modelo(xls), p)


def montar_canonico(pesos: pd.DataFrame, plano: pd.DataFrame, lanc: pd.DataFrame,
                    p: config.Parametros, catalogo: pd.DataFrame | None = None):
    """Pesos/Plano/Lançamentos (cabeçalhos do modelo v3, vindos do Excel OU do
    banco) -> mesmo formato canônico do Diário antigo, com as colunas que eram
    fórmula já calculadas. ``catalogo`` (Depto, Descrição Meta, Unidade, SLA)
    completa Unidade/SLA que não vierem na aba Pesos."""
    avisos: list[str] = []
    o_pcm = p.g("origem_pcm", str, "PCM")
    o_exec = p.g("origem_execucao", str, "Coordenação")
    s_sim, s_nao = p.g("plano_sim", str, "Sim"), p.g("plano_nao", str, "Não")

    pesos = pesos.reindex(columns=modelo.COLS_PESOS).copy()
    plano = plano.reindex(columns=modelo.COLS_PLANO).copy()
    lanc = lanc.reindex(columns=modelo.COLS_LANC).copy()
    if catalogo is not None and not catalogo.empty:
        cat = catalogo.copy()
        cat["_k"] = _texto(cat["Depto"], True) + "|" + _texto(cat["Descrição Meta"], True)
        cat = cat.drop_duplicates("_k").set_index("_k")
        k = _texto(pesos["Depto"], True) + "|" + _texto(pesos["Descrição Meta"], True)
        for c in ("Unidade", "SLA"):
            pesos[c] = pesos[c].where(pesos[c].notna(), k.map(cat[c]))

    # ---- Plano PCM e Lançamentos no formato do Diário -------------------- #
    pcm = pd.DataFrame({
        "Origem Programação": o_pcm,
        "Depto": plano["Depto"],
        "Data Planejada": plano["Data Planejada"],
        "Descrição Meta": plano["Descrição Meta"],
        "Número do Material": plano["Nº Material"],
        "Equipe": plano["Equipe"],
        "Ativo": plano["Ativo"],
        "Equipamento": plano["Equipamento"],
        "Tipo Material": plano["Tipo Material"],
        "Quantidade Programada": plano["Quantidade Programada"],
        "Plano": s_sim,
        "QUANTIDADE REALIZADA": 0.0,
        "Observação": plano["Observação"],
    })
    exe = pd.DataFrame({
        "Origem Programação": o_exec,
        "Depto": lanc["Depto"],
        "Data Planejada": lanc["Data"],
        "Descrição Meta": lanc["Descrição Meta"],
        "Número do Material": lanc["Nº Material"],
        "Equipe": lanc["Equipe"],
        "Ativo": lanc["Ativo"],
        "Tipo Material": lanc["Tipo Material"],
        "Quantidade Programada": lanc["Quantidade Programada"],
        "Plano": lanc["No Plano"].map(lambda v: _sim_nao(v, s_sim, s_nao)),
        "QUANTIDADE REALIZADA": lanc["Quantidade Realizada"],
        "Justificativa Padrão": lanc["Justificativa"],
        "Observação": lanc["Observação"],
        "Plano de ação": lanc["Plano de Ação"],
        "Responsável": lanc["Responsável"],
        "Prazo": lanc["Prazo"],
        "Status": lanc["Status"],
        "Programador": lanc["Programador"],
    })
    n_sem_plano = int(exe["Plano"].isna().sum())
    if n_sem_plano:
        avisos.append(f"{n_sem_plano} lançamento(s) sem 'No Plano' = Sim/Não foram ignorados nas curvas.")
    dia = pd.concat([pcm, exe], ignore_index=True)

    dia["Depto"] = _texto(dia["Depto"], maiusculo=True)
    dia["Descrição Meta"] = _texto(dia["Descrição Meta"], maiusculo=True)
    dia["Data Planejada"] = para_data(dia["Data Planejada"])
    n_sem_data = int(dia["Data Planejada"].isna().sum())
    if n_sem_data:
        avisos.append(f"{n_sem_data} linha(s) sem data válida (ficam fora das curvas semanais).")
    for c in ("Quantidade Programada", "QUANTIDADE REALIZADA"):
        dia[c] = pd.to_numeric(dia[c], errors="coerce").fillna(0.0)

    dia["Semana"] = semana_excel(dia["Data Planejada"])
    coord = p.coord_por_depto()
    dia["Coordenação"] = dia["Depto"].map(coord)
    sem_coord = sorted(dia.loc[dia["Coordenação"].isna() & dia["Depto"].notna(), "Depto"].unique())
    if sem_coord:
        avisos.append(f"Depto sem coordenação em parametros.xlsx (aba Coordenacoes): {', '.join(sem_coord)}.")
    dia["Chave Peso"] = dia["Depto"].fillna("") + "|" + dia["Descrição Meta"].fillna("")

    # ---- Pesos: normaliza por Depto entre as metas com plano > 0 --------- #
    pesos["Depto"] = _texto(pesos["Depto"], maiusculo=True)
    pesos["Descrição Meta"] = _texto(pesos["Descrição Meta"], maiusculo=True)
    pesos["Peso"] = pd.to_numeric(pesos["Peso"], errors="coerce").fillna(0.0).clip(lower=0)
    fora = {g.strip().upper() for g in p.g("grupos_fora_aderencia", str, "").split(";") if g.strip()}
    if fora:
        pesos.loc[pesos["Grupo"].astype("string").str.strip().str.upper().isin(fora).fillna(False), "Peso"] = 0.0
    pesos = pesos.dropna(subset=["Depto", "Descrição Meta"])
    pesos["Chave Peso"] = pesos["Depto"] + "|" + pesos["Descrição Meta"]
    pesos = pesos.drop_duplicates("Chave Peso", keep="last")

    plano_tri = (dia[dia["Origem Programação"] == o_pcm]
                 .groupby("Chave Peso")["Quantidade Programada"].sum().rename("Plano Trimestral"))
    pesos["Plano Trimestral"] = pesos["Chave Peso"].map(plano_tri).astype(float).fillna(0.0)
    ativo = pesos["Plano Trimestral"] > 0
    soma = pesos[ativo].groupby("Depto")["Peso"].transform("sum")
    pesos["Peso Item"] = 0.0
    pesos.loc[ativo, "Peso Item"] = (pesos.loc[ativo, "Peso"] / soma.replace(0, np.nan)).fillna(0.0)
    pesos["Peso por unidade"] = (pesos["Peso Item"] / pesos["Plano Trimestral"].replace(0, np.nan)).fillna(0.0)
    pesos["Peso Item Ger"] = pesos["Peso Item"] / p.n_coord_gerencia
    pesos["Coordenação Peso"] = pesos["Depto"].map(coord)

    sem_peso = sorted(set(plano_tri[plano_tri > 0].index) - set(pesos.loc[pesos["Peso"] > 0, "Chave Peso"]))
    if sem_peso:
        avisos.append("Metas no Plano_PCM sem peso na aba Pesos (não contam na curva): "
                      + ", ".join(sem_peso[:8]) + (" ..." if len(sem_peso) > 8 else ""))

    # SLA/Unidade como texto ("2" e não 2.0; "-" quando falta) - evita coluna mista na tabela
    for c in ("Unidade", "SLA"):
        pesos[c] = pesos[c].map(lambda v: "-" if pd.isna(v) else
                                (f"{v:g}" if isinstance(v, (int, float)) else str(v).strip()))
    por_chave = pesos.set_index("Chave Peso")
    for c, destino in [("Grupo", "Grupo"), ("Unidade", "Unidade"), ("SLA", "SLA"),
                       ("Peso por unidade", "Peso Unitário"), ("Peso Item", "Peso Item"),
                       ("Peso Item Ger", "Peso Item Ger"), ("Plano Trimestral", "Plano Trimestral")]:
        dia[destino] = dia["Chave Peso"].map(por_chave[c])
    dia["Peso Unitário"] = pd.to_numeric(dia["Peso Unitário"], errors="coerce").fillna(0.0)
    dia["Unidade"] = dia["Unidade"].fillna("-")
    dia["SLA"] = dia["SLA"].fillna("-")

    e_exec = dia["Origem Programação"] == o_exec
    dia["Peso Realizado Linha"] = np.where(e_exec & (dia["Plano"] == s_sim),
                                           dia["QUANTIDADE REALIZADA"] * dia["Peso Unitário"], 0.0)
    dia["Peso Extra Linha"] = np.where(e_exec & (dia["Plano"] == s_nao),
                                       dia["QUANTIDADE REALIZADA"] * dia["Peso Unitário"], 0.0)
    dia["Peso Planejado Linha"] = np.where((dia["Origem Programação"] == o_pcm) & (dia["Plano"] == s_sim),
                                           dia["Quantidade Programada"] * dia["Peso Unitário"], 0.0)
    for c in ["Origem Programação", "Plano", "Coordenação", "Descrição Meta"]:
        dia[c] = dia[c].astype("string").str.strip()

    return dia, pesos, avisos


def carregar_plano(p: config.Parametros):
    """Retorna (df_diario_merge, df_peso, avisos:list[str])."""
    avisos: list[str] = []
    arq = config.caminho(p.g("arquivo_plano", str, ""))

    with pd.ExcelFile(arq) as xls:
        if modelo.eh_modelo(xls.sheet_names):
            return _carregar_modelo(xls, p)

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
