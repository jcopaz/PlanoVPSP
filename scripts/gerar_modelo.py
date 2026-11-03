# -*- coding: utf-8 -*-
"""Gera o modelo de planilha do trimestre (formato v3, sem fórmulas).

    python scripts/gerar_modelo.py            # modelos/Modelo_Plano_Trimestre.xlsx (em branco)
                                              # + modelos/Exemplo_Plano_Trimestre.xlsx (dados fictícios)
    python scripts/gerar_modelo.py --forcar   # sobrescreve os existentes

O layout (abas/colunas/menus) vem de ``core/modelo.py``. O exemplo usa dados
FICTÍCIOS (4º tri/2026) só para mostrar o preenchimento e testar o dashboard:
aponte ``arquivo_plano`` do parametros.xlsx para ele e use ``trimestre = 4``.
"""
import os
import random
import sys
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import modelo as M  # noqa: E402
from core.planilha import gerar  # noqa: E402

PASTA = os.path.join(RAIZ, "modelos")


# --------------------------------------------------------------------------- #
# Dados FICTÍCIOS do exemplo (4º tri/2026, semanas 40-53)
# --------------------------------------------------------------------------- #
METAS_EX = {   # meta: (grupo, unidade, SLA, quantidade típica por dia)
    "SOLDA": ("Manutenção Preventiva", "UN", 2, 2),
    "DORMENTE TRAVAMENTO": ("Manutenção Preventiva", "UN", 56, 12),
    "JACARÉ": ("AMV/Travessão", "UN", 1, 1),
    "CONTRATRILHO": ("AMV/Travessão", "UN", 1, 1),
    "SOCARIA E NIVEL. MANUAL LINHA": ("Manutenção Corretiva", "M", 62, 20),
    "LIMPEZA DE LASTRO MANUAL": ("Manutenção Corretiva", "M³", 5, 5),
}
PESOS_EX = {"SOLDA": 30, "DORMENTE TRAVAMENTO": 10, "JACARÉ": 25, "CONTRATRILHO": 15,
            "SOCARIA E NIVEL. MANUAL LINHA": 12, "LIMPEZA DE LASTRO MANUAL": 8}
DEPTOS_EX = ["V.SP.IPA", "V.SP.IPG", "V.SP.PJU"]
EQUIPES_EX = {d: [f"EQ-{d[-3:]}-{i:02d}" for i in (1, 2)] for d in DEPTOS_EX}
PROGRAMADORES_EX = {"V.SP.IPA": "Programador IPA", "V.SP.IPG": "Programador IPG",
                    "V.SP.PJU": "Programador PJU"}


def _exemplo():
    rnd = random.Random(42)
    pesos = [{"Depto": d, "Grupo": g, "Descrição Meta": m, "Peso": PESOS_EX[m], "Unidade": u, "SLA": sla}
             for d in DEPTOS_EX for m, (g, u, sla, _) in METAS_EX.items()]

    inicio, fim = date(2026, 10, 1), date(2026, 12, 31)
    dias_uteis = [inicio + timedelta(n) for n in range((fim - inicio).days + 1)
                  if (inicio + timedelta(n)).weekday() < 5]
    plano = []
    for d in DEPTOS_EX:
        for m, (_, _, _, qtd) in METAS_EX.items():
            for dia in sorted(rnd.sample(dias_uteis, 4)):
                plano.append({"Depto": d, "Data Planejada": dia, "Descrição Meta": m,
                              "Equipe": rnd.choice(EQUIPES_EX[d]),
                              "Tipo Material": "Novo" if m in ("SOLDA", "JACARÉ", "CONTRATRILHO") else None,
                              "Quantidade Programada": qtd})
    plano.sort(key=lambda r: (r["Data Planejada"], r["Depto"]))

    # Lançamentos até 31/10 (meio do trimestre) + alguns extra plano
    hoje = date(2026, 10, 31)
    justif = ["Intervalo não concedido", "Mau tempo", "Falta de equipamento", "Baixo efetivo da equipe"]
    lanc = []
    for r in plano:
        if r["Data Planejada"] > hoje:
            continue
        q = r["Quantidade Programada"]
        feito = q if rnd.random() < 0.7 else round(q * rnd.choice([0, 0.5]), 1)
        lanc.append({"Depto": r["Depto"], "Data": r["Data Planejada"], "Descrição Meta": r["Descrição Meta"],
                     "Equipe": r["Equipe"], "Tipo Material": r["Tipo Material"],
                     "Quantidade Programada": q, "Quantidade Realizada": feito, "No Plano": "Sim",
                     "Justificativa": rnd.choice(justif) if feito < q else None,
                     "Status": "Aberto" if feito < q else None,
                     "Programador": PROGRAMADORES_EX[r["Depto"]]})
    for d in DEPTOS_EX:
        dia = rnd.choice([x for x in dias_uteis if x <= hoje])
        lanc.append({"Depto": d, "Data": dia, "Descrição Meta": "DORMENTE TRAVAMENTO",
                     "Equipe": EQUIPES_EX[d][0], "Quantidade Programada": 4, "Quantidade Realizada": 4,
                     "No Plano": "Não", "Observação": "Atividade extra plano (exemplo)",
                     "Programador": PROGRAMADORES_EX[d]})
    lanc.sort(key=lambda r: (r["Data"], r["Depto"]))

    listas = dict(M.LISTAS_PADRAO)
    listas["Equipe"] = [e for d in DEPTOS_EX for e in EQUIPES_EX[d]]
    return pesos, plano, lanc, listas


def main() -> None:
    forcar = "--forcar" in sys.argv
    alvos = {
        os.path.join(PASTA, "Modelo_Plano_Trimestre.xlsx"): ([], [], [], M.LISTAS_PADRAO),
        os.path.join(PASTA, "Exemplo_Plano_Trimestre.xlsx"): _exemplo(),
    }
    for destino, (pesos, plano, lanc, listas) in alvos.items():
        if os.path.exists(destino) and not forcar:
            print(f"[skip] {destino} já existe. Use --forcar para sobrescrever.")
            continue
        gerar(destino, pesos, plano, lanc, listas)
        print(f"[ok] {destino}")


if __name__ == "__main__":
    main()
