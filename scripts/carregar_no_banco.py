# -*- coding: utf-8 -*-
"""Carga em lote no banco (histórico de trimestres) — mesmo efeito da tela Dados → Upload.

    # planilhas de trimestre (modelo v3, backup exportado ou planilha antiga); 1 trimestre por arquivo
    python scripts/carregar_no_banco.py "Plano 1T2026.xlsx" "Plano de Manutenção 2º Trimestre - SP.xlsx"

    # plano do PCM (pesos + planejamento congelado) — mantém os lançamentos do trimestre
    python scripts/carregar_no_banco.py --pcm "data (9).xlsx" --planejamento "Planejamento PCM.xlsx"

O trimestre de cada planilha é deduzido pelas datas do plano (ou dos lançamentos);
use --ano/--tri para forçar quando houver 1 arquivo só. Pesos+Plano e Lançamentos
do trimestre são SUBSTITUÍDOS pelo conteúdo do arquivo.
"""
import argparse
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import config, importar_pcm, motor, planilha  # noqa: E402
from database import queries as q  # noqa: E402
from database.client import descricao_banco  # noqa: E402

USUARIO = "carga-script"


def _equipes(*dfs) -> set:
    pares = set()
    for df in dfs:
        if df is not None and not df.empty and "Equipe" in df:
            pares |= {(str(d).strip().upper(), str(e).strip()) for d, e in zip(df["Depto"], df["Equipe"])
                      if pd.notna(d) and pd.notna(e) and str(e).strip()}
    return pares


def carregar_planilha(caminho, ano=None, tri=None) -> None:
    pesos, plano, lanc = planilha.ler(caminho, config.carregar())
    if not (ano and tri):
        achado = planilha.trimestre_dos_dados(plano, lanc)
        if not achado:
            sys.exit(f"[erro] {caminho}: sem datas para deduzir o trimestre; use --ano/--tri.")
        ano, tri = achado
    tid = q.garantir_trimestre(ano, tri, USUARIO)
    n_p, n_l = q.substituir_plano(tid, pesos, plano, USUARIO)
    n_la = q.substituir_lancamentos(tid, lanc, USUARIO)
    q.completar_catalogo(pesos, USUARIO)
    q.adicionar_equipes(_equipes(plano, lanc), USUARIO)
    print(f"[ok] {os.path.basename(caminho)} -> {tri}º tri/{ano}: {n_p} pesos, {n_l} plano, {n_la} lançamentos")


def carregar_pcm(pesos_arq, plan_arq=None) -> None:
    tri_ano = importar_pcm.trimestre_do_export(pd.read_excel(pesos_arq, header=None))
    if not tri_ano:
        sys.exit("[erro] trimestre não identificado no export do PCM.")
    ano, tri = tri_ano
    p = motor.parametros(q.ler_config(), q.listar_coordenacoes(), ano, tri, *q.janela_semanas(ano, tri))
    r = importar_pcm.importar(pesos_arq, p, q.listar_catalogo(), plan_arq)
    novo = importar_pcm.atualizar_metas_depto(q.ler_config().get("metas_medicao_depto", ""),
                                              importar_pcm.tipos_de_medicao(pesos_arq))
    q.salvar_config({"metas_medicao_depto": novo}, USUARIO)
    for av in r.avisos:
        print(f"[aviso] {av}")
    pesos, plano = pd.DataFrame(r.pesos), pd.DataFrame(r.plano)
    tid = q.garantir_trimestre(ano, tri, USUARIO)
    n_p, n_l = q.substituir_plano(tid, pesos, plano, USUARIO)
    q.completar_catalogo(pesos, USUARIO)
    q.adicionar_equipes(_equipes(plano), USUARIO)
    print(f"[ok] PCM -> {tri}º tri/{ano}: {n_p} pesos, {n_l} linhas de plano (lançamentos mantidos)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planilhas", nargs="*")
    ap.add_argument("--pcm")
    ap.add_argument("--planejamento")
    ap.add_argument("--ano", type=int)
    ap.add_argument("--tri", type=int, choices=[1, 2, 3, 4])
    a = ap.parse_args()
    print(f"Banco: {descricao_banco()}")
    for arq in a.planilhas:
        carregar_planilha(config.caminho(arq), a.ano if len(a.planilhas) == 1 else None,
                          a.tri if len(a.planilhas) == 1 else None)
    if a.pcm:
        carregar_pcm(config.caminho(a.pcm), config.caminho(a.planejamento) if a.planejamento else None)
    if not (a.planilhas or a.pcm):
        ap.print_help()


if __name__ == "__main__":
    main()
