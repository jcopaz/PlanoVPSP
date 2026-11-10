# core/ui.py — Estilo e componentes visuais compartilhados pelas telas
# Paleta no padrão do Sentinel (azul-marinho #1e3a5f + dourado #e8a920) e os
# cartões de KPI herdados da v2 (borda colorida pela tendência).

import pandas as pd
import streamlit as st

CSS_GLOBAL = """
<style>
.stApp { background-color: #f8fafc; }
[data-testid="stHeader"] { background: transparent; }
.main .block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.6rem; padding-bottom: 3rem; }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 100%) !important; color: #fff !important;
    border: none !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stTabs [data-baseweb="tab"] { font-weight: 500; color: #6b7280; }
.stTabs [aria-selected="true"] { color: #1e3a5f !important; font-weight: 600 !important; }
@media (max-width: 992px) {
    .stTabs [data-baseweb="tab-list"] { overflow-x: auto; flex-wrap: nowrap; }
}
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.stAlert { border-radius: 10px !important; }
h1 a, h2 a, h3 a, h4 a { display: none !important; }

.metric-card { background:#fff; border-radius:10px; padding:16px 18px; margin-bottom:12px;
    box-shadow:0 4px 6px -1px rgba(0,0,0,.08); border:1px solid #e2e8f0; border-left:6px solid #1e3a5f; }
.metric-title { color:#64748b; font-size:.75rem; font-weight:700; text-transform:uppercase; margin-bottom:4px; }
.metric-value { color:#0f172a; font-size:1.7rem; font-weight:800; line-height:1.2; }
.metric-sub { color:#64748b; font-size:.78rem; margin-top:8px; border-top:1px solid #f1f5f9; padding-top:6px; }
.trend-adiantado { border-left-color:#10b981 !important; }
.trend-leve     { border-left-color:#f59e0b !important; }
.trend-risco    { border-left-color:#f97316 !important; }
.trend-critico  { border-left-color:#ef4444 !important; }
.titulo-tela { color:#1e3a5f; font-weight:800; font-size:1.6rem; margin:0 0 .2rem; }
.sub-tela { color:#64748b; font-size:.9rem; margin:0 0 1rem; }

[data-testid="stSidebar"] { background: #1b2130; }
[data-testid="stSidebar"] * { color: #e5e7eb; }
[data-testid="stSidebar"] .stButton > button { background: transparent; border: 1px solid rgba(255,255,255,.12);
    color: #e5e7eb !important; text-align: left; justify-content: flex-start; border-radius: 8px; }
[data-testid="stSidebar"] .stButton > button:hover { border-color: #e8a920; color: #e8a920 !important; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] { background: #2d5a8e !important; border: none; }
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #0f172a; }
.sb-marca { color:#e8a920; font-family:'Arial Black',Arial,sans-serif; font-size:1.35rem; letter-spacing:.06em; }
.sb-badge { background: rgba(255,255,255,.06); border-radius: 10px; padding: 8px 10px; font-size: .8rem; margin: 6px 0 10px; }
</style>
"""


def injetar_css() -> None:
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


def titulo(texto: str, sub: str = "") -> None:
    st.markdown(f'<p class="titulo-tela">{texto}</p>' + (f'<p class="sub-tela">{sub}</p>' if sub else ""),
                unsafe_allow_html=True)


def card(titulo_card: str, valor: str, sub: str = "", classe: str = "") -> None:
    st.markdown(
        f'<div class="metric-card {classe}"><div class="metric-title">{titulo_card}</div>'
        f'<div class="metric-value">{valor}</div>'
        + (f'<div class="metric-sub">{sub}</div>' if sub else "") + "</div>",
        unsafe_allow_html=True)


def pct(v, casas: int = 2) -> str:
    try:
        return f"{float(v) * 100:.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "-"


def reais(v: float, casas: int = 0) -> str:
    """657389.4 -> "R$ 657.389" (casas=2: "R$ 657.389,40")."""
    if v is None or pd.isna(v):
        return ""
    return "R$ " + f"{v:,.{casas}f}".translate(str.maketrans(",.", ".,"))
