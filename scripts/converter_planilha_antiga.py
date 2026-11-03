# -*- coding: utf-8 -*-
"""Converte o workbook antigo (Diário + Planilha de Peso, com fórmulas) para o
modelo v3 (Pesos / Plano_PCM / Lancamentos, sem fórmulas).

    python scripts/converter_planilha_antiga.py "Plano de Manutenção 2º Trimestre - SP.xlsx"
    python scripts/converter_planilha_antiga.py antigo.xlsx saida.xlsx

Saída padrão: dados/<nome>_v3.xlsx (a pasta dados/ não vai para o GitHub).
Também serve de teste: o dashboard deve dar a MESMA aderência nos dois arquivos.
"""
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import config, dados  # noqa: E402
from core import modelo as M  # noqa: E402
from scripts.gerar_modelo import gerar  # noqa: E402


def _vazio(v):
    return None if pd.isna(v) else v


def converter(origem: str, destino: str) -> None:
    p = config.carregar()
    p.cfg["arquivo_plano"] = origem
    dia, peso, _ = dados.carregar_plano(p)
    dia = dia.loc[:, ~dia.columns.duplicated()]       # o Diário antigo repete "Número do Material"
    peso = peso.loc[:, ~peso.columns.duplicated()]
    o_pcm = p.g("origem_pcm", str, "PCM")

    pesos = []
    for _, r in peso.dropna(subset=["Chave Peso"]).iterrows():
        depto, meta = str(r["Chave Peso"]).split("|", 1)
        pesos.append({"Depto": depto, "Grupo": _vazio(r.get("Grupo")), "Descrição Meta": meta,
                      "Peso": _vazio(r.get("Peso Item")), "Unidade": _vazio(r.get("Unidade")),
                      "SLA": _vazio(r.get("SLA"))})

    def linha(r, de_para):
        return {novo: _vazio(r.get(antigo)) for novo, antigo in de_para.items()}

    pcm = dia[dia["Origem Programação"] == o_pcm]
    exe = dia[dia["Origem Programação"] != o_pcm]
    comum = {"Depto": "Depto", "Descrição Meta": "Descrição Meta", "Nº Material": "Número do Material",
             "Equipe": "Equipe", "Ativo": "Ativo", "Tipo Material": "Tipo Material",
             "Quantidade Programada": "Quantidade Programada", "Observação": "Observação"}
    plano = [linha(r, {**comum, "Data Planejada": "Data Planejada", "Equipamento": "Equipamento"})
             for _, r in pcm.iterrows()]
    lanc = [linha(r, {**comum, "Data": "Data Planejada", "Quantidade Realizada": "QUANTIDADE REALIZADA",
                      "No Plano": "Plano", "Justificativa": "Justificativa Padrão",
                      "Plano de Ação": "Plano de ação", "Responsável": "Responsável",
                      "Prazo": "Prazo", "Status": "Status"})
            for _, r in exe.iterrows()]
    for ln in plano + lanc:
        for k in ("Data Planejada", "Data", "Prazo"):
            if isinstance(ln.get(k), pd.Timestamp):
                ln[k] = ln[k].to_pydatetime()

    listas = dict(M.LISTAS_PADRAO)
    listas["Depto"] = sorted({x["Depto"] for x in pesos})
    listas["Equipe"] = sorted(dia["Equipe"].dropna().astype(str).str.strip().unique().tolist())
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
