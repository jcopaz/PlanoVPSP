# auth/login.py — Tela de login, 1º administrador e troca de senha obrigatória
#
# Fluxo (chamado pelo app.py):
#   sem usuário no banco  -> render_primeiro_admin()  (cria o 1º administrador)
#   não logado            -> render_login()
#   deve_trocar_senha     -> render_trocar_senha()     (conta nova / senha resetada)
# Visual no padrão do MRS Sentinel: fundo escuro, cartão centralizado.

import streamlit as st

from auth import senha as S
from auth.session import get_usuario, set_usuario
from core.versao import APP_VERSION
from database import queries as q


# region ====================== SESSÃO 1: CSS ======================

def _css():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .stApp { background: #1b2130; }
    .main .block-container, [data-testid="stMainBlockContainer"] {
        padding-top: 4rem !important; max-width: 460px !important; margin: 0 auto !important;
    }
    div[data-testid="stForm"] {
        background: #ffffff; border-radius: 14px; padding: 1.6rem 1.6rem 1.2rem;
        box-shadow: 0 12px 40px rgba(0,0,0,.35); border: none;
    }
    div[data-testid="stForm"] .stButton > button, div[data-testid="stForm"] button[kind="secondaryFormSubmit"],
    div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
        width: 100%; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 100%) !important;
        color: #fff !important; border: none !important; border-radius: 8px !important;
        padding: 10px !important; font-weight: 600 !important;
    }
    .login-titulo { text-align:center; color:#e8a920; font-family:'Arial Black',Arial,sans-serif;
        font-size:1.9rem; letter-spacing:.06em; margin:0; }
    .login-sub { text-align:center; color:rgba(255,255,255,.75); font-size:.95rem; margin:.2rem 0 1.4rem; }
    .login-rodape { text-align:center; color:rgba(255,255,255,.45); font-size:.75rem; margin-top:1.2rem; }
    </style>
    """, unsafe_allow_html=True)


def _cabecalho(subtitulo: str):
    st.markdown('<div style="text-align:center;font-size:3rem">🚂</div>'
                '<p class="login-titulo">PLANO VP</p>'
                f'<p class="login-sub">{subtitulo}</p>', unsafe_allow_html=True)


def _rodape():
    st.markdown(f'<p class="login-rodape">Plano de Manutenção · Via Permanente · v{APP_VERSION}</p>',
                unsafe_allow_html=True)

# endregion


# region ====================== SESSÃO 2: Login ======================

def render_login() -> None:
    _css()
    _cabecalho("Plano de Manutenção — Via Permanente")
    with st.form("form_login"):
        login = st.text_input("Matrícula / login")
        senha = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        u = q.usuario_por_login(login) if login.strip() else None
        if not u or not u.get("ativo") or not S.verificar(senha, u.get("senha_hash")):
            st.error("Login ou senha inválidos.")       # mensagem genérica de propósito
        else:
            q.registrar_login(u["id"], u["login"])
            set_usuario(u)
            st.rerun()
    st.caption("Esqueceu a senha? Peça ao administrador para gerar uma senha provisória "
               "(Configurações → Usuários).")
    _rodape()


def render_primeiro_admin() -> None:
    """Banco vazio: cria o 1º administrador (só aparece enquanto não há usuários)."""
    _css()
    _cabecalho("Primeiro acesso — criar o administrador")
    with st.form("form_admin"):
        login = st.text_input("Matrícula / login")
        nome = st.text_input("Nome")
        email = st.text_input("E-mail (opcional)")
        s1 = st.text_input("Senha", type="password")
        s2 = st.text_input("Confirme a senha", type="password")
        ok = st.form_submit_button("Criar administrador")
    if ok:
        erro = S.validar_nova(s1, s2) or (None if login.strip() and nome.strip() else "Preencha login e nome.")
        if erro:
            st.error(erro)
        elif not q.criar_primeiro_admin(login, nome, S.gerar_hash(s1), email):
            st.error("Já existe usuário cadastrado. Recarregue a página.")
        else:
            st.success("Administrador criado. Entre com o login e a senha.")
            st.rerun()
    _rodape()


def render_trocar_senha() -> None:
    _css()
    u = get_usuario()
    _cabecalho(f"Olá, {u.get('nome', '')}. Defina sua senha")
    with st.form("form_troca"):
        s1 = st.text_input("Nova senha", type="password")
        s2 = st.text_input("Confirme a nova senha", type="password")
        ok = st.form_submit_button("Salvar senha")
    if ok:
        erro = S.validar_nova(s1, s2)
        if erro:
            st.error(erro)
        else:
            q.atualizar_usuario(u["id"], u["login"], senha_hash=S.gerar_hash(s1), deve_trocar_senha=False)
            set_usuario({**u, "deve_trocar_senha": False})
            st.cache_data.clear()      # o app guarda o usuário em cache por 60 s (app.py)
            st.rerun()
    _rodape()

# endregion
