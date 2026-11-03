# -*- coding: utf-8 -*-
"""Gráficos em Altair (já incluso no Streamlit).

Substitui o ``streamlit-echarts``, que está quebrado com a versão de Streamlit
usada no deploy / Python portátil.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

AZUL = "#0052cc"
VERDE = "#10b981"
AMBAR = "#f59e0b"
CINZA = "#94a3b8"
ROXO = "#7c3aed"

alt.data_transformers.disable_max_rows()


def _base(df_long: pd.DataFrame, y_title: str, y_format: str, dominio_cores: dict):
    ordem = list(dominio_cores.keys())
    cor = alt.Color("Série:N", scale=alt.Scale(domain=ordem, range=[dominio_cores[k] for k in ordem]),
                    legend=alt.Legend(orient="top", title=None))
    dash = alt.StrokeDash("Série:N",
                          scale=alt.Scale(domain=ordem,
                                          range=[[6, 4] if "Proje" in k else [1, 0] for k in ordem]),
                          legend=None)
    x = alt.X("Semana:O", title="Semana", axis=alt.Axis(labelAngle=0))
    y = alt.Y("Valor:Q", title=y_title, axis=alt.Axis(format=y_format))

    linha = (alt.Chart(df_long).mark_line(strokeWidth=3, point=alt.OverlayMarkDef(size=45))
             .encode(x=x, y=y, color=cor, strokeDash=dash,
                     tooltip=[alt.Tooltip("Série:N"), alt.Tooltip("Semana:O"),
                              alt.Tooltip("Valor:Q", format=y_format, title=y_title)]))
    return linha


def curva_fisica(curva: pd.DataFrame, semana_atual: int) -> alt.Chart:
    d = curva.rename(columns={"meta_pcm": "Meta PCM", "realizado": "Realizado",
                              "projecao": "Projeção (Ritmo)"})
    long = d.melt("Semana", value_vars=["Meta PCM", "Realizado", "Projeção (Ritmo)"],
                  var_name="Série", value_name="Valor").dropna(subset=["Valor"])
    ch = _base(long, "Aderência", "%", {"Meta PCM": AZUL, "Realizado": VERDE, "Projeção (Ritmo)": AMBAR})
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch + regua).properties(height=460).configure_view(strokeOpacity=0)


def curvas_coordenacoes(curvas: dict[str, pd.DataFrame], semana_atual: int) -> alt.Chart:
    """Realizado acumulado de cada coordenação (linha cheia) x Meta PCM dela (tracejada)."""
    partes = []
    for coord, c in curvas.items():
        for col, tipo in (("realizado", "Realizado"), ("meta_pcm", "Meta PCM")):
            d = c[["Semana", col]].rename(columns={col: "Valor"}).dropna()
            d["Coordenação"], d["Tipo"] = coord, tipo
            partes.append(d)
    if not partes:
        return alt.Chart(pd.DataFrame({"Semana": [], "Valor": []})).mark_line()
    long = pd.concat(partes, ignore_index=True)
    ch = (alt.Chart(long).mark_line(strokeWidth=2.5)
          .encode(x=alt.X("Semana:O", axis=alt.Axis(labelAngle=0)),
                  y=alt.Y("Valor:Q", title="Aderência acumulada", axis=alt.Axis(format="%")),
                  color=alt.Color("Coordenação:N", legend=alt.Legend(orient="top", title=None)),
                  strokeDash=alt.StrokeDash("Tipo:N", scale=alt.Scale(domain=["Realizado", "Meta PCM"],
                                                                      range=[[1, 0], [6, 4]]),
                                            legend=alt.Legend(orient="top", title=None)),
                  tooltip=["Coordenação:N", "Tipo:N", "Semana:O", alt.Tooltip("Valor:Q", format=".1%")]))
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch + regua).properties(height=420).configure_view(strokeOpacity=0)


def evolucao(hist: pd.DataFrame, valor: str = "Aderência", titulo: str = "Aderência") -> alt.Chart:
    """Barras agrupadas por período (trimestre ou ano) x visão (Gerência/coordenações)."""
    base = alt.Chart(hist).encode(
        x=alt.X("Período:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        xOffset="Visão:N",
        y=alt.Y(f"{valor}:Q", title=titulo, axis=alt.Axis(format="%")),
        color=alt.Color("Visão:N", legend=alt.Legend(orient="top", title=None)),
        tooltip=["Período:N", "Visão:N", alt.Tooltip(f"{valor}:Q", format=".1%")])
    barras = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    meta = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(color=CINZA, strokeDash=[4, 4]).encode(y="y:Q")
    return (barras + meta).properties(height=380).configure_view(strokeOpacity=0)


def curva_financeira(curva: pd.DataFrame, semana_atual: int, mostrar_ref: bool = True) -> alt.Chart:
    ren = {"orcado_plan": "Orçado Planejado", "realizado": "Realizado",
           "projetado": "Projetado", "ref_orcado": "Orçamento OPEX oficial",
           "ref_realizado": "Realizado contábil SAP"}
    d = curva.rename(columns=ren)
    series = ["Orçado Planejado", "Realizado", "Projetado"]
    cores = {"Orçado Planejado": AZUL, "Realizado": VERDE, "Projetado": AMBAR}
    if mostrar_ref and "Orçamento OPEX oficial" in d.columns:
        series += ["Orçamento OPEX oficial", "Realizado contábil SAP"]
        cores["Orçamento OPEX oficial"] = CINZA
        cores["Realizado contábil SAP"] = ROXO
    long = d.melt("Semana", value_vars=series, var_name="Série", value_name="Valor").dropna(subset=["Valor"])
    ch = _base(long, "R$ acumulado", "$,.0f", cores)
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch + regua).properties(height=460).configure_view(strokeOpacity=0)
