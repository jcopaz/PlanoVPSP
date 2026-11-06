# Testes da regra de aderência do PCM (docs/REGRA_ADERENCIA_PCM.md, seção 3).
#   python -m pytest tests        (ou: python tests/test_regra_pcm.py)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from core import config, motor, planilha


def _resultado(lanc):
    p0 = config.carregar()
    cfg = {k: str(v) for k, v in p0.cfg.items()}
    c = p0.coordenacoes[p0.coordenacoes["Depto"] != ""]
    coords = pd.DataFrame({"depto": c["Depto"], "coordenacao": c["Coordenacao"], "centro_custo": c["CentroCusto"],
                           "entra_gerencia": c["EntraNaGerencia"].eq("Sim")})
    p = motor.parametros(cfg, coords, 2026, 4, 40, 53)
    pesos = pd.DataFrame([
        {"Depto": "V.SP.IPA", "Grupo": "AMV/Travessão", "Descrição Meta": "JACARÉ", "Peso": 0.5},
        {"Depto": "V.SP.IPA", "Grupo": "Manu. Preventiva", "Descrição Meta": "JIC", "Peso": 0.5},
        {"Depto": "V.SP.IPA", "Grupo": "Drenagem", "Descrição Meta": "LIMPEZA DE CANALETA", "Peso": 0.4},
    ])
    plano = pd.DataFrame([{"Depto": "V.SP.IPA", "Data Planejada": "2026-10-05", "Descrição Meta": m,
                           "Quantidade Programada": q} for m, q in (("JACARÉ", 4), ("JIC", 10), ("LIMPEZA DE CANALETA", 100))])
    return motor.calcular_trimestre(pesos, plano, pd.DataFrame(lanc), None, p).coords["Paranapiacaba"]


def test_teto_por_meta_e_grupo_fora():
    # Jacaré: 20 de 4 conta 4 (100%); JIC: 5 de 10 (50%); Drenagem não pesa -> 0,5*1 + 0,5*0,5 = 0,75
    rf = _resultado([
        {"Depto": "V.SP.IPA", "Data": "2026-10-06", "Descrição Meta": "JACARÉ", "Quantidade Realizada": 20, "No Plano": "Sim"},
        {"Depto": "V.SP.IPA", "Data": "2026-10-13", "Descrição Meta": "JIC", "Quantidade Realizada": 5, "No Plano": "Sim"},
        {"Depto": "V.SP.IPA", "Data": "2026-10-13", "Descrição Meta": "LIMPEZA DE CANALETA", "Quantidade Realizada": 50, "No Plano": "Sim"},
    ])
    assert abs(rf.kpis["aderencia_atual"] - 0.75) < 1e-9
    tab = rf.tabela_itens
    assert abs(tab["Contribuição"].sum() - 0.75) < 1e-9          # Σ Contribuição = aderência da visão
    assert abs(tab["Peso na Visão"].sum() - 1.0) < 1e-9
    assert tab.set_index("Descrição Meta").loc["JACARÉ", "Aderência PCM"] == 1.0


def test_fora_do_plano_nao_conta():
    rf = _resultado([{"Depto": "V.SP.IPA", "Data": "2026-10-06", "Descrição Meta": "JACARÉ",
                      "Quantidade Realizada": 4, "No Plano": "Não"}])
    assert rf.kpis["aderencia_atual"] == 0.0


def test_gerencia_soma_coordenacoes():
    """Gerência (data (10), 1º tri/2026): meta pesa Σ pesos das coordenações; DEPTO soma o volume de todas
    (sobra de uma cobre falta de outra); ATIVO soma o realizado limitado de cada uma; ÷ nº de coordenações."""
    p0 = config.carregar()
    cfg = {k: str(v) for k, v in p0.cfg.items()}
    cfg["metas_medicao_depto"] = "X"
    c = p0.coordenacoes[p0.coordenacoes["Depto"] != ""]
    coords = pd.DataFrame({"depto": c["Depto"], "coordenacao": c["Coordenacao"], "centro_custo": c["CentroCusto"],
                           "entra_gerencia": c["EntraNaGerencia"].eq("Sim")})
    p = motor.parametros(cfg, coords, 2026, 4, 40, 53)
    dep = ("V.SP.IPA", "V.SP.IPG", "V.SP.PJU")
    pesos = pd.DataFrame([{"Depto": d, "Grupo": "G", "Descrição Meta": m, "Peso": .5} for d in dep for m in ("X", "Y")])
    plano = pd.DataFrame([{"Depto": d, "Data Planejada": "2026-10-05", "Descrição Meta": m, "Quantidade Programada": 10}
                          for d in dep for m in ("X", "Y")])
    real = {("V.SP.IPA", "X"): 20, ("V.SP.IPA", "Y"): 10, ("V.SP.IPG", "Y"): 20, ("V.SP.PJU", "X"): 10}
    lanc = pd.DataFrame([{"Depto": d, "Data": "2026-10-06", "Descrição Meta": m, "Quantidade Realizada": q, "No Plano": "Sim"}
                         for (d, m), q in real.items()])
    r = motor.calcular_trimestre(pesos, plano, lanc, None, p)
    coord = {k: round(v.kpis["aderencia_atual"], 6) for k, v in r.coords.items()}
    assert coord == {"Jundiaí": 0.5, "Paranapiacaba": 1.0, "Piaçaguera": 0.5}         # média seria 66,67%
    # X (DEPTO): 30 de 30 -> 1 × 1,5 ; Y (ATIVO): (10+10+0)/30 × 1,5 = 1,0  -> (1,5 + 1,0) / 3
    assert abs(r.gerencia.kpis["aderencia_atual"] - 2.5 / 3) < 1e-9
    assert abs(r.gerencia.tabela_itens["Contribuição"].sum() - 2.5 / 3) < 1e-9


def test_lista_de_ativos_sem_repetir_e_por_depto():
    df = pd.DataFrame({"Ativo": ["AMV  01", "AMV 01", None, "PN 2", "PN 3"],
                       "Coord": ["sp.ipa", "SP.IPA", "SP.IPA", "V.SP.PJU", "OUTRA"]})
    nomes = {"SP.IPA": "V.SP.IPA", "V.SP.PJU": "V.SP.PJU"}
    lista, sem_depto = planilha.lista_de_ativos(df, "Ativo", "Coord", nomes)
    assert list(zip(lista["valor"], lista["depto"])) == [("PN 3", ""), ("AMV 01", "V.SP.IPA"), ("PN 2", "V.SP.PJU")]
    assert sem_depto == 1
    assert planilha.lista_de_ativos(df, "Ativo", None, nomes)[0]["depto"].eq("").all()


if __name__ == "__main__":
    test_teto_por_meta_e_grupo_fora()
    test_fora_do_plano_nao_conta()
    test_gerencia_soma_coordenacoes()
    test_lista_de_ativos_sem_repetir_e_por_depto()
    print("ok — regra do PCM")
