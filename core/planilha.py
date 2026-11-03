# core/planilha.py — Planilha do trimestre (modelo v3) <-> dados
#
# Escrita: montar_workbook() / gerar() / para_bytes() montam o Excel no modelo
#   v3 (LEIA-ME, Pesos, Plano_PCM, Lancamentos, Listas) com menus suspensos e
#   validações — usado pelo modelo em branco, pelo importador do PCM e pela
#   exportação de backup do app (tela Dados).
# Leitura: identificar() reconhece o tipo do arquivo enviado e ler() devolve
#   (pesos, plano, lancamentos) com os cabeçalhos do modelo v3, aceitando:
#     - modelo v3 (este layout)
#     - planilha antiga (Diário + Planilha de Peso, com fórmulas)
#   Os exports do PCM (pesos e planejamento congelado) ficam em core/importar_pcm.py.
from __future__ import annotations

import io
import os
import unicodedata

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from . import config, dados
from . import modelo as M

LINHAS_VALIDACAO = 3000          # menus suspensos valem até esta linha

AZUL = PatternFill("solid", fgColor="0052CC")
BRANCO_NEGRITO = Font(bold=True, color="FFFFFF")

COLS_DATA = {"Data Planejada", "Data", "Prazo"}
COLS_NUM = {"Quantidade Programada", "Quantidade Realizada", "Peso"}

LEIAME = [
    ("Plano de Manutenção VP — modelo do trimestre", True),
    ("", False),
    ("Quem preenche cada aba", True),
    ("Pesos — PCM, 1x por trimestre: peso de cada meta em cada Depto (Peso Item Redist). "
     "Não precisa somar 1: o sistema normaliza entre as metas que têm plano.", False),
    ("Plano_PCM — 1 pessoa, no início do trimestre: visão congelada do PCM "
     "(uma linha por dia/meta/equipe). É a curva planejada.", False),
    ("Lancamentos — programadores, ao longo do trimestre: o que foi executado. "
     "No Plano = Sim (atividade do plano) ou Não (extra plano).", False),
    ("Listas — opções dos menus suspensos (equipes, justificativas...). Pode acrescentar itens.", False),
    ("", False),
    ("Regras", True),
    ("• Não mude o nome das abas nem dos cabeçalhos.", False),
    ("• Descrição Meta deve existir na aba Pesos para o mesmo Depto (senão a linha não pesa na curva).", False),
    ("• Datas no formato dd/mm/aaaa. A semana é calculada automaticamente (igual ao WEEKNUM do Excel).", False),
    ("• Não há fórmulas: Semana, Coordenação e pesos são calculados pelo sistema.", False),
    ("• Quantidade Realizada menor que a programada → preencha a Justificativa.", False),
    ("• SLA = produção esperada da equipe por dia, na unidade da meta.", False),
    ("", False),
    ("Depois de preencher", True),
    ("Envie pelo app (menu Dados → Upload). Este arquivo também é o backup exportado pelo app.", False),
]


# region ====================== SESSÃO 1: Escrita (modelo v3) ======================

def _registros(x) -> list[dict]:
    if x is None:
        return []
    if isinstance(x, pd.DataFrame):
        df = x.astype(object).where(x.notna(), None)
        return [{k: (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for k, v in r.items()}
                for r in df.to_dict("records")]
    return list(x)


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
            for r in range(2, max(n, LINHAS_VALIDACAO) + 1):
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
        if coluna not in cab or (not origem.startswith("Pesos:") and origem not in letras_listas):
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


def montar_workbook(pesos, plano, lanc, listas) -> Workbook:
    """pesos/plano/lanc: listas de dicts (ou DataFrames) com os cabeçalhos do modelo v3."""
    pesos, plano, lanc = (_registros(x) for x in (pesos, plano, lanc))
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
    return wb


def gerar(destino: str, pesos, plano, lanc, listas) -> None:
    """Grava o modelo v3 em disco."""
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    montar_workbook(pesos, plano, lanc, listas).save(destino)


def para_bytes(pesos, plano, lanc, listas) -> bytes:
    """Modelo v3 em memória (download no app)."""
    buf = io.BytesIO()
    montar_workbook(pesos, plano, lanc, listas).save(buf)
    return buf.getvalue()

# endregion


# region ====================== SESSÃO 2: Leitura (upload) ======================

def _cabecalho(arquivo, limite=15) -> set[str]:
    bruto = pd.read_excel(arquivo, header=None, nrows=limite)
    return {str(v).strip().lower() for v in bruto.to_numpy().ravel() if isinstance(v, str)}


def identificar(arquivo) -> str:
    """'v3' | 'legado' | 'pcm_pesos' | 'pcm_planejamento' | 'desconhecido'."""
    with pd.ExcelFile(arquivo) as xls:
        nomes = [n.strip().lower() for n in xls.sheet_names]
        if M.eh_modelo(xls.sheet_names):
            return "v3"
        if "diário" in nomes or "diario" in nomes:
            return "legado"
    cab = _cabecalho(arquivo)
    if "peso item redist" in cab:
        return "pcm_pesos"
    if "qtd. plano" in cab and "data" in cab:
        return "pcm_planejamento"
    return "desconhecido"


def ler(arquivo, p: config.Parametros | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(pesos, plano, lancamentos) no modelo v3 a partir de um v3 ou da planilha antiga."""
    tipo = identificar(arquivo)
    if tipo == "v3":
        with pd.ExcelFile(arquivo) as xls:
            return dados.ler_abas_modelo(xls)
    if tipo == "legado":
        return legado_para_v3(arquivo, p or config.carregar())
    raise ValueError(f"Arquivo não reconhecido como planilha do trimestre (tipo: {tipo}).")


def legado_para_v3(arquivo, p: config.Parametros) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Planilha antiga (Diário + Planilha de Peso) -> DataFrames do modelo v3."""
    p.cfg["arquivo_plano"] = arquivo
    dia, peso, _ = dados.carregar_plano(p)
    dia = dia.loc[:, ~dia.columns.duplicated()]       # o Diário antigo repete "Número do Material"
    peso = peso.loc[:, ~peso.columns.duplicated()]
    o_pcm = p.g("origem_pcm", str, "PCM")

    pe = peso.dropna(subset=["Chave Peso"]).copy()
    partes = pe["Chave Peso"].astype(str).str.split("|", n=1, expand=True)
    pesos = pd.DataFrame({"Depto": partes[0], "Grupo": pe.get("Grupo"), "Descrição Meta": partes[1],
                          "Peso": pe.get("Peso Item"), "Unidade": pe.get("Unidade"), "SLA": pe.get("SLA")})

    pcm = dia[dia["Origem Programação"] == o_pcm]
    exe = dia[dia["Origem Programação"] != o_pcm]

    def col(df, nome):
        return df[nome] if nome in df.columns else pd.Series(None, index=df.index, dtype=object)

    plano = pd.DataFrame({
        "Depto": col(pcm, "Depto"), "Data Planejada": col(pcm, "Data Planejada"),
        "Descrição Meta": col(pcm, "Descrição Meta"), "Nº Material": col(pcm, "Número do Material"),
        "Equipe": col(pcm, "Equipe"), "Ativo": col(pcm, "Ativo"), "Equipamento": col(pcm, "Equipamento"),
        "Tipo Material": col(pcm, "Tipo Material"), "Quantidade Programada": col(pcm, "Quantidade Programada"),
        "Observação": col(pcm, "Observação")})
    lanc = pd.DataFrame({
        "Depto": col(exe, "Depto"), "Data": col(exe, "Data Planejada"),
        "Descrição Meta": col(exe, "Descrição Meta"), "Nº Material": col(exe, "Número do Material"),
        "Equipe": col(exe, "Equipe"), "Ativo": col(exe, "Ativo"), "Tipo Material": col(exe, "Tipo Material"),
        "Quantidade Programada": col(exe, "Quantidade Programada"),
        "Quantidade Realizada": col(exe, "QUANTIDADE REALIZADA"), "No Plano": col(exe, "Plano"),
        "Justificativa": col(exe, "Justificativa Padrão"), "Observação": col(exe, "Observação"),
        "Plano de Ação": col(exe, "Plano de ação"), "Responsável": col(exe, "Responsável"),
        "Prazo": col(exe, "Prazo"), "Status": col(exe, "Status")})
    return pesos.reset_index(drop=True), plano.reset_index(drop=True), lanc.reset_index(drop=True)


def trimestre_dos_dados(plano: pd.DataFrame, lanc: pd.DataFrame) -> tuple[int, int] | None:
    """(ano, trimestre) mais frequente nas datas do plano (ou dos lançamentos)."""
    for df, col in ((plano, "Data Planejada"), (lanc, "Data")):
        d = pd.to_datetime(df[col], errors="coerce", dayfirst=True).dropna() if col in df else pd.Series(dtype="datetime64[ns]")
        if len(d):
            par = (d.dt.year.astype(str) + "-" + d.dt.quarter.astype(str)).mode().iloc[0]
            ano, tri = par.split("-")
            return int(ano), int(tri)
    return None

# endregion
