# -*- coding: utf-8 -*-
"""Converte o workbook antigo (Diário + Planilha de Peso, com fórmulas) para o
modelo v3 (Pesos / Plano_PCM / Lancamentos, sem fórmulas).

    python scripts/converter_planilha_antiga.py "Plano de Manutenção 2º Trimestre - SP.xlsx"
    python scripts/converter_planilha_antiga.py antigo.xlsx saida.xlsx

Saída padrão: dados/<nome>_v3.xlsx (a pasta dados/ não vai para o GitHub).
No app, não precisa converter: a tela Dados → Upload aceita a planilha antiga direto.
A conversão usa core/planilha.py::legado_para_v3 (mesma função do upload).
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import config  # noqa: E402
from core import modelo as M  # noqa: E402
from core.planilha import gerar, legado_para_v3  # noqa: E402


def converter(origem: str, destino: str) -> None:
    pesos, plano, lanc = legado_para_v3(origem, config.carregar())
    listas = dict(M.LISTAS_PADRAO)
    listas["Depto"] = sorted(pesos["Depto"].dropna().unique().tolist())
    listas["Equipe"] = sorted(set(plano["Equipe"].dropna().astype(str)) | set(lanc["Equipe"].dropna().astype(str)))
    gerar(destino, pesos, plano, lanc, listas)
    print(f"[ok] {destino}: {len(pesos)} pesos, {len(plano)} linhas PCM, {len(lanc)} lançamentos")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    origem = config.caminho(sys.argv[1])
    if len(sys.argv) > 2:
        destino = config.caminho(sys.argv[2])
    else:
        base = os.path.splitext(os.path.basename(origem))[0]
        destino = os.path.join(RAIZ, "dados", f"{base}_v3.xlsx")
    converter(origem, destino)


if __name__ == "__main__":
    main()
