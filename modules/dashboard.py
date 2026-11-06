# modules/dashboard.py — Resultado do plano do trimestre ativo
#
# Abre sempre no trimestre corrente (comum.trimestre_corrente); outro trimestre
# só por escolha no menu lateral, com aviso e botão para voltar.
#
# Abas:
#   Resumo           cartões da Gerência + 1 cartão por coordenação + quadro-resumo
#   Gerencial        curva da Gerência, curvas das coordenações lado a lado, atividades
#   Por Coordenação  curva + atividades (SLA, dias de equipe p/ concluir) + motivos
#   Financeiro       curva OPEX top-down (precisa do Orçamento Ger. SP.xlsx)
#   Evolução         aderência por trimestre e por ano (histórico do banco)
# Regras de cálculo: core/fisico.py (curvas/KPIs) e core/financeiro.py (OPEX).

import pandas as pd
import streamlit as st

from auth.session import get_depto
from core import financeiro, fisico, graficos, motor
from core.ui import card, pct, reais, titulo
from modules import comum

FMT_PCT = st.column_config.NumberColumn(format="percent")


# region ====================== SESSÃO 1: Blocos reutilizáveis ======================

def _cartoes(rf: fisico.ResultadoFisico, sem_fim: int) -> None:
    k = rf.kpis
    meta = rf.curva.loc[rf.curva["Semana"] == rf.semana_atual, "meta_pcm"]
    meta = float(meta.iloc[0]) if len(meta) else 0.0
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("🚀 Aderência do trimestre", pct(k["aderencia_atual"]),
             f"Meta PCM até a sem. {rf.semana_atual}: <b>{pct(meta)}</b>")
    with c2:
        card("🎯 Projeção de fechamento", pct(k["aderencia_projetada"]),
             f"{k['tendencia']} · alvo sem. {sem_fim}", k["classe_tendencia"])
    with c3:
        card("📈 Mín. semanal p/ meta", pct(k["minimo_semanal_para_meta"], 2),
             f"Ritmo médio atual: <b>{pct(k['ritmo_medio'], 2)}</b>/sem")
    with c4:
        card("📅 Último lançamento", k["ultimo_preenchimento"],
             f"Semanas executadas: <b>{k['semanas_executadas']}</b>")


def _tabela_atividades(tab: pd.DataFrame) -> None:
    cols = [c for c in ["Descrição Meta", "Unidade", "SLA", "Plano", "Qtd. Realizado", "Aderência PCM",
                        "Peso na Visão", "Contribuição", "% Realizado", "Pendente", "Dias Equipe p/ Concluir",
                        "Dias de Equipe", "Realizado (Extra Plano)"] if c in tab.columns]
    if tab.empty or not cols:
        st.caption("Sem atividades para exibir.")
        return
    st.dataframe(
        tab[cols].rename(columns={"% Realizado": "% Volume (sem teto)", "Dias de Equipe": "Dias Trabalhados"}),
        hide_index=True, width="stretch",
        column_config={
            "Aderência PCM": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=1,
                help="Regra do PCM: realizado limitado ao plano da meta ÷ plano"),
            "Peso na Visão": st.column_config.NumberColumn(format="percent", help="Peso da meta nesta visão"),
            "Contribuição": st.column_config.NumberColumn(
                format="percent", help="Peso × Aderência PCM — a soma da coluna é a aderência da visão"),
            "% Volume (sem teto)": st.column_config.NumberColumn(
                format="percent", help="Realizado ÷ plano sem limite (mostra excesso de execução)"),
            "SLA": st.column_config.TextColumn(help="Produção esperada da equipe por dia (Configurações → SLA)"),
            "Dias Equipe p/ Concluir": st.column_config.NumberColumn(
                format="%d", help="Pendente ÷ SLA (arredondado para cima)"),
            "Plano": st.column_config.NumberColumn(format="%.1f"),
            "Qtd. Realizado": st.column_config.NumberColumn(format="%.1f"),
            "Pendente": st.column_config.NumberColumn(format="%.1f"),
            "Realizado (Extra Plano)": st.column_config.NumberColumn(format="%.1f"),
        })


def _quadro_resumo(r: motor.ResultadoTrimestre) -> None:
    df = motor.tabela_resumo(r)
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Meta PCM até a semana": FMT_PCT, "Realizado": FMT_PCT, "Gap na semana": FMT_PCT,
        "Projeção de fechamento": FMT_PCT, "Mín. semanal p/ meta": st.column_config.NumberColumn(format="percent"),
    })

# endregion


# region ====================== SESSÃO 2: Abas ======================

def _aba_resumo(r: motor.ResultadoTrimestre) -> None:
    st.markdown(f"##### 🏢 {r.rotulo_gerencia}")
    _cartoes(r.gerencia, r.sem_fim)
    if r.coords:
        st.markdown("##### 📍 Coordenações")
        cols = st.columns(len(r.coords))
        for col, (coord, rf) in zip(cols, r.coords.items()):
            k = rf.kpis
            meta = rf.curva.loc[rf.curva["Semana"] == rf.semana_atual, "meta_pcm"]
            meta = float(meta.iloc[0]) if len(meta) else 0.0
            with col:
                card(coord, pct(k["aderencia_atual"]),
                     f"Meta até sem. {rf.semana_atual}: <b>{pct(meta)}</b><br>"
                     f"Projeção: <b>{pct(k['aderencia_projetada'])}</b> · {k['tendencia']}",
                     k["classe_tendencia"])
    st.markdown("##### 📋 Quadro-resumo")
    _quadro_resumo(r)
    st.caption(f"Regra oficial do PCM (Adr_Ativo). {r.rotulo_gerencia}: cada meta pesa a soma dos pesos das "
               "coordenações; metas medidas por Depto somam o volume de todas (a sobra de uma cobre a falta de "
               "outra) — por isso não é a média das coordenações. Pode haver pequena variação em relação ao "
               "Power BI (até ~0,5 p.p. nos trimestres conferidos), por diferença de data de extração e do "
               "realizado importado (docs/REGRA_ADERENCIA_PCM.md §3.7).")

    tab = r.gerencia.tabela_itens.copy()
    if not tab.empty and "Peso Realizado" in tab.columns:
        tab["Peso pendente"] = (tab["Peso_no_Plano"] - tab["Peso Realizado"]).clip(lower=0)
        crit = tab[tab["Peso pendente"] > 0].nlargest(8, "Peso pendente")
        if not crit.empty:
            st.markdown("##### ⚠️ Atividades que mais pesam no que falta")
            st.dataframe(crit[["Descrição Meta", "Unidade", "Pendente", "Dias Equipe p/ Concluir", "Peso pendente"]],
                         hide_index=True, width="stretch",
                         column_config={"Peso pendente": FMT_PCT,
                                        "Pendente": st.column_config.NumberColumn(format="%.1f"),
                                        "Dias Equipe p/ Concluir": st.column_config.NumberColumn(format="%d")})


def _aba_gerencial(r: motor.ResultadoTrimestre) -> None:
    st.markdown(f"##### Curva da {r.rotulo_gerencia}")
    st.altair_chart(graficos.curva_fisica(r.gerencia.curva, r.gerencia.semana_atual), width="stretch")
    if r.coords:
        st.markdown("##### Coordenações: Realizado (linha cheia) x Meta PCM (tracejada)")
        st.altair_chart(graficos.curvas_coordenacoes({c: rf.curva for c, rf in r.coords.items()},
                                                     r.gerencia.semana_atual), width="stretch")
    st.markdown("##### Quadro por coordenação")
    _quadro_resumo(r)
    st.markdown("##### Atividades (todas as coordenações)")
    _tabela_atividades(r.gerencia.tabela_itens)


def _aba_coordenacao(r: motor.ResultadoTrimestre) -> None:
    coords = list(r.coords)
    if not coords:
        st.info("Sem coordenações com dados neste trimestre.")
        return
    minha = comum.coord_por_depto().get(get_depto() or "")
    c1, c2, c3 = st.columns([1.2, 1.4, 1.4])
    coord = c1.selectbox("Coordenação", coords, index=coords.index(minha) if minha in coords else 0)
    base = r.base[r.base["Coordenação"] == coord]
    eq = c2.multiselect("Equipes", sorted(base["Equipe"].dropna().astype(str).unique()))
    it = c3.multiselect("Atividades", sorted(base["Descrição Meta"].dropna().astype(str).unique()))
    if eq:
        base = base[base["Equipe"].astype(str).isin(eq)]
    if it:
        base = base[base["Descrição Meta"].astype(str).isin(it)]
    rf = fisico.calcular(base, r.p, coord, r.sem_ini, r.sem_fim) if (eq or it) else r.coords[coord]

    _cartoes(rf, r.sem_fim)
    st.altair_chart(graficos.curva_fisica(rf.curva, rf.semana_atual), width="stretch")
    st.markdown("##### 📋 Atividades")
    _tabela_atividades(rf.tabela_itens)

    o_exec = r.p.g("origem_execucao", str, "Coordenação")
    lanc = base[(base["Origem Programação"] == o_exec)]
    falha = lanc[lanc["QUANTIDADE REALIZADA"] < lanc["Quantidade Programada"]]
    if not falha.empty and "Justificativa Padrão" in falha.columns:
        mot = (falha["Justificativa Padrão"].fillna("(sem justificativa)").value_counts()
               .rename_axis("Motivo").reset_index(name="Lançamentos"))
        st.markdown("##### 🧭 Motivos de não execução (realizado < programado)")
        st.bar_chart(mot.set_index("Motivo"), horizontal=True, color="#1e3a5f")


def _aba_financeiro(r: motor.ResultadoTrimestre) -> None:
    opcoes = [r.rotulo_gerencia] + list(r.coords)
    visao = st.selectbox("Visão", opcoes, key="fin_visao")
    rf = r.gerencia if visao == r.rotulo_gerencia else r.coords[visao]
    fin = financeiro.calcular(r.p, visao, r.sem_ini, r.sem_fim, rf.curva, rf.tabela_itens, rf.semana_atual)
    if not fin.disponivel:
        st.info("💡 " + (fin.aviso or "Curva financeira indisponível.") +
                " O arquivo de orçamento é configurado em **Configurações → Parâmetros**.")
        return
    k = rf.kpis
    c1, c2, c3 = st.columns(3)
    with c1:
        card("💵 Envelope orçado (período)", reais(fin.envelope_orcado), f"OPEX manutenção · {visao}")
    with c2:
        card("📊 Realizado do plano (R$)", reais(fin.envelope_orcado * k["aderencia_atual"]),
             f"{pct(k['aderencia_atual'])} do envelope (ritmo físico)")
    with c3:
        card("🔮 Projeção (R$)", reais(fin.envelope_orcado * k["aderencia_projetada"]),
             f"{pct(k['aderencia_projetada'])} do envelope", k["classe_tendencia"])
    ref = st.checkbox("Mostrar referências oficiais (orçamento / SAP)", value=True)
    st.altair_chart(graficos.curva_financeira(fin.curva, rf.semana_atual, ref), width="stretch")
    if fin.tabela_itens is not None and not fin.tabela_itens.empty:
        st.markdown("##### 🧾 OPEX rateado por item")
        st.dataframe(fin.tabela_itens, hide_index=True, width="stretch", column_config={
            "Orçado Planejado (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
            "Realizado (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
            "Saldo Orçado (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
            "% Consumo Orçado": FMT_PCT, "% Físico": FMT_PCT})
    st.caption("Modelo top-down: envelope da PLAN ORÇ × curva física, rateado por item conforme o peso. "
               "R$/item é aproximação contábil.")


def _aba_evolucao() -> None:
    tri = comum.trimestres()
    tri = tri[tri["linhas_plano"] > 0]
    if tri.empty:
        st.info("Sem trimestres com plano carregado.")
        return
    resultados = {row["rotulo"]: comum.resultado(int(row["id"])) for _, row in tri.iterrows()}
    hist = motor.historico(resultados)
    visoes = hist["Visão"].unique().tolist()
    sel = st.multiselect("Visões", visoes, default=visoes, key="evo_visoes")
    h = hist[hist["Visão"].isin(sel)]
    st.markdown("##### Aderência por trimestre")
    st.altair_chart(graficos.evolucao(h), width="stretch")
    piv = h.pivot_table(index="Visão", columns="Período", values="Aderência", sort=False)
    st.dataframe(piv, width="stretch",
                 column_config={c: FMT_PCT for c in piv.columns})
    anual = motor.historico_anual(h)
    if not anual.empty:
        st.markdown("##### Aderência anual (média dos trimestres carregados)")
        st.altair_chart(graficos.evolucao(anual), width="stretch")
        st.dataframe(anual[["Ano", "Visão", "Aderência", "Trimestres"]], hide_index=True,
                     width="stretch", column_config={"Aderência": FMT_PCT})
    st.caption("Trimestre em andamento entra com a aderência acumulada até a última semana lançada.")

# endregion


def render_dashboard() -> None:
    t = comum.exige_trimestre()
    r = comum.resultado(int(t["id"]))
    status = "🔒 fechado" if t["status"] == "fechado" else "aberto"
    padrao = int(t["id"]) == comum.trimestre_corrente(comum.trimestres())
    corrente = (t["ano"], t["trimestre"]) == comum.trimestre_de_hoje()
    titulo(f"Resultado do Plano — {t['rotulo']}",
           ("Trimestre corrente · " if corrente else "") +
           f"Semanas {t['semana_inicio']} a {t['semana_fim']} · {status} · "
           f"{int(t['linhas_plano'])} linhas de plano · {int(t['lancamentos'])} lançamentos")
    if padrao and not corrente:
        ano, tri = comum.trimestre_de_hoje()
        st.info(f"O {tri}º tri/{ano} ainda não foi carregado; mostrando o **{t['rotulo']}**, o mais recente.")
    elif not padrao:
        c1, c2 = st.columns([4, 1])
        c1.info(f"Você está vendo o **{t['rotulo']}**, que não é o trimestre corrente.")
        c2.button("↩️ Trimestre corrente", on_click=comum.voltar_ao_corrente, width="stretch")
    if r.avisos:
        with st.expander(f"⚠️ {len(r.avisos)} aviso(s) sobre os dados"):
            for a in r.avisos:
                st.warning(a)
    if t["linhas_plano"] == 0:
        st.warning("Este trimestre ainda não tem plano. Importe o plano do PCM em **Dados → Upload**.")

    abas = st.tabs(["📊 Resumo", "🏢 Gerencial", "📍 Por Coordenação", "💰 Financeiro", "📈 Evolução"])
    with abas[0]:
        _aba_resumo(r)
    with abas[1]:
        _aba_gerencial(r)
    with abas[2]:
        _aba_coordenacao(r)
    with abas[3]:
        _aba_financeiro(r)
    with abas[4]:
        _aba_evolucao()
