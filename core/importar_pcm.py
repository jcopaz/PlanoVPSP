# -*- coding: utf-8 -*-
"""Importa os exports do PCM para o modelo v3.

Dois arquivos do PCM (aba única "Export", rodapé "Filtros aplicados: ... Tri/Ano é Tri 4/26"):

1. **Pesos** (ex.: ``data (9).xlsx``) - consolidado por meta:
       LI_Gerencia | Coordenação | Departamento | GRUPO | Descrição Meta |
       Peso Item Inicial | Peso Item Redist | Plano Trimestral | Plano D-1 | ...
   (4 primeiras colunas mescladas: vazio = repetir a de cima)
   -> aba Pesos, com Peso = "Peso Item Redist" (já normalizado pelo PCM entre as
      metas com plano; o carregador normaliza de novo, sem efeito).

2. **Planejamento** (ex.: ``Planejamento PCM.xlsx``) - visão CONGELADA do plano
   distribuído por dia (o "norte" do trimestre):
       Data | Semana do Ano | Centro de Trabalho | Grupo | Descrição Meta |
       Nº do material / Nº do serviço | Equipamento | Equipe | Qtd. Plano |
       KM Inicio | KM Fim | Local de Instalação/Equipamento
   -> aba Plano_PCM (curva Meta PCM). Sem ele, o Plano Trimestral de cada meta é
      dividido igualmente pelas semanas (curva linear).

Só entram os Deptos cadastrados no parametros.xlsx (aba Coordenacoes).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from . import config
from .dados import semana_excel

COLS_HIERARQUIA = ["LI_Gerencia", "Coordenação", "Departamento", "GRUPO"]
RE_TRI = re.compile(r"Tri(?:mestre)?\s*([1-4])\s*/\s*(\d{4}|\d{2})\b", re.IGNORECASE)

# Planejamento PCM -> Plano_PCM
DE_PARA_PLANEJAMENTO = {
    "Data": "Data Planejada",
    "Centro de Trabalho": "Depto",
    "Descrição Meta": "Descrição Meta",
    "Nº do material / Nº do serviço": "Nº Material",
    "Equipe": "Equipe",
    "Local de Instalação/Equipamento": "Ativo",
    "Equipamento": "Equipamento",
    "Qtd. Plano": "Quantidade Programada",
}


@dataclass
class PlanoImportado:
    ano: int
    trimestre: int
    pesos: list[dict] = field(default_factory=list)
    plano: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
def trimestre_do_export(bruto: pd.DataFrame) -> tuple[int, int] | None:
    """(ano, trimestre) a partir do rodapé "Tri/Ano é Tri 4/26" ou, na falta dele,
    da célula 'Tri/Ano' do topo (o PCM grava o 4º tri/2026 como 01/04/2026:
    o MÊS é o número do trimestre)."""
    for v in bruto.to_numpy().ravel():
        if isinstance(v, str):
            m = RE_TRI.search(v)
            if m:
                ano = int(m.group(2))
                return (ano + 2000 if ano < 100 else ano), int(m.group(1))
    for i in range(min(len(bruto), 3)):
        linha = bruto.iloc[i].tolist()
        if any("tri" in str(v).lower() for v in linha):
            for v in linha:
                if isinstance(v, pd.Timestamp) or hasattr(v, "month"):
                    d = pd.Timestamp(v)
                    if d.day == 1 and 1 <= d.month <= 4:
                        return int(d.year), int(d.month)
    return None


def _acha_cabecalho(bruto: pd.DataFrame, limite: int = 15) -> int:
    for i in range(min(len(bruto), limite)):
        vals = [str(v).strip().lower() for v in bruto.iloc[i].tolist()]
        if "descrição meta" in vals or "descricao meta" in vals:
            return i
    raise ValueError(f"Cabeçalho com 'Descrição Meta' não encontrado nas {limite} primeiras linhas.")


def _semanas_do_trimestre(p: config.Parametros, tri: int) -> tuple[int, int]:
    linha = p.trimestres.loc[p.trimestres["Trimestre"] == tri]
    if not linha.empty:
        return int(linha.iloc[0]["SemanaInicio"]), int(linha.iloc[0]["SemanaFim"])
    return 1 + (tri - 1) * 13, tri * 13


def _datas_por_semana(ano: int, trimestre: int, sem_ini: int, sem_fim: int) -> dict[int, pd.Timestamp]:
    """1ª data de cada semana (WEEKNUM) dentro do trimestre."""
    ini = pd.Timestamp(ano, 3 * (trimestre - 1) + 1, 1)
    dias = pd.Series(pd.date_range(ini, ini + pd.offsets.QuarterEnd(0)))
    semanas = semana_excel(dias)
    return {w: dias[semanas == w].iloc[0] for w in range(sem_ini, sem_fim + 1) if (semanas == w).any()}


def _limpa(v):
    return None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v)


# --------------------------------------------------------------------------- #
def ler_planejamento(arquivo, deptos: set[str]) -> tuple[pd.DataFrame, tuple[int, int] | None]:
    """Planejamento PCM (plano por dia) já no layout do Plano_PCM."""
    bruto = pd.read_excel(arquivo, header=None)
    h = _acha_cabecalho(bruto)
    pl = pd.read_excel(arquivo, header=h)
    pl.columns = pd.Index(pl.columns).astype(str).str.strip()
    faltam = [c for c in ("Data", "Centro de Trabalho", "Descrição Meta", "Qtd. Plano") if c not in pl.columns]
    if faltam:
        raise ValueError(f"Colunas ausentes no Planejamento PCM: {faltam}")
    pl["Data"] = pd.to_datetime(pl["Data"], errors="coerce")
    pl = pl[pl["Data"].notna() & pl["Descrição Meta"].notna()].copy()     # tira o rodapé de filtros
    pl["Centro de Trabalho"] = pl["Centro de Trabalho"].astype(str).str.strip().str.upper()
    pl["Descrição Meta"] = pl["Descrição Meta"].astype(str).str.strip().str.upper()
    pl["Qtd. Plano"] = pd.to_numeric(pl["Qtd. Plano"], errors="coerce").fillna(0.0)
    pl = pl[pl["Centro de Trabalho"].isin(deptos) & (pl["Qtd. Plano"] > 0) & (pl["Descrição Meta"] != "")]

    out = pl[[c for c in DE_PARA_PLANEJAMENTO if c in pl.columns]].rename(columns=DE_PARA_PLANEJAMENTO)
    if {"KM Inicio", "KM Fim"}.issubset(pl.columns):
        km_i = pd.to_numeric(pl["KM Inicio"], errors="coerce").fillna(0)
        km_f = pd.to_numeric(pl["KM Fim"], errors="coerce").fillna(0)
        out["Observação"] = [f"KM {a:g}-{b:g}" if (a or b) else None for a, b in zip(km_i, km_f)]
    return out.sort_values(["Data Planejada", "Depto", "Descrição Meta"]), trimestre_do_export(bruto)


def importar(arquivo_export, p: config.Parametros, catalogo: pd.DataFrame | None = None,
             arquivo_planejamento=None) -> PlanoImportado:
    """Monta Pesos (+ Plano_PCM) a partir dos exports do PCM. ``catalogo``
    (opcional): aba Pesos de um trimestre anterior, para Unidade/SLA."""
    bruto = pd.read_excel(arquivo_export, header=None)
    h = _acha_cabecalho(bruto)
    tri_ano = trimestre_do_export(bruto)
    if tri_ano is None:
        raise ValueError("Trimestre não identificado no export (rodapé 'Tri/Ano é Tri 4/26' ou célula Tri/Ano).")
    ano, tri = tri_ano
    r = PlanoImportado(ano=ano, trimestre=tri)

    df = pd.read_excel(arquivo_export, header=h)
    df.columns = pd.Index(df.columns).astype(str).str.strip()
    faltam = [c for c in ["Departamento", "Descrição Meta", "Peso Item Redist", "Plano Trimestral"]
              if c not in df.columns]
    if faltam:
        raise ValueError(f"Colunas ausentes no export do PCM: {faltam}")
    hier = [c for c in COLS_HIERARQUIA if c in df.columns]
    df[hier] = df[hier].ffill()
    df = df[df["Descrição Meta"].notna()].copy()
    df["Departamento"] = df["Departamento"].astype(str).str.strip().str.upper()
    df["Descrição Meta"] = df["Descrição Meta"].astype(str).str.strip().str.upper()
    df = df[df["Descrição Meta"] != ""]
    df["Peso Item Redist"] = pd.to_numeric(df["Peso Item Redist"], errors="coerce").fillna(0.0)
    df["Plano Trimestral"] = pd.to_numeric(df["Plano Trimestral"], errors="coerce").fillna(0.0)

    deptos = set(p.coord_por_depto())
    fora = sorted(set(df["Departamento"]) - deptos)
    if fora:
        r.avisos.append(f"{len(fora)} Depto(s) do export fora das Coordenações cadastradas foram ignorados "
                        f"({', '.join(fora[:6])}{' ...' if len(fora) > 6 else ''}).")
    df = df[df["Departamento"].isin(deptos)]
    n_sem = int(((df["Plano Trimestral"] <= 0) | (df["Peso Item Redist"] <= 0)).sum())
    df = df[(df["Plano Trimestral"] > 0) & (df["Peso Item Redist"] > 0)]
    if n_sem:
        r.avisos.append(f"{n_sem} meta(s) sem plano ou sem peso no trimestre não entraram.")
    if df.empty:
        r.avisos.append("Nenhuma meta com plano para os Deptos cadastrados (Coordenações).")
        return r

    # ---- Pesos ----------------------------------------------------------- #
    cat = {}
    if catalogo is not None and not catalogo.empty:
        faltam = [c for c in ("Descrição Meta", "Unidade", "SLA") if c not in catalogo.columns]
        if faltam:
            raise ValueError(f"Catálogo sem as colunas {faltam} (use a aba Pesos de uma planilha v3).")
        c = catalogo.dropna(subset=["Descrição Meta"]).copy()
        c["Descrição Meta"] = c["Descrição Meta"].astype(str).str.strip().str.upper()
        cat = c.drop_duplicates("Descrição Meta").set_index("Descrição Meta")[["Unidade", "SLA"]].to_dict("index")
    sem_unid = sorted(set(df["Descrição Meta"]) - set(cat))
    if sem_unid:
        r.avisos.append(f"{len(sem_unid)} meta(s) sem Unidade/SLA"
                        f"{' no catálogo' if cat else ' (sem catálogo)'}: preencha em Configurações → SLA e Unidades.")
    for _, x in df.iterrows():
        info = cat.get(x["Descrição Meta"], {})
        r.pesos.append({"Depto": x["Departamento"], "Grupo": x.get("GRUPO"),
                        "Descrição Meta": x["Descrição Meta"], "Peso": float(x["Peso Item Redist"]),
                        "Unidade": _limpa(info.get("Unidade")), "SLA": _limpa(info.get("SLA"))})

    sem_ini, sem_fim = _semanas_do_trimestre(p, tri)

    # ---- Plano_PCM: Planejamento congelado (por dia) --------------------- #
    if arquivo_planejamento is not None:
        pl, tri_pl = ler_planejamento(arquivo_planejamento, deptos)
        if tri_pl and tri_pl != (ano, tri):
            r.avisos.append(f"Planejamento é do {tri_pl[1]}º tri/{tri_pl[0]}, mas os pesos são do "
                            f"{tri}º tri/{ano}. Confira os arquivos.")
        ini_tri = pd.Timestamp(ano, 3 * (tri - 1) + 1, 1)
        no_tri = pl["Data Planejada"].between(ini_tri, ini_tri + pd.offsets.QuarterEnd(0))
        if (~no_tri).any():
            r.avisos.append(f"{int((~no_tri).sum())} linha(s) do Planejamento fora do {tri}º tri/{ano} "
                            f"foram descartadas.")
        pl = pl[no_tri]
        soma = pl.groupby(["Depto", "Descrição Meta"])["Quantidade Programada"].sum().rename("planejamento")
        ref = (df.rename(columns={"Departamento": "Depto"})
               .groupby(["Depto", "Descrição Meta"])["Plano Trimestral"].sum().rename("pesos"))
        dif = pd.concat([ref, soma], axis=1).fillna(0.0)
        dif = dif[(dif["pesos"] - dif["planejamento"]).abs() > 1e-6]
        if len(dif):
            itens = [f"{d}|{m} ({a:g} x {b:g})" for (d, m), (a, b) in dif.iterrows()]
            r.avisos.append(f"{len(dif)} meta(s) com Plano Trimestral diferente da soma do Planejamento "
                            f"(pesos x planejamento): " + "; ".join(itens[:5]) + (" ..." if len(itens) > 5 else ""))
        sem = semana_excel(pl["Data Planejada"])
        fora_janela = sorted(set(sem[(sem < sem_ini) | (sem > sem_fim)]))
        if fora_janela:
            r.avisos.append(f"Planejamento tem datas nas semanas {fora_janela}, fora da janela "
                            f"{sem_ini}-{sem_fim} do trimestre: ajuste em Configurações → Trimestres.")
        r.plano = [{k: _limpa(v) for k, v in ln.items()} for ln in pl.to_dict("records")]
        return r

    # ---- Sem Planejamento: plano trimestral ÷ semanas (curva linear) ----- #
    datas = _datas_por_semana(ano, tri, sem_ini, sem_fim)
    if not datas:
        r.avisos.append(f"Semanas {sem_ini}-{sem_fim} não caem no {tri}º tri/{ano}; confira a aba Trimestres.")
        return r
    fora_tri = sorted(set(range(sem_ini, sem_fim + 1)) - set(datas))
    if fora_tri:
        r.avisos.append(f"Semana(s) {fora_tri} da aba Trimestres não caem no {tri}º tri/{ano}: "
                        f"plano dividido por {len(datas)} semanas.")
    r.avisos.append("Sem o Planejamento PCM: curva planejada linear (plano trimestral ÷ semanas).")
    for _, x in df.iterrows():
        q = float(x["Plano Trimestral"]) / len(datas)
        for d in datas.values():
            r.plano.append({"Depto": x["Departamento"], "Data Planejada": d.to_pydatetime(),
                            "Descrição Meta": x["Descrição Meta"], "Quantidade Programada": q,
                            "Observação": "Plano trimestral ÷ semanas (sem Planejamento PCM)"})
    r.plano.sort(key=lambda ln: (ln["Data Planejada"], ln["Depto"], ln["Descrição Meta"]))
    return r
