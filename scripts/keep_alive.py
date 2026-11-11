# -*- coding: utf-8 -*-
"""Mantém o app do Streamlit Community Cloud acordado (roda no GitHub Actions).

O Streamlit Cloud põe o app para dormir após ~12 h sem visitas, e só conta visita
de navegador de verdade (sessão websocket) — um GET simples não basta. Por isso
este script abre o app num Chromium sem tela (Playwright):
  1. se o app estiver dormindo, clica em "Yes, get this app back up!" e espera subir;
  2. confirma que a tela de login carregou (texto "PLANO VP");
  3. sai com erro se não conseguir — o GitHub avisa por e-mail da falha.

Uso: python scripts/keep_alive.py [URL]   (padrão: variável APP_URL ou planovpsp.streamlit.app)
Workflow: .github/workflows/keep-alive.yml. Detalhes: docs/DOCUMENTACAO_TECNICA.md §8.
"""
import os
import sys

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("APP_URL")) or "https://planovpsp.streamlit.app"
TEXTO_APP = "PLANO VP"          # título da tela de login (auth/login.py)
BOTAO_ACORDAR = "get this app back up"


def _app_carregou(page, espera_ms: int) -> bool:
    """O app roda num iframe dentro da página do Streamlit Cloud; procura o texto em todos os frames."""
    fim = espera_ms
    while fim > 0:
        for frame in page.frames:
            try:
                if frame.get_by_text(TEXTO_APP).first.is_visible():
                    return True
            except Exception:  # noqa: BLE001 — frame recarregando
                pass
        page.wait_for_timeout(5000)
        fim -= 5000
    return False


def main() -> None:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        page = navegador.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        botao = page.get_by_role("button", name=BOTAO_ACORDAR)
        if botao.count():
            print("App dormindo — acordando...")
            try:
                botao.first.click(timeout=30_000)
            except PWTimeout:
                print("[aviso] o botão de acordar não respondeu ao clique; esperando o app mesmo assim.")
        ok = _app_carregou(page, espera_ms=240_000)
        navegador.close()
    if not ok:
        sys.exit(f"[erro] o app não carregou em {URL} (texto '{TEXTO_APP}' não encontrado).")
    print(f"OK — {URL} acordado.")


if __name__ == "__main__":
    main()
