# -*- coding: utf-8 -*-
"""Gera o parametros.xlsx padrão (trimestre 2 / 2026).

    python scripts/gerar_parametros.py           # cria se não existir
    python scripts/gerar_parametros.py --forcar  # sobrescreve

As abas:
    Config         -> chave/valor (o que muda a cada trimestre)
    Trimestres     -> janelas de semana e meses de cada trimestre
    Coordenacoes   -> de-para Depto -> Coordenação -> Centro de Custo
    Envelope_OPEX  -> quais pacotes/centros de custo da PLAN ORÇ formam o envelope
"""
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "parametros.xlsx")

CONFIG = [
    ("ano", 2026),
    ("trimestre", 2),
    ("semana_inicio", ""),            # vazio => usa a aba Trimestres
    ("semana_fim", ""),
    ("arquivo_plano", "Plano de Manutenção 2º Trimestre - SP.xlsx"),
    ("arquivo_orcamento", "Orçamento Ger. SP.xlsx"),
    ("aba_diario", "Diário"),
    ("aba_peso", "Planilha de Peso"),
    ("aba_plan_orc", "PLAN ORÇ"),
    ("aba_realizado_analitico", "Realizado Analitico"),
    ("meta_aderencia", 1.0),
    ("faixa_leve", 0.05),
    ("faixa_risco", 0.10),
    ("faixa_critico", 0.15),
    ("rotulo_gerencia", "Gerência"),
    ("origem_pcm", "PCM"),
    ("origem_execucao", "Coordenação"),
    ("plano_sim", "Sim"),
    ("plano_nao", "Não"),
]

TRIMESTRES = pd.DataFrame(
    [[1, 1, 13, "JAN;FEV;MAR"],
     [2, 14, 26, "ABR;MAI;JUN"],
     [3, 27, 39, "JUL;AGO;SET"],
     [4, 40, 52, "OUT;NOV;DEZ"]],
    columns=["Trimestre", "SemanaInicio", "SemanaFim", "Meses"],
)

COORDENACOES = pd.DataFrame(
    [["V.SP.IPA", "Paranapiacaba", "CCR097", "Sim"],
     ["V.SP.IPG", "Piaçaguera", "CCR098", "Sim"],
     ["V.SP.PJU", "Jundiaí", "CCR063", "Sim"],
     ["", "Gerência", "CGE041", "Sim"]],
    columns=["Depto", "Coordenacao", "CentroCusto", "EntraNaGerencia"],
)

ENVELOPE = [
    ("pacotes_incluir", "PM03;PM05;MATERIAIS INDIRET DE MANUTENÇÃO/OPERAÇÃO"),
    ("centros_custo", "CCR097;CCR098;CCR063;CGE041"),
    ("dre_realizado_sap", "DRE011132-MANUTENÇÃO"),
    ("usar_realizado_sap_de", "PLAN ORÇ"),   # ou "Realizado Analitico"
]


def main() -> None:
    if os.path.exists(DESTINO) and "--forcar" not in sys.argv:
        print(f"[skip] {DESTINO} já existe. Use --forcar para sobrescrever.")
        return
    with pd.ExcelWriter(DESTINO, engine="openpyxl") as xw:
        pd.DataFrame(CONFIG, columns=["Parametro", "Valor"]).to_excel(
            xw, sheet_name="Config", index=False)
        TRIMESTRES.to_excel(xw, sheet_name="Trimestres", index=False)
        COORDENACOES.to_excel(xw, sheet_name="Coordenacoes", index=False)
        pd.DataFrame(ENVELOPE, columns=["Parametro", "Valor"]).to_excel(
            xw, sheet_name="Envelope_OPEX", index=False)
    print(f"[ok] {DESTINO} gerado.")


if __name__ == "__main__":
    main()
