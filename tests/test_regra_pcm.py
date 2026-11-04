# Testes da regra de aderência do PCM (docs/REGRA_ADERENCIA_PCM.md, seção 3).
#   python -m pytest tests        (ou: python tests/test_regra_pcm.py)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from core import config, motor


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


if __name__ == "__main__":
    test_teto_por_meta_e_grupo_fora()
    test_fora_do_plano_nao_conta()
    print("ok — regra do PCM")
