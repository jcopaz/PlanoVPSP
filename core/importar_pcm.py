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

3. **Realizado** (ex.: ``Realizado 1 ao 4º Tri.xlsx``) - ordens do SAP lançadas
   pelos programadores (Data Programada, Qtd. Programada, Qtd. Real, Considera
   Plano?, Motivo de Perda...) -> aba Lancamentos, separado por trimestre da
   Data Programada. Dispensa a planilha dos programadores.

Histórico (vários trimestres de uma vez): montar_historico() junta Planejado
(1 a N trimestres) + Realizado + o export de pesos. O **Peso Item Inicial**
(coluna F) é fixo por meta — o PCM só o redistribui entre as metas com plano
(conferido: reproduz os pesos das planilhas do 1º e do 3º tri/2026, 76/76) —
então um único export de pesos serve para todos os trimestres.

Só entram os Deptos cadastrados nas Coordenações.
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


# --------------------------------------------------------------------------- #
# Histórico: Planejado (N trimestres) + Realizado + catálogo de pesos
# --------------------------------------------------------------------------- #
DE_PARA_REALIZADO = {
    "Data Programada": "Data",
    "Descrição Meta": "Descrição Meta",
    "Nº do material / Nº do serviço": "Nº Material",
    "Equipe/Equipamento": "Equipe",
    "Local instalação": "Ativo",
    "Qtd. Programada": "Quantidade Programada",
    "Qtd. Real": "Quantidade Realizada",
    "Considera Plano?": "No Plano",
}


def _txt(v) -> str:
    return "" if pd.isna(v) else str(v).removesuffix(".0")


def catalogo_peso_inicial(arquivo_pesos, deptos: set[str]) -> pd.DataFrame:
    """Depto, Grupo, Descrição Meta, Peso (= Peso Item Inicial) de TODAS as metas
    do export de pesos — inclusive as sem plano no trimestre do export."""
    bruto = pd.read_excel(arquivo_pesos, header=None)
    df = pd.read_excel(arquivo_pesos, header=_acha_cabecalho(bruto))
    df.columns = pd.Index(df.columns).astype(str).str.strip()
    if "Peso Item Inicial" not in df.columns:
        raise ValueError("Export de pesos sem a coluna 'Peso Item Inicial'.")
    hier = [c for c in COLS_HIERARQUIA if c in df.columns]
    df[hier] = df[hier].ffill()
    df = df[df["Descrição Meta"].notna()].copy()
    df["Depto"] = df["Departamento"].astype(str).str.strip().str.upper()
    df["Descrição Meta"] = df["Descrição Meta"].astype(str).str.strip().str.upper()
    df["Peso"] = pd.to_numeric(df["Peso Item Inicial"], errors="coerce").fillna(0.0)
    df = df[df["Depto"].isin(deptos) & (df["Descrição Meta"] != "")]
    df = df.rename(columns={"GRUPO": "Grupo"})
    return df.reindex(columns=["Depto", "Grupo", "Descrição Meta", "Peso"]).drop_duplicates(["Depto", "Descrição Meta"])


# Equipes de fora da coordenação cuja execução conta para a Via (socaria mecanizada).
RESPONSAVEIS_EXTRA_VIA = {"GOEV"}


def ler_realizado(arquivo, deptos: set[str], com_sem_meta: bool = False) -> tuple[pd.DataFrame, int]:
    """Realizado do PCM no layout da aba Lancamentos + colunas _ano/_tri.

    Regra do PCM ("Adr_Ativo", conferida contra o Power BI nos 4 trimestres de 2026):
      - a execução é da coordenação ONDE FICA O ATIVO ("Centro de trabalho Ativo",
        ex. IPA -> V.SP.IPA), inclusive a feita pela GOEV (socaria mecanizada);
      - conta para o plano (No Plano = Sim) a ordem com "Considera Plano? = Sim" OU
        com a ordem Encerrada (o "CONC" das colunas do PCM).
    Devolve (lancamentos, n_linhas_sem_meta_ignoradas)."""
    bruto = pd.read_excel(arquivo, header=None, nrows=15)
    r = pd.read_excel(arquivo, header=_acha_cabecalho(bruto))
    r.columns = pd.Index(r.columns).astype(str).str.strip()
    faltam = [c for c in ("Centro de trabalho Ativo", "Centro de trabalho responsável", "Data Programada",
                          "Descrição Meta", "Qtd. Real", "Considera Plano?") if c not in r.columns]
    if faltam:
        raise ValueError(f"Colunas ausentes no Realizado do PCM: {faltam}")
    r["Data Programada"] = pd.to_datetime(r["Data Programada"], errors="coerce")
    r = r[r["Data Programada"].notna()].copy()                       # tira o rodapé de filtros
    resp = r["Centro de trabalho responsável"].astype(str).str.strip().str.upper()
    prefixos = {d.rsplit(".", 1)[0] + "." for d in deptos}            # ex.: "V.SP."
    # (Gerência, código do ativo) -> Depto: ("SP", "IPA") -> "V.SP.IPA" (evita trocar SP x VP)
    por_ger_codigo = {(d.split(".")[1], d.rsplit(".", 1)[-1]): d for d in deptos if d.count(".") >= 2}
    ger = (r["Gerência"] if "Gerência" in r.columns else pd.Series("SP", index=r.index)).astype(str).str.strip().str.upper()
    cod = r["Centro de trabalho Ativo"].astype(str).str.strip().str.upper()
    r["_depto"] = [por_ger_codigo.get((g, c)) for g, c in zip(ger, cod)]
    da_via = resp.str.startswith(tuple(prefixos)) | resp.isin(RESPONSAVEIS_EXTRA_VIA)
    r = r[r["_depto"].notna() & da_via]
    meta = r["Descrição Meta"].fillna("").astype(str).str.strip()
    n_sem_meta = int((meta == "").sum())
    if not com_sem_meta:
        r = r[meta != ""]

    out = r.reindex(columns=list(DE_PARA_REALIZADO)).rename(columns=DE_PARA_REALIZADO)
    out.insert(0, "Depto", r["_depto"].values)
    encerrada = r.get("Status atual da ordem", pd.Series("", index=r.index)).astype(str).str.strip().str.lower().eq("encerrada")
    considera = r["Considera Plano?"].astype(str).str.strip().str.lower().eq("sim")
    out["No Plano"] = ["Sim" if (c or e) else "Não" for c, e in zip(considera, encerrada)]
    out["Descrição Meta"] = out["Descrição Meta"].fillna("").astype(str).str.strip().str.upper()
    prog = pd.to_numeric(out["Quantidade Programada"], errors="coerce")
    real = pd.to_numeric(out["Quantidade Realizada"], errors="coerce")
    motivo = r["Motivo de Perda"] if "Motivo de Perda" in r.columns else pd.Series(None, index=r.index)
    out["Justificativa"] = motivo.where(~(real >= prog))           # mantém se real < prog ou se faltou quantidade
    out["Quantidade Programada"], out["Quantidade Realizada"] = prog.fillna(0.0), real.fillna(0.0)
    km_i = pd.to_numeric(r.get("Km início"), errors="coerce").fillna(0)
    km_f = pd.to_numeric(r.get("Km Fim"), errors="coerce").fillna(0)
    out["Observação"] = [
        f"Ordem {_txt(o)}/{_txt(op)} · {_txt(st)} · {_txt(rp)}" + (f" · KM {a:g}-{b:g}" if (a or b) else "")
        for o, op, st, rp, a, b in zip(r.get("Nº ordem"), r.get("Nº operação"), r.get("Status atual da ordem"),
                                       r["Centro de trabalho responsável"], km_i, km_f)]
    out["Programador"] = "PCM (SAP)"
    out["_ano"] = r["Data Programada"].dt.year.values
    out["_tri"] = r["Data Programada"].dt.quarter.values
    return out.reset_index(drop=True), n_sem_meta


def montar_historico(deptos: set[str], arquivo_planejado=None, arquivo_realizado=None, arquivo_pesos=None,
                     com_sem_meta: bool = False, trimestres_com_plano: set[tuple[int, int]] = frozenset()
                     ) -> tuple[dict[tuple[int, int], dict], list[str]]:
    """{(ano, tri): {"pesos", "plano", "lanc"}} a partir dos exports do PCM.
    pesos/plano só existem para os trimestres presentes no Planejado. Realizado de
    trimestre sem plano (nem no Planejado nem em ``trimestres_com_plano``, os que já
    estão no banco) é ignorado — ex.: ordens de 2023–2025 confirmadas em 2026."""
    avisos: list[str] = []
    saida: dict[tuple[int, int], dict] = {}
    if arquivo_planejado is not None:
        if arquivo_pesos is None:
            raise ValueError("Para gravar o Planejado envie também o export de pesos (ex.: data (9).xlsx): "
                             "ele traz o Peso Item Inicial usado em todos os trimestres.")
        cat = catalogo_peso_inicial(arquivo_pesos, deptos)
        pl, _ = ler_planejamento(arquivo_planejado, deptos)
        datas = pd.to_datetime(pl["Data Planejada"])
        for (ano, tri), g in pl.groupby([datas.dt.year, datas.dt.quarter]):
            usadas = g.groupby(["Depto", "Descrição Meta"])["Quantidade Programada"].sum()
            usadas = usadas[usadas > 0].reset_index()[["Depto", "Descrição Meta"]]
            pesos = usadas.merge(cat, on=["Depto", "Descrição Meta"], how="left")
            sem = pesos[pesos["Peso"].isna()]
            if len(sem):
                avisos.append(f"{tri}º tri/{ano}: {len(sem)} meta(s) do plano sem Peso Item Inicial no export de "
                              f"pesos (não pesam na curva): " + "; ".join((sem["Depto"] + "|" + sem["Descrição Meta"]).head(5)))
            saida[(int(ano), int(tri))] = {"pesos": pesos.fillna({"Peso": 0.0}), "plano": g.reset_index(drop=True)}
    if arquivo_realizado is not None:
        lanc, n_sem_meta = ler_realizado(arquivo_realizado, deptos, com_sem_meta)
        if n_sem_meta and not com_sem_meta:
            avisos.append(f"{n_sem_meta} linha(s) do Realizado sem Descrição Meta (ordens fora do catálogo do plano) "
                          f"ficaram de fora — não pesam na curva.")
        validos = set(saida) | set(trimestres_com_plano)
        fora = 0
        for (ano, tri), g in lanc.groupby(["_ano", "_tri"]):
            if (int(ano), int(tri)) not in validos:
                fora += len(g)
                continue
            saida.setdefault((int(ano), int(tri)), {})["lanc"] = g.drop(columns=["_ano", "_tri"]).reset_index(drop=True)
        if fora:
            avisos.append(f"{fora} linha(s) do Realizado em trimestres sem plano carregado (ordens antigas) ficaram de fora.")
    return dict(sorted(saida.items())), avisos
