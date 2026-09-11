# -*- coding: utf-8 -*-
"""Núcleo do Dashboard de Manutenção - Via Permanente (Gerência Malha SP).

Módulos:
    config      -> lê ``parametros.xlsx`` (com defaults embutidos).
    dados       -> carga do plano do trimestre (aba Diário + Planilha de Peso).
    fisico      -> curvas físicas (Meta PCM / Realizado / Projeção) e KPIs.
    financeiro  -> curva OPEX top-down (envelope da PLAN ORÇ rateado por peso).
    graficos    -> specs Altair (substitui o streamlit-echarts, incompatível com o Streamlit atual).
"""

from . import config, dados, fisico, financeiro, graficos  # noqa: F401

__all__ = ["config", "dados", "fisico", "financeiro", "graficos"]
