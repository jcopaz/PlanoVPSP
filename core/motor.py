# core/motor.py — Ponte entre o banco e o motor de cálculo
#
# O cálculo em si (curvas, KPIs, rateio OPEX) continua em core/fisico.py e
# core/financeiro.py, validado contra a planilha antiga do 2º tri/2026. Este
# módulo só:
#   1. monta o objeto Parametros a partir do banco (config + coordenações +
#      janela de semanas do trimestre) — antes vinha do parametros.xlsx;
#   2. calcula o resultado de um trimestre (Gerência e cada coordenação);
#   3. monta o histórico (trimestre a trimestre e por ano) para a Evolução.
# Não depende de Streamlit (dá para usar em script/teste).
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config, dados, fisico


# region ====================== SESSÃO 1: Parâmetros ======================

def parametros(cfg: dict, coords: pd.DataFrame, ano: int, tri: int,
               sem_ini: int, sem_fim: int) -> config.Parametros:
    """Parametros equivalente ao do parametros.xlsx, mas vindo do banco."""
    base = {k: v for k, v in cfg.items() if not k.startswith(("env.", "_"))}
    base.update({"ano": ano, "trimestre": tri, "semana_inicio": sem_ini, "semana_fim": sem_fim})
    p = config.Parametros(cfg={**config._DEFAULT_CONFIG, **base},
                          envelope={k[4:]: v for k, v in cfg.items() if k.startswith("env.")})
    if coords is not None and not coords.empty:
        p.coordenacoes = pd.DataFrame({
            "Depto": coords["depto"].astype(str),
            "Coordenacao": coords["coordenacao"].astype(str),
            "CentroCusto": coords["centro_custo"].fillna("").astype(str),
            "EntraNaGerencia": coords["entra_gerencia"].map(lambda b: "Sim" if bool(b) else "Não"),
        })
    t = p.trimestres.copy()
    t.loc[t["Trimestre"] == tri, ["SemanaInicio", "SemanaFim"]] = [sem_ini, sem_fim]
    p.trimestres = t
    p.origem = "banco de dados"
    return p

# endregion


# region ====================== SESSÃO 2: Resultado de um trimestre ======================

@dataclass
class ResultadoTrimestre:
    p: config.Parametros
    base: pd.DataFrame                      # formato canônico (todas as linhas)
    avisos: list[str]
    sem_ini: int
    sem_fim: int
    gerencia: fisico.ResultadoFisico | None = None
    coords: dict[str, fisico.ResultadoFisico] = field(default_factory=dict)

    @property
    def rotulo_gerencia(self) -> str:
        return self.p.g("rotulo_gerencia", str, "Gerência")


def calcular_trimestre(pesos, plano, lanc, catalogo, p: config.Parametros) -> ResultadoTrimestre:
    sem_ini, sem_fim = p.semanas
    base, _, avisos = dados.montar_canonico(pesos, plano, lanc, p, catalogo)
    r = ResultadoTrimestre(p=p, base=base, avisos=avisos, sem_ini=sem_ini, sem_fim=sem_fim)
    r.gerencia = fisico.calcular(base, p, r.rotulo_gerencia, sem_ini, sem_fim)
    for coord in sorted(base["Coordenação"].dropna().unique()):
        r.coords[str(coord)] = fisico.calcular(base, p, str(coord), sem_ini, sem_fim)
    return r


def linha_resumo(visao: str, rf: fisico.ResultadoFisico) -> dict:
    k = rf.kpis
    meta_atual = rf.curva.loc[rf.curva["Semana"] == rf.semana_atual, "meta_pcm"]
    meta_atual = float(meta_atual.iloc[0]) if len(meta_atual) else 0.0
    return {
        "Visão": visao,
        "Meta PCM até a semana": meta_atual,
        "Realizado": k["aderencia_atual"],
        "Gap na semana": k["aderencia_atual"] - meta_atual,
        "Projeção de fechamento": k["aderencia_projetada"],
        "Mín. semanal p/ meta": k["minimo_semanal_para_meta"],
        "Tendência": k["tendencia"],
        "Último lançamento": k["ultimo_preenchimento"],
        "Semana atual": rf.semana_atual,
    }


def tabela_resumo(r: ResultadoTrimestre) -> pd.DataFrame:
    linhas = [linha_resumo(r.rotulo_gerencia, r.gerencia)] if r.gerencia else []
    linhas += [linha_resumo(c, rf) for c, rf in r.coords.items()]
    return pd.DataFrame(linhas)

# endregion


# region ====================== SESSÃO 3: Histórico (Evolução) ======================

def historico(resultados: dict[str, ResultadoTrimestre]) -> pd.DataFrame:
    """Uma linha por trimestre x visão (Gerência + coordenações).
    resultados: {"4º tri/2026": ResultadoTrimestre, ...} em ordem cronológica."""
    linhas = []
    for rotulo, r in resultados.items():
        ano = r.p.ano
        for visao, rf in [(r.rotulo_gerencia, r.gerencia), *r.coords.items()]:
            if rf is None:
                continue
            k = rf.kpis
            linhas.append({"Período": rotulo, "Ano": ano, "Trimestre": r.p.trimestre, "Visão": visao,
                           "Aderência": k["aderencia_atual"], "Projeção": k["aderencia_projetada"],
                           "Concluído": k["semanas_restantes"] <= 0, "Tendência": k["tendencia"]})
    return pd.DataFrame(linhas)


def historico_anual(hist: pd.DataFrame) -> pd.DataFrame:
    """Aderência do ano = média das aderências trimestrais (cada trimestre vale
    100% do seu plano, então a média simples é a aderência do ano)."""
    if hist.empty:
        return hist
    a = (hist.groupby(["Ano", "Visão"], as_index=False)
         .agg(Aderência=("Aderência", "mean"), Trimestres=("Trimestre", "nunique")))
    a["Período"] = a["Ano"].astype(str)
    return a

# endregion
