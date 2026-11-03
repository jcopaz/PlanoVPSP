# -*- coding: utf-8 -*-
"""Cria um usuário ou redefine a senha de um existente direto no banco.

Uso típico: recuperar o acesso de administrador (ninguém mais consegue entrar).

    python scripts/criar_usuario.py LOGIN "Nome Completo" --perfil admin
    python scripts/criar_usuario.py LOGIN --resetar

A senha é pedida no terminal (não aparece na tela nem fica no histórico).
Banco: o mesmo do app (secrets.toml / PLANO_DB_URL / dados/plano.db).
"""
import argparse
import getpass
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from auth import senha as S  # noqa: E402
from auth.permissions import PERFIS  # noqa: E402
from database import queries as q  # noqa: E402
from database.client import descricao_banco  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("login")
    ap.add_argument("nome", nargs="?")
    ap.add_argument("--perfil", choices=list(PERFIS), default="admin")
    ap.add_argument("--depto")
    ap.add_argument("--resetar", action="store_true", help="só redefine a senha de um login existente")
    a = ap.parse_args()
    print(f"Banco: {descricao_banco()}")
    s1 = getpass.getpass("Nova senha: ")
    s2 = getpass.getpass("Confirme: ")
    erro = S.validar_nova(s1, s2)
    if erro:
        sys.exit(f"[erro] {erro}")
    u = q.usuario_por_login(a.login)
    if a.resetar or u:
        if not u:
            sys.exit(f"[erro] login {a.login} não existe.")
        q.atualizar_usuario(u["id"], "script", senha_hash=S.gerar_hash(s1), ativo=True, deve_trocar_senha=False)
        print(f"[ok] senha de {a.login} redefinida (conta reativada).")
        return
    if not a.nome:
        sys.exit("[erro] informe o nome para criar o usuário.")
    q.criar_usuario(a.login, a.nome, S.gerar_hash(s1), a.perfil, a.depto, None, "script", deve_trocar_senha=False)
    print(f"[ok] usuário {a.login} ({a.perfil}) criado.")


if __name__ == "__main__":
    main()
