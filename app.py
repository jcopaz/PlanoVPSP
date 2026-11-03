# app.py — Ponto de entrada do Plano VP (Plano de Manutenção · Via Permanente)
#
#     streamlit run app.py
#
# ESTRUTURA DE ROTEAMENTO (mesmo padrão do MRS Sentinel):
#   banco sem usuários   → render_primeiro_admin()
#   não logado           → render_login()
#   deve trocar a senha  → render_trocar_senha()   (sem menu: não dá para "fugir")
#   logado               → render_sidebar() + ROTAS[st.session_state.pagina]
#
# Para adicionar uma tela: modules/nova.py (render_nova) → ROTAS abaixo →
# botão em modules/home.py::MENU. Documentação: docs/DOCUMENTACAO_TECNICA.md.

import streamlit as st

from core.versao import APP_NOME, APP_VERSION

# region ====================== SESSÃO 1: Configuração da página ======================
# ⚠️ st.set_page_config precisa ser a PRIMEIRA chamada st.*
st.set_page_config(
    page_title=APP_NOME,
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None,
                "About": f"**{APP_NOME}** — Plano de Manutenção da Via Permanente\n\nv{APP_VERSION}"},
)
# endregion


# region ====================== SESSÃO 2: Imports (após set_page_config) ======================
from auth.login import render_login, render_primeiro_admin, render_trocar_senha  # noqa: E402
from auth.session import (clear_session, get_pagina, get_usuario, init_session,  # noqa: E402
                          is_logged_in, set_usuario)
from core.ui import injetar_css  # noqa: E402
from database import queries as q  # noqa: E402
from modules.configuracoes import render_configuracoes  # noqa: E402
from modules.dados import render_dados  # noqa: E402
from modules.dashboard import render_dashboard  # noqa: E402
from modules.home import render_sidebar  # noqa: E402
from modules.lancamentos import render_lancamentos  # noqa: E402
# endregion


# region ====================== SESSÃO 3: Roteador ======================
ROTAS = {
    "dashboard": render_dashboard,
    "lancamentos": render_lancamentos,
    "dados": render_dados,
    "configuracoes": render_configuracoes,
}


def _usuario_ainda_valido() -> bool:
    """Relê o usuário no banco a cada interação: conta desativada sai na hora e
    mudança de perfil/Depto vale sem precisar sair e entrar de novo."""
    u = q.usuario_por_login(get_usuario().get("login", ""))
    if not u or not u.get("ativo"):
        clear_session()
        init_session()
        return False
    set_usuario(u)
    return True


def main() -> None:
    injetar_css()
    init_session()
    try:
        sem_usuarios = q.contar_usuarios() == 0
    except Exception as e:  # noqa: BLE001
        st.error(f"🚨 Não foi possível conectar ao banco de dados: {e}")
        st.info("Confira a URL em `.streamlit/secrets.toml` ([database] url) ou a variável PLANO_DB_URL. "
                "Sem nenhuma das duas, o app usa o SQLite local em dados/plano.db.")
        st.stop()

    if sem_usuarios:
        render_primeiro_admin()
    elif not is_logged_in() or not _usuario_ainda_valido():
        render_login()
    elif get_usuario().get("deve_trocar_senha"):
        render_trocar_senha()
    else:
        render_sidebar()
        ROTAS.get(get_pagina(), render_dashboard)()


main()
# endregion
