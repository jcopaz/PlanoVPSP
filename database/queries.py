# database/queries.py — Todas as leituras/gravações do banco
#
# Regra da casa: as telas (modules/) NUNCA montam SQL; chamam funções daqui.
# Leituras devolvem DataFrames já com os cabeçalhos do modelo de planilha
# (core/modelo.py) — o mesmo formato do Excel — para o motor de cálculo
# (core/dados.py::montar_canonico) e a exportação usarem sem conversão.
#
# Toda gravação: (1) roda numa transação, (2) registra em `auditoria`,
# (3) incrementa config._versao_dados — as leituras em cache (st.cache_data
# nas telas) usam esse número como chave, então todo mundo vê o dado novo
# no próximo rerun, mesmo com vários usuários.

from __future__ import annotations

import json
import math
from datetime import date, datetime

import pandas as pd
from sqlalchemy import Date, DateTime, String, and_, case, delete, func, insert, or_, select, update

from database import schema as S
from database.client import get_engine


# region ====================== SESSÃO 1: Utilitários ======================

def _limpa(v):
    """NaN/NaT/'' -> None; Timestamp -> date; numpy -> python."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if v is pd.NaT or (not isinstance(v, (str, bytes, list, dict)) and pd.isna(v)):
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if hasattr(v, "item") and not isinstance(v, (pd.Timestamp, datetime, date)):
        return v.item()
    return v


def _data(v):
    v = _limpa(v)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    from core.dados import para_data
    d = para_data([v]).iloc[0]
    return None if pd.isna(d) else d.date()


def _num(v, padrao=None):
    v = _limpa(v)
    if v is None:
        return padrao
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def _texto(v, maiusculo=False):
    v = _limpa(v)
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)                     # Nº Material 100025431.0 -> "100025431"
    s = " ".join(str(v).split())
    return s.upper() if maiusculo else s


def _cabe(tab, linhas: list[dict]) -> list[dict]:
    """Corta textos maiores que a coluna (o PostgreSQL recusa; o SQLite aceitava calado)."""
    tam = {c.name: c.type.length for c in tab.c if isinstance(c.type, String) and c.type.length}
    for ln in linhas:
        for k, n in tam.items():
            v = ln.get(k)
            if isinstance(v, str) and len(v) > n:
                ln[k] = v[:n]
    return linhas


def _auditar(conn, usuario, acao, tabela=None, registro_id=None, detalhe=None):
    conn.execute(insert(S.auditoria).values(
        usuario=usuario, acao=acao, tabela=tabela, registro_id=registro_id,
        detalhe=json.dumps(detalhe, ensure_ascii=False, default=str) if isinstance(detalhe, (dict, list)) else detalhe,
        quando=datetime.now()))


def _bump(conn):
    atual = conn.execute(select(S.config.c.valor).where(S.config.c.chave == "_versao_dados")).scalar()
    novo = str(int(atual or 0) + 1)
    if atual is None:
        conn.execute(insert(S.config).values(chave="_versao_dados", valor=novo))
    else:
        conn.execute(update(S.config).where(S.config.c.chave == "_versao_dados").values(valor=novo))


def versao_dados() -> int:
    with get_engine().connect() as c:
        return int(c.execute(select(S.config.c.valor).where(S.config.c.chave == "_versao_dados")).scalar() or 0)


def _df(conn, stmt) -> pd.DataFrame:
    res = conn.execute(stmt)
    return pd.DataFrame(res.fetchall(), columns=list(res.keys()))

# endregion


# region ====================== SESSÃO 2: Padrões da 1ª execução ======================

CHAVES_CONFIG = ["meta_aderencia", "faixa_leve", "faixa_risco", "faixa_critico", "rotulo_gerencia",
                 "grupos_fora_aderencia", "metas_medicao_depto",
                 "origem_pcm", "origem_execucao", "plano_sim", "plano_nao",
                 "arquivo_orcamento", "aba_plan_orc", "aba_realizado_analitico"]


def semear_padroes(engine) -> None:
    """Preenche config, coordenações e listas na 1ª execução (não sobrescreve nada)."""
    from core import config as cfg_mod
    from core import modelo

    p = cfg_mod.carregar()      # parametros.xlsx (se existir) ou defaults embutidos
    with engine.begin() as conn:
        if not conn.execute(select(func.count()).select_from(S.config)).scalar():
            linhas = [{"chave": k, "valor": str(p.g(k, str, ""))} for k in CHAVES_CONFIG]
            linhas += [{"chave": f"env.{k}", "valor": str(p.env(k))}
                       for k in ("pacotes_incluir", "centros_custo", "dre_realizado_sap", "usar_realizado_sap_de")]
            linhas.append({"chave": "_versao_dados", "valor": "0"})
            conn.execute(insert(S.config), linhas)
        if not conn.execute(select(func.count()).select_from(S.coordenacoes)).scalar():
            c = p.coordenacoes
            linhas = [{"depto": str(r["Depto"]).strip(), "coordenacao": str(r["Coordenacao"]).strip(),
                       "centro_custo": str(r["CentroCusto"]).strip(),
                       "entra_gerencia": str(r["EntraNaGerencia"]).strip().lower() in ("sim", "x", "1", "true")}
                      for _, r in c.iterrows() if str(r["Depto"]).strip()]
            if linhas:
                conn.execute(insert(S.coordenacoes), linhas)
        if not conn.execute(select(func.count()).select_from(S.listas)).scalar():
            linhas = [{"tipo": tipo, "valor": v, "depto": "", "ativo": True}
                      for tipo in ("Justificativa", "Status", "Tipo Material", "Grupo")
                      for v in modelo.LISTAS_PADRAO.get(tipo, [])]
            if linhas:
                conn.execute(insert(S.listas), linhas)

# endregion


# region ====================== SESSÃO 3: Configuração e coordenações ======================

def ler_config() -> dict:
    with get_engine().connect() as c:
        return {k: v for k, v in c.execute(select(S.config.c.chave, S.config.c.valor))}


def salvar_config(valores: dict, usuario: str) -> None:
    with get_engine().begin() as conn:
        for k, v in valores.items():
            conn.execute(delete(S.config).where(S.config.c.chave == k))
            conn.execute(insert(S.config).values(chave=k, valor="" if v is None else str(v)))
        _auditar(conn, usuario, "config", "config", detalhe=valores)
        _bump(conn)


def listar_coordenacoes() -> pd.DataFrame:
    with get_engine().connect() as c:
        return _df(c, select(S.coordenacoes).order_by(S.coordenacoes.c.depto))


def salvar_coordenacoes(df: pd.DataFrame, usuario: str) -> None:
    linhas = [{"depto": _texto(r["depto"], True), "coordenacao": _texto(r["coordenacao"]),
               "centro_custo": _texto(r.get("centro_custo")), "entra_gerencia": bool(r.get("entra_gerencia"))}
              for _, r in df.iterrows() if _texto(r.get("depto")) and _texto(r.get("coordenacao"))]
    with get_engine().begin() as conn:
        conn.execute(delete(S.coordenacoes))
        if linhas:
            conn.execute(insert(S.coordenacoes), linhas)
        _auditar(conn, usuario, "salvar", "coordenacoes", detalhe={"linhas": len(linhas)})
        _bump(conn)

# endregion


# region ====================== SESSÃO 4: Trimestres ======================

def janela_semanas(ano: int, tri: int) -> tuple[int, int]:
    """Semanas (WEEKNUM do Excel) do 1º e do último dia do trimestre.
    Ex.: 4º tri/2026 = 40 a 53 (28-31/12/2026 caem na semana 53)."""
    from core.dados import semana_excel
    ini = pd.Timestamp(ano, 3 * (tri - 1) + 1, 1)
    fim = ini + pd.offsets.QuarterEnd(0)
    s = semana_excel(pd.Series([ini, fim]))
    return int(s.iloc[0]), int(s.iloc[1])


def listar_trimestres() -> pd.DataFrame:
    with get_engine().connect() as c:
        df = _df(c, select(S.trimestres).order_by(S.trimestres.c.ano, S.trimestres.c.trimestre))
        cont = {}
        for tab, nome in ((S.plano, "linhas_plano"), (S.lancamentos, "lancamentos")):
            q = select(tab.c.trimestre_id, func.count()).group_by(tab.c.trimestre_id)
            cont[nome] = dict(c.execute(q).fetchall())
    for nome, mapa in cont.items():
        df[nome] = df["id"].map(mapa).fillna(0).astype(int) if not df.empty else []
    if not df.empty:
        df["rotulo"] = df["trimestre"].astype(str) + "º tri/" + df["ano"].astype(str)
    return df


def obter_trimestre(tid: int) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(select(S.trimestres).where(S.trimestres.c.id == tid)).mappings().first()
        return dict(r) if r else None


def garantir_trimestre(ano: int, tri: int, usuario: str) -> int:
    with get_engine().begin() as conn:
        tid = conn.execute(select(S.trimestres.c.id).where(
            and_(S.trimestres.c.ano == ano, S.trimestres.c.trimestre == tri))).scalar()
        if tid:
            return int(tid)
        ini, fim = janela_semanas(ano, tri)
        tid = conn.execute(insert(S.trimestres).values(
            ano=ano, trimestre=tri, semana_inicio=ini, semana_fim=fim, status="aberto")).inserted_primary_key[0]
        _auditar(conn, usuario, "criar", "trimestres", tid, {"ano": ano, "trimestre": tri})
        _bump(conn)
        return int(tid)


def atualizar_trimestre(tid: int, usuario: str, **campos) -> None:
    with get_engine().begin() as conn:
        conn.execute(update(S.trimestres).where(S.trimestres.c.id == tid)
                     .values(**campos, atualizado_em=datetime.now()))
        _auditar(conn, usuario, "atualizar", "trimestres", tid, campos)
        _bump(conn)


def excluir_trimestre(tid: int, usuario: str) -> None:
    with get_engine().begin() as conn:
        _copiar_lancamentos(conn, tid, "excluir trimestre", usuario)
        for tab in (S.lancamentos, S.plano, S.pesos):
            conn.execute(delete(tab).where(tab.c.trimestre_id == tid))
        conn.execute(delete(S.trimestres).where(S.trimestres.c.id == tid))
        _auditar(conn, usuario, "excluir", "trimestres", tid)
        _bump(conn)

# endregion


# region ====================== SESSÃO 5: Pesos, plano e lançamentos ======================

def carregar_dados(tid: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(pesos, plano, lancamentos) do trimestre com os cabeçalhos do modelo v3.
    Lançamentos trazem também a coluna 'id' (para edição linha a linha)."""
    with get_engine().connect() as c:
        pe = _df(c, select(S.pesos).where(S.pesos.c.trimestre_id == tid).order_by(S.pesos.c.depto, S.pesos.c.meta))
        pl = _df(c, select(S.plano).where(S.plano.c.trimestre_id == tid).order_by(S.plano.c.data, S.plano.c.depto))
        la = _df(c, select(S.lancamentos).where(S.lancamentos.c.trimestre_id == tid)
                 .order_by(S.lancamentos.c.data, S.lancamentos.c.depto, S.lancamentos.c.id))
    pe = pe.rename(columns=S.MAPA_PESOS).reindex(columns=list(S.MAPA_PESOS.values()))
    pl = pl.rename(columns=S.MAPA_PLANO).reindex(columns=list(S.MAPA_PLANO.values()))
    la = la.rename(columns=S.MAPA_LANC).reindex(columns=["id"] + list(S.MAPA_LANC.values()))
    for df, col in ((pl, "Data Planejada"), (la, "Data"), (la, "Prazo")):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return pe, pl, la


def _linhas_pesos(tid, df):
    out = {}
    for _, r in df.iterrows():
        depto, meta = _texto(r.get("Depto"), True), _texto(r.get("Descrição Meta"), True)
        if depto and meta:
            out[(depto, meta)] = {"trimestre_id": tid, "depto": depto, "meta": meta,
                                  "grupo": _texto(r.get("Grupo")), "peso": _num(r.get("Peso"), 0.0)}
    return list(out.values())


def _linhas_plano(tid, df):
    linhas = []
    for _, r in df.iterrows():
        d, depto, meta = _data(r.get("Data Planejada")), _texto(r.get("Depto"), True), _texto(r.get("Descrição Meta"), True)
        if d and depto:
            linhas.append({"trimestre_id": tid, "depto": depto, "data": d, "meta": meta or SEM_META,
                           "n_material": _texto(r.get("Nº Material")), "equipe": _texto(r.get("Equipe")),
                           "ativo": _texto(r.get("Ativo")), "equipamento": _texto(r.get("Equipamento")),
                           "tipo_material": _texto(r.get("Tipo Material")),
                           "qtd": _num(r.get("Quantidade Programada"), 0.0), "observacao": _texto(r.get("Observação"))})
    return linhas


SEM_META = "(SEM META)"     # lançamento antigo sem meta: guardado para correção, não pesa na curva


def linha_lancamento(r: dict) -> dict | None:
    """Linha do modelo v3 (aba Lancamentos) -> colunas do banco. None se faltar Depto ou Data."""
    d, depto, meta = _data(r.get("Data")), _texto(r.get("Depto"), True), _texto(r.get("Descrição Meta"), True)
    if not (d and depto):
        return None
    meta = meta or SEM_META
    no_plano = _texto(r.get("No Plano"))
    if no_plano:
        no_plano = {"s": "Sim", "sim": "Sim", "n": "Não", "não": "Não", "nao": "Não"}.get(no_plano.lower(), no_plano)
    return {"depto": depto, "data": d, "meta": meta, "n_material": _texto(r.get("Nº Material")),
            "equipe": _texto(r.get("Equipe")), "ativo": _texto(r.get("Ativo")),
            "tipo_material": _texto(r.get("Tipo Material")),
            "qtd_prog": _num(r.get("Quantidade Programada"), 0.0), "qtd_real": _num(r.get("Quantidade Realizada"), 0.0),
            "no_plano": no_plano, "justificativa": _texto(r.get("Justificativa")),
            "observacao": _texto(r.get("Observação")), "plano_acao": _texto(r.get("Plano de Ação")),
            "responsavel": _texto(r.get("Responsável")), "prazo": _data(r.get("Prazo")),
            "status": _texto(r.get("Status")), "programador": _texto(r.get("Programador"))}


def substituir_plano(tid: int, pesos_df: pd.DataFrame, plano_df: pd.DataFrame, usuario: str) -> tuple[int, int]:
    """Troca Pesos + Plano do trimestre (lançamentos ficam intactos)."""
    lp, ll = _linhas_pesos(tid, pesos_df), _linhas_plano(tid, plano_df)
    with get_engine().begin() as conn:
        conn.execute(delete(S.pesos).where(S.pesos.c.trimestre_id == tid))
        conn.execute(delete(S.plano).where(S.plano.c.trimestre_id == tid))
        if lp:
            conn.execute(insert(S.pesos), _cabe(S.pesos, lp))
        if ll:
            conn.execute(insert(S.plano), _cabe(S.plano, ll))
        _auditar(conn, usuario, "substituir_plano", "plano", tid, {"pesos": len(lp), "plano": len(ll)})
        _bump(conn)
    return len(lp), len(ll)


def substituir_lancamentos(tid: int, lanc_df: pd.DataFrame, usuario: str, deptos: list[str] | None = None) -> int:
    """Troca os lançamentos do trimestre (upload) — todos, ou só os dos ``deptos``.
    Antes, guarda cópia do trimestre em lancamentos_copia."""
    agora = datetime.now()
    linhas = []
    for r in lanc_df.to_dict("records"):
        ln = linha_lancamento(r)
        if ln and (deptos is None or ln["depto"] in deptos):
            linhas.append({**ln, "trimestre_id": tid, "origem": "upload", "criado_por": usuario, "criado_em": agora})
    apagar = S.lancamentos.c.trimestre_id == tid
    if deptos is not None:
        apagar = and_(apagar, S.lancamentos.c.depto.in_(deptos))
    with get_engine().begin() as conn:
        _copiar_lancamentos(conn, tid, "upload", usuario)
        conn.execute(delete(S.lancamentos).where(apagar))
        if linhas:
            conn.execute(insert(S.lancamentos), _cabe(S.lancamentos, linhas))
        _auditar(conn, usuario, "substituir_lancamentos", "lancamentos", tid,
                 {"linhas": len(linhas), "deptos": deptos or "todos"})
        _bump(conn)
    return len(linhas)


def salvar_edicao_lancamentos(tid: int, novos: list[dict], alterados: dict[int, dict],
                              excluidos: list[int], usuario: str, deptos: list[str]) -> None:
    """Grava a edição linha a linha da tela de Lançamentos (já validada).
    novos/alterados: dicts no formato do banco (linha_lancamento).
    ``deptos``: Deptos que o usuário pode editar — o banco só altera/exclui
    registros desses Deptos (defesa em profundidade além da validação da tela)."""
    if any(n["depto"] not in deptos for n in [*novos, *alterados.values()]):
        raise PermissionError("Lançamento em Depto não permitido para o usuário.")
    agora = datetime.now()
    no_escopo = and_(S.lancamentos.c.trimestre_id == tid, S.lancamentos.c.depto.in_(deptos))
    with get_engine().begin() as conn:
        if excluidos:
            conn.execute(delete(S.lancamentos).where(and_(no_escopo, S.lancamentos.c.id.in_(excluidos))))
        for lid, valores in alterados.items():
            valores = _cabe(S.lancamentos, [dict(valores)])[0]
            res = conn.execute(update(S.lancamentos).where(and_(no_escopo, S.lancamentos.c.id == lid))
                               .values(**valores, origem="app", alterado_por=usuario, alterado_em=agora))
            if res.rowcount != 1:
                raise PermissionError(f"Lançamento #{lid} não encontrado no seu escopo (trimestre/Depto).")
        if novos:
            conn.execute(insert(S.lancamentos), _cabe(S.lancamentos, [
                {**n, "trimestre_id": tid, "origem": "app", "criado_por": usuario, "criado_em": agora} for n in novos]))
        _auditar(conn, usuario, "editar_lancamentos", "lancamentos", tid,
                 {"novos": len(novos), "alterados": sorted(alterados), "excluidos": sorted(excluidos)})
        _bump(conn)

# endregion


# region ====================== SESSÃO 5b: Proteção dos lançamentos ======================
# Todo upload que substitui lançamentos, toda exclusão de trimestre e toda
# restauração guardam ANTES uma cópia (JSON) em lancamentos_copia, na mesma
# transação. Ficam as COPIAS_POR_TRIMESTRE mais recentes de cada trimestre.

COPIAS_POR_TRIMESTRE = 10


def lancamentos_do_app() -> dict[int, int]:
    """{trimestre_id: nº de lançamentos digitados/corrigidos na tela de Lançamentos}."""
    c = S.lancamentos.c
    with get_engine().connect() as conn:
        return dict(conn.execute(select(c.trimestre_id, func.count())
                                 .where(or_(c.origem == "app", c.alterado_por.is_not(None)))
                                 .group_by(c.trimestre_id)).fetchall())


def lancamentos_por_depto(tid: int) -> pd.DataFrame:
    """Depto, total de lançamentos e quantos foram digitados/corrigidos no app."""
    c = S.lancamentos.c
    do_app = func.sum(case((or_(c.origem == "app", c.alterado_por.is_not(None)), 1), else_=0))
    with get_engine().connect() as conn:
        df = _df(conn, select(c.depto, func.count().label("total"), do_app.label("app"))
                 .where(c.trimestre_id == tid).group_by(c.depto))
    return df.astype({"total": int, "app": int}) if not df.empty else df


def _copiar_lancamentos(conn, tid: int, motivo: str, usuario: str) -> None:
    linhas = [dict(r) for r in conn.execute(select(S.lancamentos).where(S.lancamentos.c.trimestre_id == tid)).mappings()]
    t = conn.execute(select(S.trimestres.c.ano, S.trimestres.c.trimestre).where(S.trimestres.c.id == tid)).first()
    if not linhas or t is None:
        return
    for ln in linhas:
        ln.pop("id"), ln.pop("trimestre_id")
    cp = S.lancamentos_copia
    conn.execute(insert(cp).values(ano=t.ano, trimestre=t.trimestre, quando=datetime.now(), usuario=usuario,
                                   motivo=motivo, linhas=len(linhas),
                                   dados=json.dumps(linhas, ensure_ascii=False, default=str)))
    velhas = (select(cp.c.id).where(and_(cp.c.ano == t.ano, cp.c.trimestre == t.trimestre))
              .order_by(cp.c.quando.desc(), cp.c.id.desc()).offset(COPIAS_POR_TRIMESTRE))
    ids = [r[0] for r in conn.execute(velhas)]
    if ids:
        conn.execute(delete(cp).where(cp.c.id.in_(ids)))


def listar_copias(ano: int, tri: int) -> pd.DataFrame:
    cp = S.lancamentos_copia
    with get_engine().connect() as conn:
        return _df(conn, select(cp.c.id, cp.c.quando, cp.c.usuario, cp.c.motivo, cp.c.linhas)
                   .where(and_(cp.c.ano == ano, cp.c.trimestre == tri)).order_by(cp.c.quando.desc()))


def restaurar_copia(copia_id: int, usuario: str) -> int:
    """Volta os lançamentos do trimestre para a cópia (o estado atual vira uma nova cópia)."""
    cp = S.lancamentos_copia
    with get_engine().connect() as conn:
        r = conn.execute(select(cp).where(cp.c.id == copia_id)).mappings().first()
    if r is None:
        raise ValueError("Cópia não encontrada.")
    tid = garantir_trimestre(int(r["ano"]), int(r["trimestre"]), usuario)
    tipos = {c.name: c.type for c in S.lancamentos.c}
    linhas = []
    for ln in json.loads(r["dados"]):
        for k, v in ln.items():
            if isinstance(v, str) and isinstance(tipos.get(k), DateTime):
                ln[k] = datetime.fromisoformat(v)
            elif isinstance(v, str) and isinstance(tipos.get(k), Date):
                ln[k] = date.fromisoformat(v[:10])
        linhas.append({k: v for k, v in ln.items() if k in tipos} | {"trimestre_id": tid})
    with get_engine().begin() as conn:
        _copiar_lancamentos(conn, tid, "antes de restaurar", usuario)
        conn.execute(delete(S.lancamentos).where(S.lancamentos.c.trimestre_id == tid))
        if linhas:
            conn.execute(insert(S.lancamentos), linhas)
        _auditar(conn, usuario, "restaurar_lancamentos", "lancamentos", tid,
                 {"copia": copia_id, "linhas": len(linhas)})
        _bump(conn)
    return len(linhas)

# endregion


# region ====================== SESSÃO 6: Catálogo (Unidade/SLA) e listas ======================

def listar_catalogo() -> pd.DataFrame:
    with get_engine().connect() as c:
        df = _df(c, select(S.metas_catalogo).order_by(S.metas_catalogo.c.depto, S.metas_catalogo.c.meta))
    return df.rename(columns={"depto": "Depto", "meta": "Descrição Meta", "unidade": "Unidade", "sla": "SLA"})


def salvar_catalogo(df: pd.DataFrame, usuario: str, deptos: list[str] | None = None) -> None:
    """Regrava o catálogo. ``deptos`` limita o escopo (programador só mexe no seu)."""
    linhas = {}
    for _, r in df.iterrows():
        depto, meta = _texto(r.get("Depto"), True), _texto(r.get("Descrição Meta"), True)
        if depto and meta and (deptos is None or depto in deptos):
            linhas[(depto, meta)] = {"depto": depto, "meta": meta, "unidade": _texto(r.get("Unidade")),
                                     "sla": _num(r.get("SLA"))}
    with get_engine().begin() as conn:
        q = delete(S.metas_catalogo)
        if deptos is not None:
            q = q.where(S.metas_catalogo.c.depto.in_(deptos))
        conn.execute(q)
        if linhas:
            conn.execute(insert(S.metas_catalogo), list(linhas.values()))
        _auditar(conn, usuario, "salvar", "metas_catalogo", detalhe={"linhas": len(linhas), "deptos": deptos})
        _bump(conn)


def completar_catalogo(df: pd.DataFrame, usuario: str) -> int:
    """Inclui Depto×Meta que ainda não estão no catálogo e preenche Unidade/SLA
    vazios. Nunca sobrescreve o que já foi configurado."""
    atual = listar_catalogo().set_index(["Depto", "Descrição Meta"])
    novos, n = [], 0
    with get_engine().begin() as conn:
        for _, r in df.iterrows():
            depto, meta = _texto(r.get("Depto"), True), _texto(r.get("Descrição Meta"), True)
            if not (depto and meta):
                continue
            unid, sla = _texto(r.get("Unidade")), _num(r.get("SLA"))
            if unid == "-":
                unid = None
            if (depto, meta) not in atual.index:
                novos.append({"depto": depto, "meta": meta, "unidade": unid, "sla": sla})
                atual.loc[(depto, meta), ["Unidade", "SLA"]] = [unid, sla]
                continue
            ex = atual.loc[(depto, meta)]
            mud = {}
            if unid and pd.isna(ex["Unidade"]):
                mud["unidade"] = unid
            if sla is not None and pd.isna(ex["SLA"]):
                mud["sla"] = sla
            if mud:
                conn.execute(update(S.metas_catalogo).where(and_(S.metas_catalogo.c.depto == depto,
                                                                 S.metas_catalogo.c.meta == meta)).values(**mud))
                n += 1
        if novos:
            conn.execute(insert(S.metas_catalogo), novos)
        if novos or n:
            _auditar(conn, usuario, "completar", "metas_catalogo", detalhe={"novos": len(novos), "atualizados": n})
            _bump(conn)
    return len(novos) + n


def listar_listas() -> pd.DataFrame:
    with get_engine().connect() as c:
        return _df(c, select(S.listas).order_by(S.listas.c.tipo, S.listas.c.depto, S.listas.c.valor))


def opcoes(tipo: str, depto: str | None = None) -> list[str]:
    """Valores ativos de uma lista; com depto, junta os gerais ("") e os do Depto."""
    df = listar_listas()
    df = df[(df["tipo"] == tipo) & df["ativo"].astype(bool)]
    if depto is not None:
        df = df[df["depto"].isin(["", depto])]
    return sorted(df["valor"].dropna().unique().tolist())


def salvar_listas(tipo: str, df: pd.DataFrame, usuario: str, deptos: list[str] | None = None) -> None:
    linhas = {}
    for _, r in df.iterrows():
        valor = _texto(r.get("valor"))
        depto = _texto(r.get("depto"), True) or ""
        if valor and (deptos is None or depto in deptos):
            linhas[(valor, depto)] = {"tipo": tipo, "valor": valor, "depto": depto,
                                      "ativo": bool(r.get("ativo", True)) if pd.notna(r.get("ativo", True)) else True}
    with get_engine().begin() as conn:
        q = delete(S.listas).where(S.listas.c.tipo == tipo)
        if deptos is not None:
            q = q.where(S.listas.c.depto.in_(deptos))
        conn.execute(q)
        if linhas:
            conn.execute(insert(S.listas), _cabe(S.listas, list(linhas.values())))
        _auditar(conn, usuario, "salvar", "listas", detalhe={"tipo": tipo, "linhas": len(linhas)})
        _bump(conn)


def adicionar_equipes(pares: set[tuple[str, str]], usuario: str) -> int:
    """Inclui (Depto, Equipe) que ainda não existem na lista de Equipes."""
    df = listar_listas()
    existentes = set(zip(df.loc[df["tipo"] == "Equipe", "depto"], df.loc[df["tipo"] == "Equipe", "valor"]))
    novos = [{"tipo": "Equipe", "valor": e, "depto": d, "ativo": True}
             for d, e in sorted(pares) if d and e and (d, e) not in existentes]
    if novos:
        with get_engine().begin() as conn:
            conn.execute(insert(S.listas), novos)
            _auditar(conn, usuario, "adicionar_equipes", "listas", detalhe={"novas": len(novos)})
            _bump(conn)
    return len(novos)

# endregion


# region ====================== SESSÃO 7: Usuários e auditoria ======================

def contar_usuarios() -> int:
    with get_engine().connect() as c:
        return int(c.execute(select(func.count()).select_from(S.usuarios)).scalar() or 0)


def usuario_por_login(login: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(select(S.usuarios).where(func.lower(S.usuarios.c.login) == login.strip().lower())).mappings().first()
        return dict(r) if r else None


def listar_usuarios() -> pd.DataFrame:
    with get_engine().connect() as c:
        df = _df(c, select(S.usuarios).order_by(S.usuarios.c.nome))
    return df.drop(columns=["senha_hash"], errors="ignore")


def criar_usuario(login: str, nome: str, senha_hash: str, perfil: str, depto: str | None,
                  email: str | None, usuario: str, deve_trocar_senha: bool = True) -> int:
    with get_engine().begin() as conn:
        uid = conn.execute(insert(S.usuarios).values(
            login=login.strip(), nome=nome.strip(), email=_texto(email), senha_hash=senha_hash,
            perfil=perfil, depto=_texto(depto, True), ativo=True,
            deve_trocar_senha=deve_trocar_senha)).inserted_primary_key[0]
        _auditar(conn, usuario, "criar", "usuarios", uid, {"login": login, "perfil": perfil, "depto": depto})
        return int(uid)


def criar_primeiro_admin(login: str, nome: str, senha_hash: str, email: str | None) -> bool:
    """Cria o 1º administrador só se a tabela estiver vazia (checagem e insert na mesma transação)."""
    with get_engine().begin() as conn:
        if conn.execute(select(func.count()).select_from(S.usuarios)).scalar():
            return False
        uid = conn.execute(insert(S.usuarios).values(
            login=login.strip(), nome=nome.strip(), email=_texto(email), senha_hash=senha_hash,
            perfil="admin", ativo=True, deve_trocar_senha=False)).inserted_primary_key[0]
        _auditar(conn, login, "criar_primeiro_admin", "usuarios", uid)
        return True


def admins_ativos() -> int:
    with get_engine().connect() as c:
        return int(c.execute(select(func.count()).select_from(S.usuarios).where(
            and_(S.usuarios.c.perfil == "admin", S.usuarios.c.ativo.is_(True)))).scalar() or 0)


def atualizar_usuario(uid: int, usuario: str, **campos) -> None:
    with get_engine().begin() as conn:
        conn.execute(update(S.usuarios).where(S.usuarios.c.id == uid).values(**campos))
        _auditar(conn, usuario, "atualizar", "usuarios", uid,
                 {k: ("***" if k == "senha_hash" else v) for k, v in campos.items()})


def registrar_login(uid: int, login: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(update(S.usuarios).where(S.usuarios.c.id == uid).values(ultimo_login=datetime.now()))
        _auditar(conn, login, "login", "usuarios", uid)


def listar_auditoria(limite: int = 300) -> pd.DataFrame:
    with get_engine().connect() as c:
        return _df(c, select(S.auditoria).order_by(S.auditoria.c.id.desc()).limit(limite))

# endregion
