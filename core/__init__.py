# -*- coding: utf-8 -*-
"""Núcleo do Dashboard de Manutenção - Via Permanente (Gerência Malha SP).

Módulos:
    config      -> lê ``parametros.xlsx`` (com defaults embutidos).
    modelo      -> layout do modelo de planilha v3 (Pesos / Plano_PCM / Lancamentos).
    dados       -> carga do plano do trimestre (modelo v3 ou Diário + Planilha de Peso antigos).
    fisico      -> curvas físicas (Meta PCM / Realizado / Projeção) e KPIs.
    financeiro  -> curva OPEX top-down (envelope da PLAN ORÇ rateado por peso).
    graficos    -> specs Altair (substitui o streamlit-echarts, incompatível com o Streamlit atual).
"""

from . import config, modelo, dados, fisico, financeiro, graficos  # noqa: F401

__all__ = ["config", "modelo", "dados", "fisico", "financeiro", "graficos"]
