# -*- coding: utf-8 -*-
"""Dashboard de Manutenção - Via Permanente (Gerência Malha SP).

v2 - replicável por trimestre (parametros.xlsx) e com curva OPEX (top-down).
Toda a lógica pesada está em ``core/``; aqui só a orquestração da tela.

    streamlit run app.py
"""
import pandas as pd
import streamlit as st

from core import config, dados, fisico, financeiro, graficos

st.set_page_config(page_title="Dashboard Manutenção VP",
                   page_icon="🚂", layout="wide", initial_sidebar_state="expanded")

# --------------------------------------------------------------------------- #
# Estilo (Clean Executive - herdado da v1)
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
[data-testid="stFormSubmitButton"] button {
    background-color:#0052cc; color:#fff; border-radius:6px; font-weight:700;
    border:none; padding:8px; width:100%; transition:all .2s ease-in-out;
}
[data-testid="stFormSubmitButton"] button:hover { background-color:#003d99; transform:translateY(-2px); }
.metric-card {
    background:#fff; border-radius:10px; padding:20px; margin-bottom:16px;
    box-shadow:0 4px 6px -1px rgba(0,0,0,.1); border:1px solid #e2e8f0; border-left:6px solid #0052cc;
}
.metric-title { color:#64748b; font-size:.8rem; font-weight:700; text-transform:uppercase; margin-bottom:5px; }
.metric-value { color:#0f172a; font-size:2rem; font-weight:800; line-height:1.2; }
.metric-sub { color:#64748b; font-size:.8rem; margin-top:10px; border-top:1px solid #f1f5f9; padding-top:8px; }
.trend-adiantado { border-left-color:#10b981 !important; }
.trend-leve     { border-left-color:#f59e0b !important; }
.trend-risco    { border-left-color:#f97316 !important; }
.trend-critico  { border-left-color:#ef4444 !important; }
h1 { text-align:center; color:#1e293b; font-weight:800; }
</style>
""", unsafe_allow_html=True)


def card(titulo, valor, sub, classe=""):
    st.markdown(
        f'<div class="metric-card {classe}"><div class="metric-title">{titulo}</div>'
        f'<div class="metric-value">{valor}</div><div class="metric-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def reais(v: float) -> str:
    return ("R$ " + f"{v:,.0f}").replace(",", ".")


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Carregando plano do trimestre...")
def carregar(caminho_parametros: str):
    p = config.carregar(caminho_parametros)
    df, peso, avisos = dados.carregar_plano(p)
    return p, df, peso, avisos


PARAMS = config.ARQ_PARAMETROS
try:
    P, DF, PESO, AVISOS = carregar(PARAMS)
except Exception as e:  # noqa: BLE001
    st.error(f"🚨 Falha ao carregar os dados: {e}")
    st.info("Verifique **parametros.xlsx** (aba Config → `arquivo_plano`) e se o arquivo do "
            "trimestre está na pasta do projeto.")
    st.stop()

st.markdown("<h1>🚂 Plano de Manutenção — Via Permanente</h1>", unsafe_allow_html=True)
for a in AVISOS:
    st.warning(a)

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #
dic_tri = P.dic_trimestres
rot_default = next((k for k, v in dic_tri.items() if v == P.semanas), list(dic_tri)[0])
rot_ger = P.g("rotulo_gerencia", str, "Gerência")

with st.sidebar.form("filtros"):
    st.markdown("### ⚙️ Painel de Controle")
    tri_sel = st.selectbox("Trimestre", list(dic_tri), index=list(dic_tri).index(rot_default))
    coords = sorted(DF["Coordenação"].dropna().unique().tolist()) if "Coordenação" in DF else []
    coord = st.selectbox("Visão / Coordenação", [rot_ger] + coords)
    equipes = sorted(DF["Equipe"].dropna().unique().tolist()) if "Equipe" in DF else []
    eq_sel = st.multiselect("Equipes (opcional)", equipes)
    itens = sorted(DF["Descrição Meta"].dropna().unique().tolist()) if "Descrição Meta" in DF else []
    it_sel = st.multiselect("Itens de manutenção (opcional)", itens)
    ver_ref = st.checkbox("Mostrar referências oficiais (orçamento / SAP)", value=True)
    st.form_submit_button("🚀 Aplicar")

    st.caption(f"Config: **{P.origem}** · Coordenações na visão Gerência: **{P.n_coord_gerencia}**")

sem_ini, sem_fim = dic_tri[tri_sel]

base = DF.copy()
if coord != rot_ger:
    base = base[base["Coordenação"] == coord]
if eq_sel:
    base = base[base["Equipe"].isin(eq_sel)]
if it_sel:
    base = base[base["Descrição Meta"].isin(it_sel)]

# --------------------------------------------------------------------------- #
# Cálculo
# --------------------------------------------------------------------------- #
RF = fisico.calcular(base, P, coord, sem_ini, sem_fim)
FIN = financeiro.calcular(P, coord, sem_ini, sem_fim,
                          RF.curva, RF.tabela_itens, RF.semana_atual)

k = RF.kpis
c1, c2, c3 = st.columns(3)
with c1:
    card("📅 Último preenchimento", k["ultimo_preenchimento"],
         f"Semanas executadas: <b>{k['semanas_executadas']}</b>")
with c2:
    card("🚀 Aderência atual", f"{k['aderencia_atual']*100:.1f}%",
         f"Acumulado até a semana {RF.semana_atual}")
with c3:
    card("🎯 Projeção de fechamento", k["tendencia"],
         f"Alvo da sem. {sem_fim}: <b>{k['aderencia_projetada']*100:.1f}%</b> · "
         f"mín. semanal p/ meta: <b>{k['minimo_semanal_para_meta']*100:.2f}%</b>",
         k["classe_tendencia"])

# --------------------------------------------------------------------------- #
# Abas
# --------------------------------------------------------------------------- #
sem_dados = float(pd.to_numeric(RF.curva["meta_pcm"], errors="coerce").max() or 0) == 0 and \
    float(pd.to_numeric(RF.curva["realizado"], errors="coerce").max() or 0) == 0
if sem_dados:
    st.warning("Não há plano nem execução para este trimestre/filtro. "
               "Confira **parametros.xlsx** (aba Config → `trimestre` / `arquivo_plano`).")

aba_fis, aba_fin, aba_sobre = st.tabs(["📈 Físico", "💰 Financeiro (OPEX)", "ℹ️ Como funciona"])

with aba_fis:
    st.altair_chart(graficos.curva_fisica(RF.curva, RF.semana_atual), width='stretch')
    st.markdown("#### 📋 Resumo por atividade")
    tab = RF.tabela_itens.rename(columns={"Peso_no_Plano": "Peso no Plano"})
    cols = [c for c in ["Descrição Meta", "Plano", "Unidade", "SLA", "Dias de Equipe",
                        "Qtd. Realizado", "Realizado (Extra Plano)", "Pendente",
                        "% Realizado", "Peso no Plano"] if c in tab.columns]
    if tab.empty or not cols:
        st.caption("Sem atividades para exibir.")
    else:
        st.dataframe(
            tab[cols].style.format({"% Realizado": "{:.1%}", "Peso no Plano": "{:.2%}",
                                    "Plano": "{:,.1f}", "Qtd. Realizado": "{:,.1f}",
                                    "Realizado (Extra Plano)": "{:,.1f}", "Pendente": "{:,.1f}"})
            .background_gradient(subset=["% Realizado"], cmap="Blues", vmin=0, vmax=1),
            width='stretch', hide_index=True,
        )

with aba_fin:
    if not FIN.disponivel:
        st.info("💡 " + (FIN.aviso or "Curva financeira indisponível para esta seleção."))
    else:
        e1, e2, e3 = st.columns(3)
        with e1:
            card("💵 Envelope orçado (período)", reais(FIN.envelope_orcado),
                 f"OPEX manutenção · {coord}")
        with e2:
            card("📊 Realizado do plano (R$)", reais(FIN.envelope_orcado * k["aderencia_atual"]),
                 f"{k['aderencia_atual']*100:.1f}% do envelope (ritmo físico)")
        with e3:
            proj = FIN.envelope_orcado * k["aderencia_projetada"]
            card("🔮 Projeção de fechamento (R$)", reais(proj),
                 f"{k['aderencia_projetada']*100:.1f}% do envelope",
                 k["classe_tendencia"])
        st.altair_chart(graficos.curva_financeira(FIN.curva, RF.semana_atual, ver_ref),
                        width='stretch')
        st.markdown("#### 🧾 OPEX rateado por item")
        if FIN.tabela_itens is None or FIN.tabela_itens.empty:
            st.caption("Sem itens no período.")
        else:
            st.dataframe(
                FIN.tabela_itens.style.format({
                    "Orçado Planejado (R$)": "R$ {:,.0f}", "Realizado (R$)": "R$ {:,.0f}",
                    "Saldo Orçado (R$)": "R$ {:,.0f}", "% Consumo Orçado": "{:.1%}",
                    "% Físico": "{:.1%}"})
                .background_gradient(subset=["% Consumo Orçado"], cmap="Oranges", vmin=0, vmax=1.2),
                width='stretch', hide_index=True,
            )
        st.caption("Modelo top-down: envelope da aba **PLAN ORÇ** (Orçamento Ger. SP) × curva física, "
                   "rateado por item conforme o peso planejado. R$/item é aproximação contábil.")

with aba_sobre:
    st.markdown(f"""
**Fonte dos dados**
- Físico: aba `{P.g('aba_diario', str, 'Diário')}` + `{P.g('aba_peso', str, 'Planilha de Peso')}` de
  **{P.g('arquivo_plano', str, '')}** (o que os colaboradores preenchem).
- Financeiro: aba `{P.g('aba_plan_orc', str, 'PLAN ORÇ')}` de **{P.g('arquivo_orcamento', str, '')}**.

**Curvas físicas**
- **Meta PCM** — soma acumulada do `Peso Planejado Linha` (origem PCM){' ÷ nº de coordenações' if coord == rot_ger else ''}.
- **Realizado** — `Peso Realizado Linha` das linhas com `Plano = {P.g('plano_sim', str, 'Sim')}` e origem `{P.g('origem_execucao', str, 'Coordenação')}`.
- **Projeção** — realizado até a semana atual + ritmo médio × semanas restantes.

**Curvas financeiras (top-down)**
- **Orçado Planejado** = envelope OPEX do período × curva Meta PCM.
- **Realizado** = envelope × aderência física realizada.
- **Projetado** = envelope × projeção física.
- **Orçamento OPEX oficial** / **Realizado contábil SAP** = curvas mensais da PLAN ORÇ (referência).

**Trocar de trimestre:** editar **parametros.xlsx** → aba `Config` (`trimestre`, `arquivo_plano`).
Nada de código. Config atual carregada de: **{P.origem}**.
""")
