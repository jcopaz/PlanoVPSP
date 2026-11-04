# -*- coding: utf-8 -*-
"""Confere a aderência do app contra o número oficial do PCM (Power BI, "Adr_Ativo").

Use sempre que o PCM mudar algo (pesos, colunas, regra) ou a cada trimestre fechado:

    python scripts/conferir_pcm.py --pesos "data (9).xlsx" \
        --planejado "Planejado 1 ao 3º Tri.xlsx" --planejamento-atual "Planejamento PCM.xlsx" \
        --realizado "Realizado 1 ao 4º Tri.xlsx" --referencia referencia_pcm.csv

--referencia: CSV (separador ;) com os números do Power BI, uma linha por trimestre x coordenação:
    ano;trimestre;depto;aderencia
    2026;1;V.SP.IPA;0,9927
(aderência em fração ou em %, vírgula ou ponto). Sem --referencia, só mostra os números do app.

Roda o MESMO código do app (core/importar_pcm.py + core/motor.py), em memória, sem banco.
Regra e histórico da investigação: docs/REGRA_ADERENCIA_PCM.md.
"""
import argparse
import os
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import config, importar_pcm, motor  # noqa: E402
from database.queries import janela_semanas  # noqa: E402

TOLERANCIA = 0.005   # 0,5 ponto percentual


def _referencia(caminho: str) -> dict:
    ref = pd.read_csv(caminho, sep=";", dtype=str)
    ref["aderencia"] = pd.to_numeric(ref["aderencia"].str.replace("%", "").str.replace(",", "."), errors="coerce")
    ref.loc[ref["aderencia"] > 1.5, "aderencia"] /= 100
    return {(int(a), int(t), d.strip().upper()): v for a, t, d, v in ref[["ano", "trimestre", "depto", "aderencia"]].itertuples(index=False)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pesos", required=True)
    ap.add_argument("--planejado", help="export Planejado (1 ou mais trimestres)")
    ap.add_argument("--planejamento-atual", help="Planejamento PCM do trimestre corrente (opcional)")
    ap.add_argument("--realizado", required=True)
    ap.add_argument("--referencia")
    a = ap.parse_args()

    p0 = config.carregar()
    deptos = set(p0.coord_por_depto())
    cfg = {k: str(v) for k, v in p0.cfg.items()}
    c = p0.coordenacoes[p0.coordenacoes["Depto"] != ""]
    coords = pd.DataFrame({"depto": c["Depto"], "coordenacao": c["Coordenacao"], "centro_custo": c["CentroCusto"],
                           "entra_gerencia": c["EntraNaGerencia"].eq("Sim")})

    hist, avisos = {}, []
    for arq in (a.planejado, a.planejamento_atual):
        if arq:
            h, av = importar_pcm.montar_historico(deptos, arq, None, a.pesos)
            hist.update(h)
            avisos += av
    h, av = importar_pcm.montar_historico(deptos, None, a.realizado, None, trimestres_com_plano=set(hist))
    for k, d in h.items():
        hist.setdefault(k, {}).update(d)
    avisos += av
    for x in avisos:
        print("[aviso]", x)

    ref = _referencia(a.referencia) if a.referencia else {}
    nome = dict(zip(coords["coordenacao"], coords["depto"]))
    ok = total = 0
    for (ano, tri), d in sorted(hist.items()):
        if "plano" not in d:
            continue
        p = motor.parametros(cfg, coords, ano, tri, *janela_semanas(ano, tri))
        r = motor.calcular_trimestre(d["pesos"], d["plano"], d.get("lanc", pd.DataFrame()), None, p)
        linhas = [(r.rotulo_gerencia, None, r.gerencia)] + [(cn, nome.get(cn), rf) for cn, rf in r.coords.items()]
        print(f"\n{tri}º tri/{ano}")
        for visao, depto, rf in linhas:
            app = rf.kpis["aderencia_atual"]
            pcm = ref.get((ano, tri, depto)) if depto else None
            if pcm is None:
                print(f"  {visao:14s} app {app:7.2%}")
                continue
            total += 1
            bate = abs(app - pcm) <= TOLERANCIA
            ok += bate
            print(f"  {visao:14s} app {app:7.2%}   PCM {pcm:7.2%}   {'OK' if bate else 'DIVERGE'} ({(app - pcm) * 100:+.2f} p.p.)")
    if ref and not total:
        sys.exit("[erro] nenhuma linha da --referencia casou com ano/trimestre/depto do app.")
    if total:
        print(f"\n{ok} de {total} dentro de {TOLERANCIA * 100:.1f} p.p.")
        sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
