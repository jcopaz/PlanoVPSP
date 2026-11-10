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


def pct_br(v: pd.Series) -> pd.Series:
    """0.30756 -> "30,8%" (rótulos em português; o formato "%" do Vega sai com 6 casas)."""
    return v.map(lambda x: "" if pd.isna(x) else f"{x * 100:.1f}%".replace(".", ","))


def _rotulos(df: pd.DataFrame, x, cor, abaixo: set[str], campo: str, grupo: list[str]) -> alt.LayerChart:
    """Texto com o valor de cada ponto; séries em ``abaixo`` ficam sob o ponto (não encavalam).
    Só escreve quando o valor muda em relação à semana anterior da mesma linha, e nunca 0%."""
    df = df.sort_values([*grupo, "Semana"])
    df = df[(df["Rótulo"] != df.groupby(grupo)["Rótulo"].shift()) & (df["Valor"] >= 0.0005)]
    camadas = []
    for dados, dy in ((df[~df[campo].isin(abaixo)], -11), (df[df[campo].isin(abaixo)], 15)):
        if not dados.empty:
            camadas.append(alt.Chart(dados).mark_text(fontSize=10, fontWeight="bold", dy=dy)
                           .encode(x=x, y="Valor:Q", text="Rótulo:N", color=cor))
    return alt.layer(*camadas) if camadas else alt.layer(alt.Chart(df).mark_text())


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
    long["Rótulo"] = pct_br(long["Valor"])
    cores = {"Meta PCM": AZUL, "Realizado": VERDE, "Projeção (Ritmo)": AMBAR}
    ch = _base(long, "Aderência", ".0%", cores)
    # a projeção começa no último realizado: sem rótulo repetido nessa semana
    txt = long[~((long["Série"] == "Projeção (Ritmo)") & (long["Semana"] == semana_atual))]
    cor = alt.Color("Série:N", scale=alt.Scale(domain=list(cores), range=list(cores.values())), legend=None)
    rot = _rotulos(txt, alt.X("Semana:O"), cor, {"Realizado"}, "Série", ["Série"])
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch.encode(tooltip=["Série:N", "Semana:O", alt.Tooltip("Rótulo:N", title="Aderência")]) + rot + regua) \
        .properties(height=460).configure_view(strokeOpacity=0)


def curvas_coordenacoes(curvas: dict[str, pd.DataFrame], semana_atual: int,
                        tipos=("Realizado", "Meta PCM"), todas: list[str] | None = None) -> alt.Chart:
    """Realizado acumulado de cada coordenação (linha cheia) x Meta PCM dela (tracejada).
    ``tipos``: linhas a mostrar; ``todas``: coordenações existentes (mantém a cor de cada uma
    ao filtrar). Valor escrito em cada ponto: Realizado acima, Meta PCM abaixo."""
    partes = []
    for coord, c in curvas.items():
        for col, tipo in (("realizado", "Realizado"), ("meta_pcm", "Meta PCM")):
            if tipo not in tipos:
                continue
            d = c[["Semana", col]].rename(columns={col: "Valor"}).dropna()
            d["Coordenação"], d["Tipo"] = coord, tipo
            partes.append(d)
    if not partes:
        return alt.Chart(pd.DataFrame({"Semana": [], "Valor": []})).mark_line()
    long = pd.concat(partes, ignore_index=True)
    long["Rótulo"] = pct_br(long["Valor"])
    x = alt.X("Semana:O", axis=alt.Axis(labelAngle=0))
    cor = alt.Color("Coordenação:N", legend=alt.Legend(orient="top", title=None),
                    scale=alt.Scale(domain=todas or list(curvas)))
    ch = (alt.Chart(long).mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=30))
          .encode(x=x,
                  y=alt.Y("Valor:Q", title="Aderência acumulada", axis=alt.Axis(format=".0%")),
                  color=cor,
                  strokeDash=alt.StrokeDash("Tipo:N", scale=alt.Scale(domain=["Realizado", "Meta PCM"],
                                                                      range=[[1, 0], [6, 4]]),
                                            legend=alt.Legend(orient="top", title=None)),
                  tooltip=["Coordenação:N", "Tipo:N", "Semana:O", alt.Tooltip("Rótulo:N", title="Aderência")]))
    rot = _rotulos(long, x, cor, {"Meta PCM"}, "Tipo", ["Coordenação", "Tipo"])
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch + rot + regua).properties(height=460).configure_view(strokeOpacity=0)


def evolucao(hist: pd.DataFrame, valor: str = "Aderência", titulo: str = "Aderência") -> alt.Chart:
    """Barras agrupadas por período (trimestre ou ano) x visão (Gerência/coordenações),
    com o percentual escrito na base de cada barra (dispensa a tabela)."""
    hist = hist.assign(Rótulo=pct_br(hist[valor]))
    x = alt.X("Período:N", sort=None, title=None, axis=alt.Axis(labelAngle=0))
    base = alt.Chart(hist).encode(
        x=x, xOffset="Visão:N",
        y=alt.Y(f"{valor}:Q", title=titulo, axis=alt.Axis(format=".0%")),
        color=alt.Color("Visão:N", legend=alt.Legend(orient="top", title=None)),
        tooltip=["Período:N", "Visão:N", alt.Tooltip("Rótulo:N", title=titulo)])
    barras = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    # texto na base da barra: branco dentro da barra; escuro acima de barra baixa
    rotulo = (alt.Chart(hist).mark_text(fontSize=11, fontWeight="bold", baseline="bottom", dy=-4)
              .encode(x=x, xOffset="Visão:N", y=alt.datum(0), text="Rótulo:N",
                      color=alt.condition(f"datum['{valor}'] >= 0.12", alt.value("white"), alt.value("#1e293b"))))
    meta = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(color=CINZA, strokeDash=[4, 4]).encode(y="y:Q")
    return (barras + rotulo + meta).properties(height=380).configure_view(strokeOpacity=0)


SERIES_FINANCEIRAS = ["Orçado Planejado", "Realizado", "Projetado", "Orçamento OPEX oficial", "Realizado contábil SAP"]


def curva_financeira(curva: pd.DataFrame, semana_atual: int, series: list[str] | None = None) -> alt.Chart:
    """``series``: linhas a mostrar (padrão: todas as disponíveis)."""
    ren = {"orcado_plan": "Orçado Planejado", "realizado": "Realizado",
           "projetado": "Projetado", "ref_orcado": "Orçamento OPEX oficial",
           "ref_realizado": "Realizado contábil SAP"}
    d = curva.rename(columns=ren)
    todas = {"Orçado Planejado": AZUL, "Realizado": VERDE, "Projetado": AMBAR,
             "Orçamento OPEX oficial": CINZA, "Realizado contábil SAP": ROXO}
    cores = {k: v for k, v in todas.items() if k in d.columns and (series is None or k in series)}
    long = d.melt("Semana", value_vars=list(cores), var_name="Série", value_name="Valor").dropna(subset=["Valor"])
    ch = _base(long, "R$ acumulado", "$,.0f", cores)
    regua = (alt.Chart(pd.DataFrame({"Semana": [semana_atual]}))
             .mark_rule(color=CINZA, strokeDash=[3, 3]).encode(x="Semana:O"))
    return (ch + regua).properties(height=460).configure_view(strokeOpacity=0)
