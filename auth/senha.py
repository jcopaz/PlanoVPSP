# auth/senha.py — Hash e verificação de senha (PBKDF2-SHA256)
#
# Mesmo esquema do VIA WMS: a senha nunca é gravada pura, só o hash com sal
# aleatório. Formato gravado em usuarios.senha_hash:
#     pbkdf2_sha256$<iterações>$<sal base64>$<hash base64>
# Não depende de serviço externo (Supabase Auth etc.): roda igual no SQLite
# local e no Postgres/Neon. Troca para AD/Entra ID fica no roadmap.

import base64
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 600_000          # recomendação OWASP para PBKDF2-SHA256
TAMANHO_SAL = 16
SENHA_MINIMA = 8


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(TAMANHO_SAL)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES)
    return f"{ALGORITMO}${ITERACOES}${base64.b64encode(sal).decode()}${base64.b64encode(dk).decode()}"


def verificar(senha: str, armazenado: str | None) -> bool:
    try:
        alg, it, sal_b64, hash_b64 = (armazenado or "").split("$")
        if alg != ALGORITMO or not (100_000 <= int(it) <= 2_000_000):
            return False
        dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), base64.b64decode(sal_b64), int(it))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def validar_nova(senha: str, confirmacao: str) -> str | None:
    """Mensagem de erro, ou None se a senha nova é aceitável."""
    if len(senha) < SENHA_MINIMA:
        return f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres."
    if senha != confirmacao:
        return "A confirmação não confere com a senha."
    if not (any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)):
        return "Use letras e números na senha."
    return None


def senha_provisoria() -> str:
    """Senha temporária para conta nova/reset (o usuário troca no 1º acesso)."""
    return "Plano-" + secrets.token_hex(3)
