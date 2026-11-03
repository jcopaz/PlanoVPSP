# -*- coding: utf-8 -*-
"""Cria a planilha do trimestre (modelo v3) a partir dos exports do PCM.

    python scripts/importar_plano_pcm.py "data (9).xlsx" --planejamento "Planejamento PCM.xlsx"
    python scripts/importar_plano_pcm.py "data (9).xlsx" --planejamento "Planejamento PCM.xlsx" \
        --catalogo "dados/Plano_2026_T3.xlsx"
    python scripts/importar_plano_pcm.py ... --forcar   # troca Pesos/Plano_PCM, MANTÉM os Lancamentos

1º arquivo     export de pesos do PCM (Peso Item Redist, Plano Trimestral)
--planejamento visão congelada do plano por dia (curva planejada); sem ela, curva linear
--catalogo     planilha v3 anterior: copia Unidade/SLA das metas (o export não traz)
Saída padrão: dados/Plano_<ano>_T<trimestre>.xlsx (fora do Git), com Pesos e
Plano_PCM preenchidos e Lancamentos em branco para os programadores.
"""
import argparse
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import config, importar_pcm  # noqa: E402
from core import modelo as M  # noqa: E402
from scripts.gerar_modelo import gerar  # noqa: E402


def _preservar(arquivo: str):
    """Lançamentos e equipes de uma planilha v3 existente (reimportação do plano)."""
    with pd.ExcelFile(arquivo) as xls:
        if not M.eh_modelo(xls.sheet_names):
            sys.exit(f"[erro] {arquivo} não está no modelo v3; use --saida para outro arquivo.")
        lanc = pd.read_excel(xls, M.ABA_LANC).dropna(how="all")
        listas = pd.read_excel(xls, M.ABA_LISTAS) if M.ABA_LISTAS in xls.sheet_names else pd.DataFrame()
    lanc = lanc.astype(object).where(lanc.notna(), None)
    linhas = [{k: (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for k, v in ln.items()}
              for ln in lanc.to_dict("records")]
    equipes = listas["Equipe"].dropna().astype(str).tolist() if "Equipe" in listas else []
    return linhas, equipes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export")
    ap.add_argument("--planejamento")
    ap.add_argument("--catalogo")
    ap.add_argument("--saida")
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()

    p = config.carregar()
    catalogo = None
    if a.catalogo:
        catalogo = pd.read_excel(config.caminho(a.catalogo), sheet_name=M.ABA_PESOS)
    r = importar_pcm.importar(config.caminho(a.export), p, catalogo,
                              config.caminho(a.planejamento) if a.planejamento else None)

    destino = config.caminho(a.saida or os.path.join("dados", f"Plano_{r.ano}_T{r.trimestre}.xlsx"))
    listas = dict(M.LISTAS_PADRAO)
    listas["Depto"] = sorted({x["Depto"] for x in r.pesos}) or listas["Depto"]
    lanc, equipes = [], []
    if os.path.exists(destino):
        if not a.forcar:
            sys.exit(f"[erro] {destino} já existe. Use --forcar para trocar Pesos/Plano_PCM "
                     f"(os Lancamentos e as Equipes são mantidos) ou --saida.")
        lanc, equipes = _preservar(destino)
        print(f"[info] mantidos {len(lanc)} lançamento(s) de {destino}")
    do_plano = [str(ln["Equipe"]).strip() for ln in r.plano if ln.get("Equipe")]
    listas["Equipe"] = sorted(set(equipes) | set(do_plano))
    gerar(destino, r.pesos, r.plano, lanc, listas)

    for av in r.avisos:
        print(f"[aviso] {av}")
    print(f"[ok] {destino}: {r.trimestre}º tri/{r.ano}, {len(r.pesos)} metas, {len(r.plano)} linhas de plano")
    print(f"     No parametros.xlsx (aba Config): arquivo_plano = {os.path.relpath(destino, RAIZ)}"
          f" | trimestre = {r.trimestre} | ano = {r.ano}")


if __name__ == "__main__":
    main()
