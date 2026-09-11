# -*- coding: utf-8 -*-
"""Curva OPEX (financeira) - modelo TOP-DOWN.

Não existe custo unitário confiável por item de manutenção. Então:

1.  Monta-se o **envelope OPEX do período** a partir da aba ``PLAN ORÇ`` da
    ``Orçamento Ger. SP.xlsx`` (Orçado e Realizado por mês x Pacote x Centro de
    Custo), somando só os pacotes de manutenção e os centros de custo da visão
    escolhida.
2.  As curvas **Orçado Planejado / Realizado / Projetado** são esse envelope
    multiplicado pela curva FÍSICA correspondente (plano PCM, aderência real,
    projeção pelo ritmo médio). "Se executei 60 %% do plano físico, consumi ~60 %%
    do orçado."
3.  O R$ **por item** é o envelope rateado pelo peso planejado/realizado de cada
    ``Descrição Meta``.
4.  Duas linhas de **referência**: Orçamento OPEX oficial (curva mensal da PLAN
    ORÇ) e Realizado contábil SAP (PLAN ORÇ REAL ou aba ``Realizado Analitico``).

Se a planilha de orçamento não estiver disponível, ``disponivel = False`` e o
app mostra só a parte física.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config

MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


@dataclass
class ResultadoFinanceiro:
    disponivel: bool = False
    curva: pd.DataFrame = field(default_factory=pd.DataFrame)   # Semana | orcado_plan | realizado | projetado | ref_orcado | ref_realizado
    tabela_itens: pd.DataFrame = field(default_factory=pd.DataFrame)
    envelope_orcado: float = 0.0
    envelope_realizado_oficial: float = 0.0
    aviso: str = ""


# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return str(s).strip().upper()


def _acha_col_mes(cols, prefixo: str, mes: str) -> str | None:
    """Ex.: prefixo='OR', mes='ABR' -> 'ORÇ ABR' / 'ORC ABR' / 'OR$ ABR'..."""
    alvo = mes.upper()
    for c in cols:
        cu = _norm(c)
        if not cu.endswith(alvo):
            continue
        if prefixo == "OR" and cu.startswith("OR") and not cu.startswith("REAL"):
            return c
        if prefixo == "REAL" and cu.startswith("REAL"):
            return c
    return None


def _semanas_fim_de_mes(sem_ini: int, sem_fim: int, n_meses: int) -> list[int]:
    span = sem_fim - sem_ini + 1
    return [sem_ini + int(round((k + 1) / n_meses * span)) - 1 for k in range(n_meses)]


def _curva_mensal_para_semanal(valores_acum_mes, semanas_fim, sem_ini, sem_fim) -> pd.Series:
    """Interpola linearmente os acumulados de fim-de-mês para todas as semanas."""
    xs = [sem_ini - 1] + list(semanas_fim)
    ys = [0.0] + list(valores_acum_mes)
    todas = list(range(sem_ini, sem_fim + 1))
    return pd.Series(np.interp(todas, xs, ys), index=todas)


# --------------------------------------------------------------------------- #
def calcular(p: config.Parametros, coord: str, sem_ini: int, sem_fim: int,
            curva_fisica: pd.DataFrame, tabela_fisica: pd.DataFrame,
            semana_atual: int) -> ResultadoFinanceiro:
    r = ResultadoFinanceiro()
    arq = config.caminho(p.g("arquivo_orcamento", str, ""))
    rot_ger = p.g("rotulo_gerencia", str, "Gerência")
    meses = p.meses_trimestre
    cc_por_coord = p.cc_por_coord()
    pacotes = [_norm(x) for x in p.env_lista("pacotes_incluir")]
    ccs_cfg = [_norm(x) for x in p.env_lista("centros_custo")]

    ccs_visao = ccs_cfg if coord == rot_ger else [_norm(cc_por_coord.get(coord, "@@"))]

    try:
        po = pd.read_excel(arq, sheet_name=p.g("aba_plan_orc", str, "PLAN ORÇ"), header=2)
    except Exception as e:  # noqa: BLE001
        r.aviso = f"Orçamento não carregado ({e}). Exibindo apenas curva física."
        return r

    po.columns = pd.Index(po.columns).astype(str).str.strip()
    po = po.loc[:, ~po.columns.duplicated()]
    col_pac = next((c for c in po.columns if _norm(c) == "PACOTE"), None)
    col_cc = next((c for c in po.columns if "CENTRO DE CUSTO" in _norm(c)), None)
    if not col_pac or not col_cc:
        r.aviso = "PLAN ORÇ sem colunas PACOTE / CENTRO DE CUSTO reconhecíveis."
        return r

    po["_PAC"] = po[col_pac].map(_norm)
    po["_CC"] = po[col_cc].map(_norm)
    mask = po["_CC"].isin(ccs_visao)
    if pacotes:
        mask &= po["_PAC"].apply(lambda x: any(x.startswith(pk) or pk in x for pk in pacotes))
    sel = po[mask]
    if sel.empty:
        r.aviso = ("Nenhuma linha da PLAN ORÇ casou com os pacotes/centros de custo "
                   "configurados na aba Envelope_OPEX. Exibindo apenas curva física.")
        return r

    # ---- envelope mensal (acumulado) --------------------------------- #
    orc_mes, real_mes = [], []
    ac_o = ac_r = 0.0
    for m in meses:
        co = _acha_col_mes(po.columns, "OR", m)
        cr = _acha_col_mes(po.columns, "REAL", m)
        ac_o += float(pd.to_numeric(sel[co], errors="coerce").sum()) if co else 0.0
        ac_r += float(pd.to_numeric(sel[cr], errors="coerce").sum()) if cr else 0.0
        orc_mes.append(ac_o)
        real_mes.append(ac_r)

    envelope_orc = orc_mes[-1] if orc_mes else 0.0
    if envelope_orc <= 0:
        r.aviso = "Envelope orçado do período ficou zerado na PLAN ORÇ."
        return r
    r.disponivel = True
    r.envelope_orcado = envelope_orc
    r.envelope_realizado_oficial = real_mes[-1] if real_mes else 0.0

    # ---- realizado SAP alternativo (aba Realizado Analitico) -------- #
    if _norm(p.env("usar_realizado_sap_de", "PLAN ORÇ")).startswith("REALIZADO"):
        real_mes = _realizado_analitico(p, arq, ccs_visao, sem_ini, sem_fim) or real_mes

    semanas_fim = _semanas_fim_de_mes(sem_ini, sem_fim, len(meses))
    ref_orc = _curva_mensal_para_semanal(orc_mes, semanas_fim, sem_ini, sem_fim)
    ref_real = _curva_mensal_para_semanal(real_mes, semanas_fim, sem_ini, sem_fim)

    # ---- curvas derivadas do físico -------------------------------- #
    cf = curva_fisica.set_index("Semana")
    out = pd.DataFrame({"Semana": range(sem_ini, sem_fim + 1)}).set_index("Semana")
    out["orcado_plan"] = cf["meta_pcm"].reindex(out.index).ffill().fillna(0.0) * envelope_orc
    out["realizado"] = cf["realizado"].reindex(out.index) * envelope_orc
    out["projetado"] = cf["projecao"].reindex(out.index) * envelope_orc
    out["ref_orcado"] = ref_orc.reindex(out.index)
    out["ref_realizado"] = ref_real.reindex(out.index)
    r.curva = out.reset_index()

    # ---- rateio por item ----------------------------------------- #
    r.tabela_itens = _tabela_itens(tabela_fisica, envelope_orc, p)
    return r


def _realizado_analitico(p, arq, ccs_visao, sem_ini, sem_fim) -> list[float] | None:
    try:
        ra = pd.read_excel(arq, sheet_name=p.g("aba_realizado_analitico", str, "Realizado Analitico"),
                           header=1)
    except Exception:  # noqa: BLE001
        return None
    ra.columns = pd.Index(ra.columns).astype(str).str.strip()
    col_per = next((c for c in ra.columns if "Período Fiscal" in c or "Periodo Fiscal" in c
                    or c.startswith("Exerc")), None)
    col_mont = next((c for c in ra.columns if "Montante em moeda da empresa" in c), None)
    col_dre = next((c for c in ra.columns if _norm(c) == "DRE_FINAL"), None)
    col_cc = next((c for c in ra.columns if "Centro de custo" in c and "d." in c.lower()), None) \
        or next((c for c in ra.columns if "Centro de custo" in c), None)
    if not (col_per and col_mont):
        return None
    ra["_per"] = pd.to_numeric(ra[col_per], errors="coerce")
    ra["_mont"] = pd.to_numeric(ra[col_mont], errors="coerce").fillna(0.0)
    filtro = pd.Series(True, index=ra.index)
    dre_alvo = _norm(p.env("dre_realizado_sap", ""))
    if col_dre and dre_alvo:
        chave = dre_alvo.split("-")[-1]
        filtro &= ra[col_dre].map(_norm).str.contains(chave, na=False)
    if col_cc:
        filtro &= ra[col_cc].map(_norm).isin(ccs_visao)
    ra = ra[filtro]
    meses = p.meses_trimestre
    ac, saida = 0.0, []
    for m in meses:
        yyyymm = p.ano * 100 + MESES.get(m.upper(), 0)
        ac += float(ra.loc[ra["_per"] == yyyymm, "_mont"].sum())
        saida.append(ac)
    return saida if saida and saida[-1] > 0 else None


def _tabela_itens(tab_fisica: pd.DataFrame, envelope: float, p: config.Parametros) -> pd.DataFrame:
    """Rateia o envelope OPEX por ``Descrição Meta`` conforme o peso do item.

    Orçado do item  = envelope x (peso planejado do item / total)
    Realizado (R$)  = envelope x (peso realizado do item / total planejado)
                      -> consistente com a curva: soma dos realizados = envelope x aderência
    """
    cols_saida = ["Descrição Meta", "Unidade", "% Físico", "Orçado Planejado (R$)",
                  "Realizado (R$)", "Saldo Orçado (R$)", "% Consumo Orçado"]
    if tab_fisica.empty or "Descrição Meta" not in tab_fisica.columns:
        return pd.DataFrame(columns=cols_saida)
    t = tab_fisica.copy()

    peso_plan = t["Peso_no_Plano"].clip(lower=0)
    total_plan = peso_plan.sum()
    share_plan = peso_plan / total_plan if total_plan else peso_plan * 0

    peso_real = t.get("Peso Realizado", pd.Series(0.0, index=t.index)).clip(lower=0)
    share_real = peso_real / total_plan if total_plan else peso_real * 0

    out = pd.DataFrame({
        "Descrição Meta": t["Descrição Meta"],
        "Unidade": t.get("Unidade", pd.Series("-", index=t.index)).fillna("-"),
        "% Físico": t.get("% Realizado", np.nan),
        "Orçado Planejado (R$)": share_plan * envelope,
        "Realizado (R$)": share_real * envelope,
    })
    out["Saldo Orçado (R$)"] = out["Orçado Planejado (R$)"] - out["Realizado (R$)"]
    out["% Consumo Orçado"] = out["Realizado (R$)"] / out["Orçado Planejado (R$)"].replace(0, np.nan)
    return out.sort_values("Orçado Planejado (R$)", ascending=False)
