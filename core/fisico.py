# -*- coding: utf-8 -*-
"""Curvas FÍSICAS: Meta PCM, Realizado e Projeção (ritmo médio) + KPIs.

É a mesma lógica da v1, isolada e parametrizada (nº de coordenações da visão
Gerência, janela de semanas e faixas de risco vêm do parametros.xlsx).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config


@dataclass
class ResultadoFisico:
    curva: pd.DataFrame            # Semana | meta_pcm | realizado | projecao  (0..1, acumulado)
    tabela_itens: pd.DataFrame     # por Descrição Meta
    kpis: dict
    semana_atual: int
    divisor: int                   # 1 (coordenação) ou nº de coordenações (Gerência)


def _filtra_visao(df, p, coord):
    base = df.copy()
    if coord != p.g("rotulo_gerencia", str, "Gerência") and "Coordenação" in base.columns:
        base = base[base["Coordenação"] == coord]
    return base


def _peso_realizado_limitado(exec_sim: pd.DataFrame) -> pd.DataFrame:
    """Peso realizado por Chave Peso x Semana com TETO no plano da meta (regra do PCM:
    fazer 132 de 40 conta 40). Acumula semana a semana e só credita até o Plano Trimestral."""
    cols = ["Chave Peso", "Semana", "peso"]
    if exec_sim.empty or "Plano Trimestral" not in exec_sim.columns:
        return exec_sim.assign(peso=exec_sim.get("Peso Realizado Linha", 0.0)).reindex(columns=cols)
    g = (exec_sim.groupby(["Chave Peso", "Semana"], as_index=False)["QUANTIDADE REALIZADA"].sum()
         .sort_values(["Chave Peso", "Semana"]))
    plano = exec_sim.groupby("Chave Peso")["Plano Trimestral"].first()
    pu = exec_sim.groupby("Chave Peso")["Peso Unitário"].first()
    acum = g.groupby("Chave Peso")["QUANTIDADE REALIZADA"].cumsum()
    lim = np.minimum(acum, pd.to_numeric(g["Chave Peso"].map(plano), errors="coerce").fillna(0.0))
    inc = lim - lim.groupby(g["Chave Peso"]).shift(fill_value=0.0)
    g["peso"] = inc * pd.to_numeric(g["Chave Peso"].map(pu), errors="coerce").fillna(0.0)
    return g[cols]


def calcular(df, p: config.Parametros, coord: str, sem_ini: int, sem_fim: int) -> ResultadoFisico:
    rot_ger = p.g("rotulo_gerencia", str, "Gerência")
    o_pcm = p.g("origem_pcm", str, "PCM")
    o_exec = p.g("origem_execucao", str, "Coordenação")
    s_sim = p.g("plano_sim", str, "Sim")

    divisor = p.n_coord_gerencia if coord == rot_ger else 1
    base = _filtra_visao(df, p, coord)
    base = base[base["Semana"].between(0, sem_fim)]

    # ---- Meta PCM (planejado) ------------------------------------------- #
    pcm = base[base["Origem Programação"] == o_pcm]
    meta_sem = (pcm.groupby("Semana")["Peso Planejado Linha"].sum() / divisor).cumsum()

    # ---- Realizado (execução dentro do plano) -------------------------- #
    exec_sim = base[(base["Origem Programação"] == o_exec) & (base["Plano"] == s_sim)].copy()
    real_sem = (_peso_realizado_limitado(exec_sim).groupby("Semana")["peso"].sum() / divisor)

    semanas = pd.DataFrame({"Semana": range(sem_ini, sem_fim + 1)})
    real_sem = semanas.merge(real_sem.rename("peso").reset_index(), on="Semana", how="left").fillna(0.0)
    real_sem["acum"] = real_sem["peso"].cumsum()

    semana_atual = int(exec_sim["Semana"].max()) if not exec_sim.empty else sem_ini
    semana_atual = min(max(semana_atual, sem_ini), sem_fim)
    real_acum_atual = float(
        real_sem.loc[real_sem["Semana"] == semana_atual, "acum"].pipe(
            lambda s: s.iloc[0] if len(s) else 0.0
        )
    )
    semanas_exec = semana_atual - sem_ini + 1
    ritmo = real_acum_atual / semanas_exec if semanas_exec > 0 else 0.0

    def valor(sem):
        if sem <= semana_atual:
            v = real_sem.loc[real_sem["Semana"] == sem, "acum"]
            return round(float(v.iloc[0]), 6) if len(v) else 0.0
        return round(real_acum_atual + ritmo * (sem - semana_atual), 6)

    curva = pd.DataFrame({"Semana": list(range(sem_ini, sem_fim + 1))})
    curva["realizado"] = curva["Semana"].apply(lambda s: valor(s) if s <= semana_atual else np.nan)
    curva["projecao"] = curva["Semana"].apply(lambda s: valor(s) if s >= semana_atual else np.nan)

    meta_vals, ult = [], 0.0
    for s in curva["Semana"]:
        if s in meta_sem.index:
            ult = float(meta_sem.loc[s])
        meta_vals.append(round(ult, 6))
    curva["meta_pcm"] = meta_vals

    # ---- KPIs ---------------------------------------------------------- #
    aderencia_proj = valor(sem_fim)
    meta = p.g("meta_aderencia", float, 1.0)
    gap = meta - aderencia_proj
    restantes = max(0, sem_fim - semana_atual)
    f_leve, f_risco, f_crit = (p.g("faixa_leve", float, .05),
                               p.g("faixa_risco", float, .10),
                               p.g("faixa_critico", float, .15))
    if aderencia_proj == 0:
        tend = "Aguardando Lançamentos" if max(meta_vals, default=0) > 0 else "Sem Planejamento"
        classe = ""
    elif restantes <= 0:
        ok = aderencia_proj >= meta
        tend = "Concluído: Meta Atingida" if ok else "Concluído: Meta Não Atingida"
        classe = "trend-adiantado" if ok else "trend-critico"
    elif aderencia_proj >= meta:
        tend, classe = "Adiantado (Meta Garantida)", "trend-adiantado"
    elif gap > f_crit:
        tend, classe = f"Atraso Crítico (>{f_crit:.0%})", "trend-critico"
    elif gap > f_risco:
        tend, classe = f"Risco Alto ({f_risco:.0%}-{f_crit:.0%})", "trend-risco"
    elif gap > f_leve:
        tend, classe = f"Em Risco ({f_leve:.0%}-{f_risco:.0%})", "trend-risco"
    else:
        tend, classe = f"Leve Desvio (<{f_leve:.0%})", "trend-leve"

    mask_preench = ((base["Origem Programação"] == o_exec) & (base["Plano"] == s_sim)
                    & (base["QUANTIDADE REALIZADA"] > 0))
    ult_data = base.loc[mask_preench, "Data Planejada"].max() if "Data Planejada" in base.columns else pd.NaT

    kpis = {
        "ultimo_preenchimento": ult_data.strftime("%d/%m/%Y") if pd.notnull(ult_data) else "Sem registros",
        "semanas_executadas": semanas_exec,
        "aderencia_atual": real_acum_atual,
        "aderencia_projetada": aderencia_proj,
        "ritmo_medio": ritmo,
        "gap": gap,
        "semanas_restantes": restantes,
        "tendencia": tend,
        "classe_tendencia": classe,
        "minimo_semanal_para_meta": (gap / restantes) if restantes > 0 else 0.0,
    }

    # ---- Tabela por atividade (físico) ------------------------------- #
    tab = _tabela_itens(base, p, sem_fim, divisor)

    return ResultadoFisico(curva=curva, tabela_itens=tab, kpis=kpis,
                           semana_atual=semana_atual, divisor=divisor)


def _tabela_itens(base, p, sem_fim, divisor: int = 1) -> pd.DataFrame:
    o_pcm = p.g("origem_pcm", str, "PCM")
    o_exec = p.g("origem_execucao", str, "Coordenação")
    s_sim, s_nao = p.g("plano_sim", str, "Sim"), p.g("plano_nao", str, "Não")

    pcm = base[base["Origem Programação"] == o_pcm]
    res_pcm = (pcm.groupby("Descrição Meta")
               .agg(Plano=("Quantidade Programada", "sum"),
                    Peso_no_Plano=("Peso Planejado Linha", "sum"))
               .reset_index())

    reals = base[(base["Origem Programação"] == o_exec) & (base["Plano"] == s_sim)]
    agg = {"QUANTIDADE REALIZADA": "sum", "Peso Realizado Linha": "sum"}
    if "Data Planejada" in reals.columns:
        agg["Data Planejada"] = "nunique"
    for c in ("Unidade", "SLA"):
        if c in reals.columns:
            agg[c] = "first"
    res_real = reals.groupby("Descrição Meta").agg(agg).reset_index().rename(
        columns={"QUANTIDADE REALIZADA": "Qtd. Realizado",
                 "Data Planejada": "Dias de Equipe",
                 "Peso Realizado Linha": "Peso Realizado"})

    extra = base[(base["Origem Programação"] == o_exec) & (base["Plano"] == s_nao)]
    res_extra = (extra.groupby("Descrição Meta")
                 .agg(**{"Realizado (Extra Plano)": ("QUANTIDADE REALIZADA", "sum")})
                 .reset_index())

    # Peso realizado com teto no plano de cada Depto|Meta (mesma regra da curva)
    lim = _peso_realizado_limitado(reals)
    if not lim.empty:
        meta_da_chave = reals.drop_duplicates("Chave Peso").set_index("Chave Peso")["Descrição Meta"]
        res_real["Peso Realizado"] = res_real["Descrição Meta"].map(
            lim.groupby(lim["Chave Peso"].map(meta_da_chave))["peso"].sum()).fillna(0.0)
    tab = res_pcm.merge(res_real, on="Descrição Meta", how="outer")
    tab = tab.merge(res_extra, on="Descrição Meta", how="outer")
    num = tab.select_dtypes("number").columns
    tab[num] = tab[num].fillna(0.0)
    tab["Pendente"] = (tab["Plano"] - tab["Qtd. Realizado"]).clip(lower=0)
    tab["% Realizado"] = tab["Qtd. Realizado"] / tab["Plano"].replace(0, np.nan)
    # SLA = produção esperada da equipe por dia -> dias de equipe que faltam
    sla = pd.to_numeric(tab["SLA"], errors="coerce") if "SLA" in tab.columns else pd.Series(np.nan, index=tab.index)
    tab["Dias Equipe p/ Concluir"] = np.ceil(tab["Pendente"] / sla.where(sla > 0))
    # Visão por material na regra do PCM: aderência com teto e quanto cada meta soma na visão.
    # Σ Contribuição = aderência da visão (coordenação, ou Gerência = ÷ nº de coordenações).
    if "Peso Realizado" not in tab.columns:
        tab["Peso Realizado"] = 0.0
    tab["Aderência PCM"] = (tab["Peso Realizado"] / tab["Peso_no_Plano"].replace(0, np.nan)).clip(upper=1)
    tab["Peso na Visão"] = tab["Peso_no_Plano"] / divisor
    tab["Contribuição"] = np.minimum(tab["Peso Realizado"], tab["Peso_no_Plano"]) / divisor
    return tab.sort_values("Peso_no_Plano", ascending=False)
