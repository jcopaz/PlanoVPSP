# auth/session.py — Estado de sessão do usuário (padrão MRS Sentinel)
# Centraliza toda leitura/escrita do st.session_state relacionada ao usuário
# e à navegação, evitando acesso direto e disperso ao session_state.

import streamlit as st


# region ====================== SESSÃO 1: Leitura ======================

def is_logged_in() -> bool:
    return bool(st.session_state.get("usuario"))


def get_usuario() -> dict:
    return st.session_state.get("usuario") or {}


def get_login() -> str:
    return get_usuario().get("login", "")


def get_nome() -> str:
    return get_usuario().get("nome", "Usuário")


def get_perfil() -> str:
    return get_usuario().get("perfil", "leitor")


def get_depto() -> str | None:
    """Depto delegado ao usuário (ex.: V.SP.IPA) ou None = todos."""
    return get_usuario().get("depto") or None


def get_pagina() -> str:
    return st.session_state.get("pagina", "dashboard")


def get_trimestre_id() -> int | None:
    return st.session_state.get("trimestre_id")

# endregion


# region ====================== SESSÃO 2: Escrita ======================

def set_usuario(usuario: dict) -> None:
    dados = {k: v for k, v in usuario.items() if k != "senha_hash"}
    st.session_state["usuario"] = dados


def set_pagina(pagina: str) -> None:
    st.session_state["pagina"] = pagina


def set_trimestre_id(tid: int | None) -> None:
    st.session_state["trimestre_id"] = tid


def clear_session() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def init_session() -> None:
    for k, v in {"usuario": None, "pagina": "dashboard", "trimestre_id": None}.items():
        st.session_state.setdefault(k, v)

# endregion
