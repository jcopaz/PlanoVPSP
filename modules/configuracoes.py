# modules/configuracoes.py — Pré-configurações e administração
#
# Abas (cada uma com a sua regra de permissão — ver auth/permissions.py):
#   SLA e Unidades  produção esperada da equipe/dia por Depto x Meta (programador: só o seu Depto)
#   Equipes         equipes de cada Depto (menu da tela de Lançamentos)
#   Listas          Justificativas, Status, Tipo Material, Grupo           (admin/PCM)
#   Coordenações    de-para Depto -> Coordenação -> Centro de Custo         (admin/PCM)
#   Trimestres      janela de semanas, abrir/fechar, excluir, restaurar     (admin/PCM;
#                   excluir e restaurar cópia de lançamentos: admin)
#   Parâmetros      meta, faixas de risco, orçamento (curva OPEX)           (admin/PCM)
#   Usuários        cadastro, perfil, Depto delegado, senha provisória      (admin)
#   Auditoria       quem fez o quê                                          (admin)

import pandas as pd
import streamlit as st

from auth import permissions as perm
from auth import senha as S
from auth.session import get_login
from core.ui import titulo
from database import queries as q
from modules import comum


def _ok(msg: str):
    comum.limpar_cache()
    st.session_state["msg_cfg"] = msg
    st.rerun()


# region ====================== SESSÃO 1: Cadastros (programador também) ======================

def _aba_sla():
    st.caption("**SLA** = produção esperada de uma equipe por dia, na unidade da meta. É usado no "
               "Dashboard para calcular **Dias de equipe p/ concluir** (Pendente ÷ SLA). Preencha uma vez por "
               "coordenação; vale para todos os trimestres.")
    deptos = perm.deptos_permitidos(comum.deptos_cadastrados())
    _, _, catalogo, _ = comum.cadastros()
    if not deptos:
        st.info("Nenhum Depto disponível para o seu usuário.")
        return
    filtro = st.selectbox("Depto", deptos, key="sla_depto") if len(deptos) > 1 else deptos[0]
    df = catalogo[catalogo["Depto"] == filtro][["Depto", "Descrição Meta", "Unidade", "SLA"]].reset_index(drop=True)
    vazios = int(df["SLA"].isna().sum())
    if vazios:
        st.warning(f"{vazios} meta(s) de {filtro} sem SLA.")
    t = comum.trimestre_ativo()
    if t is not None:
        pesos, _, _ = comum.dados_trimestre(int(t["id"]))
        faltam = pesos[(pesos["Depto"] == filtro) & ~pesos["Descrição Meta"].isin(df["Descrição Meta"])]
        if not faltam.empty and st.button(f"➕ Incluir {len(faltam)} meta(s) do {t['rotulo']} que faltam"):
            q.completar_catalogo(faltam, get_login())
            _ok("Metas incluídas — preencha Unidade e SLA.")
    ed = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_sla_{filtro}",
                        column_config={
                            "Depto": st.column_config.SelectboxColumn(options=[filtro], default=filtro, required=True),
                            "Descrição Meta": st.column_config.TextColumn(required=True, width="large"),
                            "Unidade": st.column_config.TextColumn(help="UN, M, TON, M³..."),
                            "SLA": st.column_config.NumberColumn(min_value=0, format="%.2f",
                                                                 help="Produção esperada da equipe por dia")})
    if st.button("💾 Salvar SLA e Unidades", type="primary", key="salvar_sla"):
        q.salvar_catalogo(ed.assign(Depto=filtro), get_login(), deptos=[filtro])
        _ok(f"SLA de {filtro} salvo.")


def _aba_equipes():
    deptos = perm.deptos_permitidos(comum.deptos_cadastrados())
    _, _, _, listas = comum.cadastros()
    if not deptos:
        st.info("Nenhum Depto disponível para o seu usuário.")
        return
    filtro = st.selectbox("Depto", deptos, key="eq_depto") if len(deptos) > 1 else deptos[0]
    df = listas[(listas["tipo"] == "Equipe") & (listas["depto"] == filtro)][["valor", "ativo"]].reset_index(drop=True)
    df["ativo"] = df["ativo"].astype(bool)
    ed = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_eq_{filtro}",
                        column_config={"valor": st.column_config.TextColumn("Equipe", required=True),
                                       "ativo": st.column_config.CheckboxColumn("Ativa", default=True)})
    st.caption("Desmarque 'Ativa' para tirar a equipe do menu sem perder o histórico.")
    if st.button("💾 Salvar equipes", type="primary", key="salvar_eq"):
        q.salvar_listas("Equipe", ed.assign(depto=filtro), get_login(), deptos=[filtro])
        _ok(f"Equipes de {filtro} salvas.")

# endregion


# region ====================== SESSÃO 2: Sistema (admin/PCM) ======================

def _aba_listas():
    tipo = st.selectbox("Lista", ["Justificativa", "Status", "Tipo Material", "Grupo"], key="lst_tipo")
    _, _, _, listas = comum.cadastros()
    df = listas[(listas["tipo"] == tipo) & (listas["depto"] == "")][["valor", "ativo"]].reset_index(drop=True)
    df["ativo"] = df["ativo"].astype(bool)
    ed = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_lst_{tipo}",
                        column_config={"valor": st.column_config.TextColumn(tipo, required=True),
                                       "ativo": st.column_config.CheckboxColumn("Ativo", default=True)})
    if st.button("💾 Salvar lista", type="primary", key="salvar_lst"):
        q.salvar_listas(tipo, ed.assign(depto=""), get_login(), deptos=[""])
        _ok(f"Lista '{tipo}' salva.")


def _aba_coordenacoes():
    st.caption("Depto (Centro de Trabalho do PCM) → Coordenação. Só os Deptos daqui entram nas importações. "
               "'Entra na Gerência' = conta na visão consolidada (média das coordenações).")
    _, coords, _, _ = comum.cadastros()
    df = coords.copy()
    df["entra_gerencia"] = df["entra_gerencia"].astype(bool)
    ed = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key="ed_coord",
                        column_config={"depto": st.column_config.TextColumn("Depto", required=True),
                                       "coordenacao": st.column_config.TextColumn("Coordenação", required=True),
                                       "centro_custo": st.column_config.TextColumn("Centro de Custo"),
                                       "entra_gerencia": st.column_config.CheckboxColumn("Entra na Gerência",
                                                                                         default=True)})
    if st.button("💾 Salvar coordenações", type="primary", key="salvar_coord"):
        q.salvar_coordenacoes(ed, get_login())
        _ok("Coordenações salvas.")


def _aba_trimestres():
    tri = comum.trimestres()
    if tri.empty:
        st.info("Nenhum trimestre. Importe em Dados → Upload.")
        return
    st.dataframe(tri[["rotulo", "semana_inicio", "semana_fim", "status", "linhas_plano", "lancamentos", "observacao"]]
                 .rename(columns={"rotulo": "Trimestre", "semana_inicio": "Sem. início", "semana_fim": "Sem. fim",
                                  "status": "Status", "linhas_plano": "Linhas de plano",
                                  "lancamentos": "Lançamentos", "observacao": "Observação"}),
                 hide_index=True, width="stretch")
    rot = dict(zip(tri["rotulo"], tri["id"]))
    escolha = st.selectbox("Editar trimestre", list(rot), index=len(rot) - 1, key="cfg_tri")
    t = tri.loc[tri["id"] == rot[escolha]].iloc[0]
    with st.form("form_tri"):
        c1, c2, c3 = st.columns(3)
        ini = c1.number_input("Semana início", 1, 54, int(t["semana_inicio"]))
        fim = c2.number_input("Semana fim", 1, 54, int(t["semana_fim"]))
        status = c3.selectbox("Status", ["aberto", "fechado"], index=0 if t["status"] == "aberto" else 1,
                              help="Fechado = lançamentos somente leitura (exceto administrador)")
        obs = st.text_input("Observação", t["observacao"] or "")
        ok = st.form_submit_button("💾 Salvar trimestre")
    if ok:
        if ini > fim:
            st.error("Semana início maior que semana fim.")
        else:
            q.atualizar_trimestre(int(t["id"]), get_login(), semana_inicio=int(ini), semana_fim=int(fim),
                                  status=status, observacao=obs or None)
            _ok(f"{escolha} atualizado.")
    if perm.is_admin():
        with st.expander("🗑️ Excluir trimestre (apaga pesos, plano e lançamentos)"):
            st.caption("Exporte o backup antes (Dados → Exportação).")
            conf = st.text_input(f"Digite {escolha} para confirmar", key="conf_exc")
            if st.button("Excluir definitivamente", disabled=conf != escolha):
                q.excluir_trimestre(int(t["id"]), get_login())
                _ok(f"{escolha} excluído.")
        _restaurar_lancamentos(tri)


def _restaurar_lancamentos(tri: pd.DataFrame):
    """Cópias automáticas dos lançamentos (antes de upload, exclusão ou restauração)."""
    with st.expander("♻️ Restaurar lançamentos de uma cópia automática"):
        st.caption(f"Antes de todo upload que substitui lançamentos, de excluir um trimestre e de restaurar, o "
                   f"sistema guarda uma cópia (as {q.COPIAS_POR_TRIMESTRE} mais recentes de cada trimestre). "
                   "Restaurar troca os lançamentos atuais pelos da cópia — e o estado atual vira uma nova cópia.")
        anos_tri = sorted({(int(a), int(t)) for a, t in zip(tri["ano"], tri["trimestre"])}, reverse=True)
        c1, c2 = st.columns(2)
        ano = c1.number_input("Ano", 2020, 2100, anos_tri[0][0] if anos_tri else 2026, key="rest_ano")
        tr_ = c2.selectbox("Trimestre", [1, 2, 3, 4], index=(anos_tri[0][1] - 1) if anos_tri else 0, key="rest_tri")
        copias = q.listar_copias(int(ano), int(tr_))
        if copias.empty:
            st.info("Nenhuma cópia deste trimestre.")
            return
        st.dataframe(copias.rename(columns={"quando": "Quando", "usuario": "Usuário", "motivo": "Motivo",
                                            "linhas": "Lançamentos"}).drop(columns=["id"]),
                     hide_index=True, width="stretch")
        rot = {f"{r.quando:%d/%m/%Y %H:%M} · {r.motivo} · {r.linhas} lanç.": int(r.id) for r in copias.itertuples()}
        escolha = st.selectbox("Cópia", list(rot), key="rest_copia")
        conf = st.checkbox("Confirmo: substituir os lançamentos atuais pelos desta cópia", key="rest_conf")
        if st.button("♻️ Restaurar", disabled=not conf):
            n = q.restaurar_copia(rot[escolha], get_login())
            _ok(f"{tr_}º tri/{ano}: {n} lançamentos restaurados.")


def _aba_parametros():
    cfg, _, _, _ = comum.cadastros()

    def f(k, d=0.0):
        try:
            return float(cfg.get(k, d))
        except (TypeError, ValueError):
            return d

    with st.form("form_param"):
        st.markdown("**Aderência e faixas de risco** (gap da projeção em relação à meta)")
        c1, c2, c3, c4 = st.columns(4)
        meta = c1.number_input("Meta de aderência", 0.0, 2.0, f("meta_aderencia", 1.0), 0.01, format="%.2f")
        leve = c2.number_input("Leve desvio até", 0.0, 1.0, f("faixa_leve", .05), 0.01, format="%.2f")
        risco = c3.number_input("Em risco até", 0.0, 1.0, f("faixa_risco", .10), 0.01, format="%.2f")
        crit = c4.number_input("Risco alto até", 0.0, 1.0, f("faixa_critico", .15), 0.01, format="%.2f")
        rot = st.text_input("Nome da visão consolidada", cfg.get("rotulo_gerencia", "Gerência"))
        fora = st.text_input("Grupos fora da aderência (;)", cfg.get("grupos_fora_aderencia", "Saneamento Vegetal;Drenagem"),
                             help="Metas desses grupos não pesam na curva da Via (regra do PCM).")
        depto = st.text_area("Metas com Tipo de medição = DEPTO (;)", cfg.get("metas_medicao_depto", ""), height=80,
                             help="Na Gerência, essas metas somam o volume de todas as coordenações (a sobra de "
                                  "uma cobre a falta de outra). Preenchido sozinho ao importar o export de pesos.")
        st.markdown("**Curva financeira (OPEX)** — arquivo na pasta do app")
        c5, c6 = st.columns(2)
        orc = c5.text_input("Arquivo de orçamento", cfg.get("arquivo_orcamento", ""))
        aba = c6.text_input("Aba do orçamento", cfg.get("aba_plan_orc", "PLAN ORÇ"))
        pac = st.text_input("Pacotes do envelope (;)", cfg.get("env.pacotes_incluir", ""))
        ccs = st.text_input("Centros de custo do envelope (;)", cfg.get("env.centros_custo", ""))
        ok = st.form_submit_button("💾 Salvar parâmetros")
    if ok:
        if not (leve <= risco <= crit):
            st.error("As faixas precisam estar em ordem: leve ≤ risco ≤ alto.")
        else:
            q.salvar_config({"meta_aderencia": meta, "faixa_leve": leve, "faixa_risco": risco,
                             "faixa_critico": crit, "rotulo_gerencia": rot, "grupos_fora_aderencia": fora,
                             "metas_medicao_depto": ";".join(sorted({m.strip().upper() for m in depto.split(";") if m.strip()})), "arquivo_orcamento": orc,
                             "aba_plan_orc": aba, "env.pacotes_incluir": pac, "env.centros_custo": ccs},
                            get_login())
            _ok("Parâmetros salvos.")

# endregion


# region ====================== SESSÃO 3: Usuários e auditoria (admin) ======================

def _aba_usuarios():
    deptos = [""] + comum.deptos_cadastrados()
    us = q.listar_usuarios()
    st.dataframe(us[["login", "nome", "email", "perfil", "depto", "ativo", "deve_trocar_senha", "ultimo_login"]],
                 hide_index=True, width="stretch")
    with st.expander("➕ Novo usuário"):
        with st.form("form_novo_usr", clear_on_submit=True):
            c1, c2 = st.columns(2)
            login = c1.text_input("Matrícula / login")
            nome = c2.text_input("Nome")
            email = c1.text_input("E-mail")
            perfil = c2.selectbox("Perfil", list(perm.PERFIS), format_func=perm.PERFIS.get, index=2)
            depto = c1.selectbox("Depto delegado (programador)", deptos,
                                 format_func=lambda d: d or "Todos")
            ok = st.form_submit_button("Criar usuário")
        if ok:
            if not (login.strip() and nome.strip()):
                st.error("Login e nome são obrigatórios.")
            elif q.usuario_por_login(login):
                st.error("Já existe usuário com esse login.")
            else:
                prov = S.senha_provisoria()
                q.criar_usuario(login, nome, S.gerar_hash(prov), perfil, depto or None, email, get_login())
                st.session_state["msg_cfg"] = (f"Usuário {login} criado. Senha provisória: **{prov}** "
                                               "(ele troca no 1º acesso).")
                st.rerun()
    if us.empty:
        return
    with st.expander("✏️ Editar / resetar senha"):
        sel = st.selectbox("Usuário", us["login"].tolist(), key="usr_sel")
        u = us.loc[us["login"] == sel].iloc[0]
        with st.form("form_edit_usr"):
            c1, c2, c3 = st.columns(3)
            perfil = c1.selectbox("Perfil", list(perm.PERFIS), format_func=perm.PERFIS.get,
                                  index=list(perm.PERFIS).index(u["perfil"]) if u["perfil"] in perm.PERFIS else 3)
            dep_atual = u["depto"] if u["depto"] in deptos else ""
            depto = c2.selectbox("Depto delegado", deptos, index=deptos.index(dep_atual),
                                 format_func=lambda d: d or "Todos")
            ativo = c3.checkbox("Ativo", bool(u["ativo"]))
            resetar = st.checkbox("Gerar nova senha provisória")
            ok = st.form_submit_button("Salvar")
        if ok:
            perde_admin = u["perfil"] == "admin" and bool(u["ativo"]) and (perfil != "admin" or not ativo)
            if sel == get_login() and perde_admin:
                st.error("Você não pode tirar o seu próprio acesso de administrador.")
            elif perde_admin and q.admins_ativos() <= 1:
                st.error("Este é o último administrador ativo. Promova outro usuário antes.")
            else:
                campos = {"perfil": perfil, "depto": depto or None, "ativo": ativo}
                msg = f"Usuário {sel} atualizado."
                if resetar:
                    prov = S.senha_provisoria()
                    campos.update(senha_hash=S.gerar_hash(prov), deve_trocar_senha=True)
                    msg += f" Senha provisória: **{prov}**"
                q.atualizar_usuario(int(u["id"]), get_login(), **campos)
                st.session_state["msg_cfg"] = msg
                st.rerun()


def _aba_auditoria():
    df = q.listar_auditoria(500)
    st.dataframe(df, hide_index=True, width="stretch")

# endregion


def render_configuracoes() -> None:
    perm.require(perm.pode_configurar_cadastros())
    titulo("Configurações", "Pré-configurações do programador (SLA, equipes) e do sistema")
    msg = st.session_state.pop("msg_cfg", None)
    if msg:
        st.success(msg)
    if not comum.deptos_cadastrados():
        st.warning("Nenhuma coordenação cadastrada.")
    abas = [("🎯 SLA e Unidades", _aba_sla, True), ("👷 Equipes", _aba_equipes, True),
            ("📋 Listas", _aba_listas, perm.pode_configurar_sistema()),
            ("🏢 Coordenações", _aba_coordenacoes, perm.pode_configurar_sistema()),
            ("📅 Trimestres", _aba_trimestres, perm.pode_configurar_sistema()),
            ("⚙️ Parâmetros", _aba_parametros, perm.pode_configurar_sistema()),
            ("👥 Usuários", _aba_usuarios, perm.is_admin()),
            ("🧾 Auditoria", _aba_auditoria, perm.is_admin())]
    abas = [a for a in abas if a[2]]
    for tab, (_, fn, _) in zip(st.tabs([a[0] for a in abas]), abas):
        with tab:
            if not comum.deptos_cadastrados() and fn in (_aba_sla, _aba_equipes):
                st.info("Cadastre as coordenações primeiro.")
                continue
            fn()
