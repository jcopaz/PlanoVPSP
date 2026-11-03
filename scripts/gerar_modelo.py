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
import unicodedata
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from core import modelo as M  # noqa: E402

PASTA = os.path.join(RAIZ, "modelos")
LINHAS_VALIDACAO = 3000          # menus suspensos valem até esta linha

AZUL = PatternFill("solid", fgColor="0052CC")
CINZA = PatternFill("solid", fgColor="F1F5F9")
BRANCO_NEGRITO = Font(bold=True, color="FFFFFF")

COLS_DATA = {"Data Planejada", "Data", "Prazo"}
COLS_NUM = {"Quantidade Programada", "Quantidade Realizada", "Peso"}

LEIAME = [
    ("Plano de Manutenção VP — modelo do trimestre", True),
    ("", False),
    ("Quem preenche cada aba", True),
    ("Pesos — PCM, 1x por trimestre: peso RELATIVO de cada meta em cada Depto. "
     "Não precisa somar 1: o sistema normaliza entre as metas que têm plano.", False),
    ("Plano_PCM — 1 pessoa, no início do trimestre: copie as linhas da planilha do PCM "
     "(uma linha por dia/meta/equipe).", False),
    ("Lancamentos — programadores, ao longo do trimestre: o que foi executado. "
     "No Plano = Sim (atividade do plano) ou Não (extra plano).", False),
    ("Listas — opções dos menus suspensos (equipes, justificativas...). Pode acrescentar itens.", False),
    ("", False),
    ("Regras", True),
    ("• Não mude o nome das abas nem dos cabeçalhos.", False),
    ("• Descrição Meta deve existir na aba Pesos para o mesmo Depto (senão a linha não pesa na curva).", False),
    ("• Datas no formato dd/mm/aaaa. A semana é calculada automaticamente (igual ao WEEKNUM do Excel).", False),
    ("• Não há fórmulas: Semana, Coordenação e pesos são calculados pelo dashboard.", False),
    ("• Quantidade Realizada menor que a programada → preencha a Justificativa.", False),
    ("", False),
    ("Depois de preencher", True),
    ("Salve na pasta do projeto e, no parametros.xlsx (aba Config), aponte arquivo_plano "
     "para este arquivo e ajuste trimestre.", False),
]


# --------------------------------------------------------------------------- #
def _aba_tabela(wb, nome, colunas, linhas, nome_tabela):
    ws = wb.create_sheet(nome)
    ws.append(colunas)
    for ln in linhas:
        ws.append([ln.get(c) for c in colunas])
    n = max(ws.max_row, 2)
    ref = f"A1:{get_column_letter(len(colunas))}{n}"
    tab = Table(displayName=nome_tabela, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tab)
    for i, c in enumerate(colunas, start=1):
        cel = ws.cell(row=1, column=i)
        cel.fill, cel.font = AZUL, BRANCO_NEGRITO
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        letra = get_column_letter(i)
        ws.column_dimensions[letra].width = max(12, min(40, len(c) + 6))
        if c in COLS_DATA:
            for r in range(2, LINHAS_VALIDACAO + 1):
                ws.cell(row=r, column=i).number_format = "dd/mm/yyyy"
        elif c in COLS_NUM:
            for r in range(2, n + 1):
                ws.cell(row=r, column=i).number_format = "#,##0.00"
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    return ws


def _aba_listas(wb, listas):
    ws = wb.create_sheet(M.ABA_LISTAS)
    nomes = list(listas)
    for i, nome in enumerate(nomes, start=1):
        cel = ws.cell(row=1, column=i, value=nome)
        cel.fill, cel.font = AZUL, BRANCO_NEGRITO
        for r, v in enumerate(listas[nome], start=2):
            ws.cell(row=r, column=i, value=v)
        ws.column_dimensions[get_column_letter(i)].width = 32
    ws.freeze_panes = "A2"
    return {nome: get_column_letter(i) for i, nome in enumerate(nomes, start=1)}


def _nome_lista(wb, origem, letras_listas) -> str:
    """Cria (uma vez) um intervalo nomeado para a lista e devolve o nome.
    Menus suspensos via nome funcionam em qualquer versão do Excel."""
    sem_acento = unicodedata.normalize("NFKD", origem.split(":")[-1]).encode("ascii", "ignore").decode()
    nome = "lst" + "".join(ch for ch in sem_acento.title() if ch.isalnum())
    if nome not in wb.defined_names:
        if origem.startswith("Pesos:"):
            letra = get_column_letter([c.value for c in wb[M.ABA_PESOS][1]].index(origem.split(":", 1)[1]) + 1)
            aba = M.ABA_PESOS
        else:
            letra, aba = letras_listas[origem], M.ABA_LISTAS
        wb.defined_names[nome] = DefinedName(nome, attr_text=f"{aba}!${letra}$2:${letra}$500")
    return nome


def _validacoes(wb, letras_listas):
    for (aba, coluna), origem in M.VALIDACOES.items():
        ws = wb[aba]
        cab = [c.value for c in ws[1]]
        if coluna not in cab:
            continue
        formula = "=" + _nome_lista(wb, origem, letras_listas)
        dv = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True,
                            errorTitle="Valor fora da lista",
                            error=f"Escolha um valor da lista ({origem}). Para incluir um novo, "
                                  f"acrescente na aba {origem.split(':')[0] if ':' in origem else M.ABA_LISTAS}.")
        letra_col = get_column_letter(cab.index(coluna) + 1)
        dv.add(f"{letra_col}2:{letra_col}{LINHAS_VALIDACAO}")
        ws.add_data_validation(dv)
    # Quantidades: número >= 0
    for aba in (M.ABA_PLANO, M.ABA_LANC):
        ws = wb[aba]
        cab = [c.value for c in ws[1]]
        for coluna in ("Quantidade Programada", "Quantidade Realizada"):
            if coluna in cab:
                letra_col = get_column_letter(cab.index(coluna) + 1)
                dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0",
                                    allow_blank=True, showErrorMessage=True,
                                    errorTitle="Quantidade inválida", error="Informe um número ≥ 0.")
                dv.add(f"{letra_col}2:{letra_col}{LINHAS_VALIDACAO}")
                ws.add_data_validation(dv)


def gerar(destino: str, pesos, plano, lanc, listas) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = M.ABA_LEIAME
    for txt, negrito in LEIAME:
        ws.append([txt])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=negrito, size=14 if ws.max_row == 1 else 11)
    ws.column_dimensions["A"].width = 120
    ws.sheet_view.showGridLines = False

    _aba_tabela(wb, M.ABA_PESOS, M.COLS_PESOS, pesos, "tbPesos")
    _aba_tabela(wb, M.ABA_PLANO, M.COLS_PLANO, plano, "tbPlanoPCM")
    _aba_tabela(wb, M.ABA_LANC, M.COLS_LANC, lanc, "tbLancamentos")
    letras = _aba_listas(wb, listas)
    _validacoes(wb, letras)
    for nome in (M.ABA_PESOS, M.ABA_PLANO, M.ABA_LANC):
        wb[nome].sheet_properties.tabColor = "0052CC"
    wb[M.ABA_LISTAS].sheet_properties.tabColor = "94A3B8"
    wb.active = 0
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    wb.save(destino)


# --------------------------------------------------------------------------- #
# Dados FICTÍCIOS do exemplo (4º tri/2026, semanas 40-52)
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
