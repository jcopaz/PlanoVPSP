# auth/permissions.py — Perfis e permissões (RBAC)
#
#   Ação                                   | admin | pcm | programador        | leitor
#   Ver Dashboard (todas as visões)        |  ✅   | ✅  | ✅                 | ✅
#   Lançar / corrigir atividades           |  ✅   | ✅  | ✅ só o seu Depto  | ❌
#   Exportar planilha (backup)             |  ✅   | ✅  | ✅                 | ✅
#   Upload (plano do PCM, histórico)       |  ✅   | ✅  | ❌                 | ❌
#   Configurar SLA / Equipes               |  ✅   | ✅  | ✅ só o seu Depto  | ❌
#   Configurar sistema (trimestres, listas,|  ✅   | ✅  | ❌                 | ❌
#     coordenações, parâmetros)            |       |     |                    |
#   Usuários e auditoria                   |  ✅   | ❌  | ❌                 | ❌
#   Editar trimestre FECHADO               |  ✅   | ❌  | ❌                 | ❌
#
# "Depto delegado" (usuarios.depto) restringe programador ao seu Depto. Para
# admin/pcm o campo é ignorado (veem e editam tudo). O bloqueio é de verdade
# nas telas (require_*), não só o botão sumindo do menu.

import streamlit as st

from auth.session import get_depto, get_perfil

PERFIS = {
    "admin": "Administrador",
    "pcm": "PCM / Planejamento",
    "programador": "Programador",
    "leitor": "Leitura",
}


def is_admin() -> bool:
    return get_perfil() == "admin"


def pode_lancar() -> bool:
    return get_perfil() in ("admin", "pcm", "programador")


def pode_upload() -> bool:
    return get_perfil() in ("admin", "pcm")


def pode_configurar_cadastros() -> bool:
    return get_perfil() in ("admin", "pcm", "programador")


def pode_configurar_sistema() -> bool:
    return get_perfil() in ("admin", "pcm")


def pode_editar_fechado() -> bool:
    return is_admin()


def deptos_permitidos(todos: list[str]) -> list[str]:
    """Deptos que o usuário pode editar (programador com Depto delegado: só o dele)."""
    if get_perfil() == "programador" and get_depto():
        return [d for d in todos if d == get_depto()]
    return list(todos)


def require(condicao: bool, mensagem: str = "Você não tem permissão para acessar esta tela.") -> None:
    """Interrompe a tela se o usuário não tiver permissão."""
    if not condicao:
        st.error(f"🔒 {mensagem}")
        st.stop()
