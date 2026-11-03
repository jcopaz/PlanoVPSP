# modules/home.py — Menu lateral (marca, usuário, trimestre ativo, navegação, sair)
#
# Para adicionar uma tela nova:
#   1. crie modules/nova_tela.py com render_nova_tela()
#   2. registre em app.py::ROTAS
#   3. inclua o botão em MENU abaixo (com a regra de permissão)

import streamlit as st

from auth import permissions as perm
from auth.session import (clear_session, get_depto, get_nome, get_pagina, get_perfil,
                          set_pagina, set_trimestre_id)
from core.versao import APP_VERSION
from database.client import descricao_banco
from modules import comum

# (página, rótulo, função que diz se o usuário vê o botão)
MENU = [
    ("dashboard", "📊  Dashboard", lambda: True),
    ("lancamentos", "📝  Lançamentos", perm.pode_lancar),
    ("dados", "🗂️  Dados (upload / exportação)", lambda: True),
    ("configuracoes", "⚙️  Configurações", perm.pode_configurar_cadastros),
]


def _seletor_trimestre():
    tri = comum.trimestres()
    if tri.empty:
        st.caption("Nenhum trimestre carregado.")
        return
    t = comum.trimestre_ativo()
    rotulos = dict(zip(tri["rotulo"] + tri["status"].map({"fechado": " 🔒", "aberto": ""}), tri["id"]))
    lista = list(rotulos)
    atual = next(i for i, (_, v) in enumerate(rotulos.items()) if v == t["id"])
    escolha = st.selectbox("Trimestre", lista, index=atual, key="sb_trimestre")
    if rotulos[escolha] != t["id"]:
        set_trimestre_id(int(rotulos[escolha]))
        st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="sb-marca">🚂 PLANO VP</div>'
                    '<div style="font-size:.78rem;opacity:.7">Plano de Manutenção · Via Permanente</div>',
                    unsafe_allow_html=True)
        depto = get_depto()
        st.markdown(f'<div class="sb-badge">👤 <b>{get_nome()}</b><br>'
                    f'{perm.PERFIS.get(get_perfil(), get_perfil())}'
                    + (f" · {depto}" if depto and get_perfil() == "programador" else "") + "</div>",
                    unsafe_allow_html=True)
        _seletor_trimestre()
        st.markdown("&nbsp;", unsafe_allow_html=True)
        for pagina, rotulo, pode in MENU:
            if pode():
                tipo = "primary" if get_pagina() == pagina else "secondary"
                if st.button(rotulo, key=f"nav_{pagina}", width="stretch", type=tipo):
                    set_pagina(pagina)
                    st.rerun()
        st.markdown("---")
        if st.button("🚪  Sair", key="btn_sair", width="stretch"):
            clear_session()
            st.rerun()
        st.caption(f"v{APP_VERSION} · {descricao_banco()}")
