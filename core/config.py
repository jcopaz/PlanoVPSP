# -*- coding: utf-8 -*-
"""Leitura centralizada de ``parametros.xlsx``.

A ideia é que TODA informação que muda de um trimestre para o outro (qual
arquivo abrir, número do trimestre, faixas de risco, de-para de coordenação,
composição do envelope OPEX...) fique nesse Excel - nunca no código.

Se o arquivo não existir, ou uma aba/chave faltar, usa-se o default embutido
aqui. Assim o app sobe mesmo numa primeira execução / deploy limpo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

# --------------------------------------------------------------------------- #
# Caminhos
# --------------------------------------------------------------------------- #
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ_PARAMETROS = os.path.join(RAIZ, "parametros.xlsx")


def caminho(nome_arquivo: str) -> str:
    """Resolve um nome de arquivo relativo à raiz do projeto (portável p/ web)."""
    if os.path.isabs(nome_arquivo):
        return nome_arquivo
    return os.path.join(RAIZ, nome_arquivo)


# --------------------------------------------------------------------------- #
# Defaults (trimestre 2/2026) - usados quando parametros.xlsx está ausente
# --------------------------------------------------------------------------- #
_DEFAULT_CONFIG = {
    "ano": 2026,
    "trimestre": 2,
    "semana_inicio": "",          # vazio => deriva da tabela Trimestres
    "semana_fim": "",
    "arquivo_plano": "Plano de Manutenção 2º Trimestre - SP.xlsx",
    "arquivo_orcamento": "Orçamento Ger. SP.xlsx",
    "aba_diario": "Diário",
    "aba_peso": "Planilha de Peso",
    "aba_plan_orc": "PLAN ORÇ",
    "aba_realizado_analitico": "Realizado Analitico",
    "meta_aderencia": 1.0,
    "faixa_leve": 0.05,
    "faixa_risco": 0.10,
    "faixa_critico": 0.15,
    "rotulo_gerencia": "Gerência",
    "origem_pcm": "PCM",
    "origem_execucao": "Coordenação",
    "plano_sim": "Sim",
    "plano_nao": "Não",
    # Grupos que não entram na aderência da Via (o PCM os mede em outros centros)
    "grupos_fora_aderencia": "Saneamento Vegetal;Drenagem",
}

_DEFAULT_TRIMESTRES = pd.DataFrame(
    [
        [1, 1, 13, "JAN;FEV;MAR"],
        [2, 14, 26, "ABR;MAI;JUN"],
        [3, 27, 39, "JUL;AGO;SET"],
        [4, 40, 53, "OUT;NOV;DEZ"],
    ],
    columns=["Trimestre", "SemanaInicio", "SemanaFim", "Meses"],
)

_DEFAULT_COORDENACOES = pd.DataFrame(
    [
        ["V.SP.IPA", "Paranapiacaba", "CCR097", "Sim"],
        ["V.SP.IPG", "Piaçaguera", "CCR098", "Sim"],
        ["V.SP.PJU", "Jundiaí", "CCR063", "Sim"],
        ["", "Gerência", "CGE041", "Sim"],
    ],
    columns=["Depto", "Coordenacao", "CentroCusto", "EntraNaGerencia"],
)

_DEFAULT_ENVELOPE = {
    "pacotes_incluir": "PM03;PM05;MATERIAIS INDIRET DE MANUTENÇÃO/OPERAÇÃO",
    "centros_custo": "CCR097;CCR098;CCR063;CGE041",
    "dre_realizado_sap": "DRE011132-MANUTENÇÃO",
    "usar_realizado_sap_de": "PLAN ORÇ",   # ou "Realizado Analitico"
}


# --------------------------------------------------------------------------- #
# Estrutura devolvida
# --------------------------------------------------------------------------- #
@dataclass
class Parametros:
    cfg: dict = field(default_factory=dict)
    trimestres: pd.DataFrame = field(default_factory=lambda: _DEFAULT_TRIMESTRES.copy())
    coordenacoes: pd.DataFrame = field(default_factory=lambda: _DEFAULT_COORDENACOES.copy())
    envelope: dict = field(default_factory=dict)
    origem: str = "defaults"          # "parametros.xlsx" ou "defaults"

    # ---- atalhos ---------------------------------------------------------- #
    def g(self, chave, tipo=str, default=None):
        val = self.cfg.get(chave, _DEFAULT_CONFIG.get(chave, default))
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return default
        try:
            if tipo is bool:
                return str(val).strip().lower() in ("sim", "true", "1", "x", "verdadeiro")
            return tipo(val)
        except (TypeError, ValueError):
            return default

    @property
    def ano(self) -> int:
        return self.g("ano", int, 2026)

    @property
    def trimestre(self) -> int:
        return self.g("trimestre", int, 2)

    @property
    def semanas(self) -> tuple[int, int]:
        """(semana_inicio, semana_fim) - override do Config ou tabela Trimestres."""
        ini = self.g("semana_inicio", int, None)
        fim = self.g("semana_fim", int, None)
        if ini and fim:
            return ini, fim
        linha = self.trimestres.loc[self.trimestres["Trimestre"] == self.trimestre]
        if not linha.empty:
            return int(linha.iloc[0]["SemanaInicio"]), int(linha.iloc[0]["SemanaFim"])
        return (1 + (self.trimestre - 1) * 13, self.trimestre * 13)

    @property
    def meses_trimestre(self) -> list[str]:
        linha = self.trimestres.loc[self.trimestres["Trimestre"] == self.trimestre]
        if not linha.empty and isinstance(linha.iloc[0]["Meses"], str):
            return [m.strip().upper() for m in linha.iloc[0]["Meses"].split(";") if m.strip()]
        return ["ABR", "MAI", "JUN"]

    @property
    def dic_trimestres(self) -> dict:
        out = {}
        for _, r in self.trimestres.sort_values("Trimestre").iterrows():
            rot = f"{int(r['Trimestre'])}º Trimestre (Sem {int(r['SemanaInicio'])} a {int(r['SemanaFim'])})"
            out[rot] = (int(r["SemanaInicio"]), int(r["SemanaFim"]))
        return out

    @property
    def n_coord_gerencia(self) -> int:
        """Quantas coordenações reais (com Depto) compõem a visão Gerência."""
        c = self.coordenacoes
        reais = c[(c["Depto"].astype(str).str.strip() != "")
                  & (c["EntraNaGerencia"].astype(str).str.strip().str.lower().isin(["sim", "x", "1", "true"]))]
        return max(1, len(reais))

    def coord_por_depto(self) -> dict:
        c = self.coordenacoes
        return {str(r["Depto"]).strip(): str(r["Coordenacao"]).strip()
                for _, r in c.iterrows() if str(r["Depto"]).strip()}

    def cc_por_coord(self) -> dict:
        c = self.coordenacoes
        return {str(r["Coordenacao"]).strip(): str(r["CentroCusto"]).strip()
                for _, r in c.iterrows() if str(r["CentroCusto"]).strip()}

    def env(self, chave, default=""):
        return self.envelope.get(chave, _DEFAULT_ENVELOPE.get(chave, default))

    def env_lista(self, chave) -> list[str]:
        return [x.strip() for x in str(self.env(chave)).split(";") if x.strip()]


# --------------------------------------------------------------------------- #
# Carregamento
# --------------------------------------------------------------------------- #
def _kv(df: pd.DataFrame) -> dict:
    """Converte uma aba de 2 colunas (Parametro/Valor) em dict."""
    if df.shape[1] < 2:
        return {}
    df = df.iloc[:, :2].copy()
    df.columns = ["k", "v"]
    df = df.dropna(subset=["k"])
    return {str(k).strip(): (v if pd.notna(v) else "") for k, v in zip(df["k"], df["v"])}


def carregar(caminho_parametros: str | None = None) -> Parametros:
    caminho_parametros = caminho_parametros or ARQ_PARAMETROS
    p = Parametros(cfg=dict(_DEFAULT_CONFIG), envelope=dict(_DEFAULT_ENVELOPE))

    if not os.path.exists(caminho_parametros):
        return p

    try:
        xls = pd.ExcelFile(caminho_parametros)
    except Exception:
        return p

    nomes = {n.lower().strip(): n for n in xls.sheet_names}

    if "config" in nomes:
        p.cfg.update({k: v for k, v in _kv(pd.read_excel(xls, nomes["config"])).items()})
    if "envelope_opex" in nomes:
        p.envelope.update(_kv(pd.read_excel(xls, nomes["envelope_opex"])))
    if "trimestres" in nomes:
        t = pd.read_excel(xls, nomes["trimestres"])
        if {"Trimestre", "SemanaInicio", "SemanaFim"}.issubset(t.columns):
            p.trimestres = t
    if "coordenacoes" in nomes:
        c = pd.read_excel(xls, nomes["coordenacoes"])
        if {"Depto", "Coordenacao"}.issubset(c.columns):
            for col in ("Depto", "CentroCusto", "EntraNaGerencia"):
                if col not in c.columns:
                    c[col] = ""
            p.coordenacoes = c.fillna("")

    p.origem = "parametros.xlsx"
    return p
