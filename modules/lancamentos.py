# modules/lancamentos.py — Lançamento e correção das atividades (programadores)
#
# Mesmas colunas da aba Lancamentos da planilha (modelo v3), numa grade
# editável (st.data_editor):
#   - editar qualquer célula = corrigir a linha
#   - última linha em branco = incluir; selecionar e apagar = excluir
#   - "Trazer o plano" pré-preenche as linhas do Plano PCM da(s) semana(s)
#     (Quantidade Programada = plano; o programador só informa o realizado)
# Só grava ao clicar em "Salvar" (diff: novos / alterados / excluídos), com
# validação e registro na auditoria. Trimestre fechado = somente leitura
# (exceto administrador). Programador só vê/edita o seu Depto.

from datetime import date

import pandas as pd
import streamlit as st

from auth import permissions as perm
from auth.session import get_login, get_nome
from core import modelo
from core.dados import semana_excel
from core.ui import titulo
from database import queries as q
from modules import comum

COLS = ["id", "Semana"] + modelo.COLS_LANC
CAMPOS_EDITAVEIS = modelo.COLS_LANC


# region ====================== SESSÃO 1: Preparação ======================

def _semana_atual(t: dict) -> int | None:
    s = int(semana_excel(pd.Series([pd.Timestamp(date.today())])).iloc[0])
    return s if t["semana_inicio"] <= s <= t["semana_fim"] and date.today().year == t["ano"] else None


def _base_editor(lanc: pd.DataFrame, depto: str, semanas: list[int]) -> pd.DataFrame:
    df = lanc.copy()
    df["Semana"] = semana_excel(df["Data"])
    df = df[df["Depto"] == depto]
    if semanas:
        df = df[df["Semana"].isin(semanas)]
    df = df.reindex(columns=COLS)
    df["id"] = df["id"].astype("Int64")
    for c in ("Data", "Prazo"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("Quantidade Programada", "Quantidade Realizada"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    texto = [c for c in COLS if c not in ("id", "Semana", "Data", "Prazo",
                                          "Quantidade Programada", "Quantidade Realizada")]
    df[texto] = df[texto].astype(object).where(df[texto].notna(), None)
    return df.reset_index(drop=True)


def _plano_para_lancar(plano: pd.DataFrame, depto: str, semanas: list[int]) -> pd.DataFrame:
    pl = plano[plano["Depto"] == depto].copy()
    pl["Semana"] = semana_excel(pl["Data Planejada"])
    if semanas:
        pl = pl[pl["Semana"].isin(semanas)]
    return pl


def _config_colunas(deptos, metas, equipes, ativos, listas_tipo, so_leitura):
    sel = st.column_config.SelectboxColumn
    return {
        "id": st.column_config.NumberColumn("#", disabled=True, help="Nº do registro (vazio = linha nova)"),
        "Semana": st.column_config.NumberColumn(disabled=True, help="Calculada pela data (WEEKNUM)"),
        "Depto": sel(options=deptos, required=True),
        "Data": st.column_config.DateColumn(format="DD/MM/YYYY", required=True),
        "Descrição Meta": sel(options=metas, required=True, width="large"),
        "Equipe": sel(options=equipes),
        # Sem relação de ativos carregada (Dados → Upload), o campo segue livre.
        "Ativo": sel(options=ativos, width="medium") if ativos else st.column_config.TextColumn(),
        "Tipo Material": sel(options=listas_tipo("Tipo Material")),
        "Quantidade Programada": st.column_config.NumberColumn(min_value=0, format="%.2f"),
        "Quantidade Realizada": st.column_config.NumberColumn(min_value=0, format="%.2f"),
        "No Plano": sel(options=["Sim", "Não"], help="Sim = atividade do plano · Não = extra plano"),
        "Justificativa": sel(options=listas_tipo("Justificativa"),
                             help="Obrigatória quando o realizado fica abaixo do programado"),
        "Status": sel(options=listas_tipo("Status")),
        "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Observação": st.column_config.TextColumn(width="large"),
        "Plano de Ação": st.column_config.TextColumn(width="medium"),
    }

# endregion


# region ====================== SESSÃO 2: Validação e gravação ======================

def _originais(original: pd.DataFrame) -> dict[int, dict]:
    return {int(r["id"]): q.linha_lancamento(r) for r in original.to_dict("records") if pd.notna(r["id"])}


def _validar(editado: pd.DataFrame, t: dict, deptos_ok: list[str], depto_padrao: str,
             metas_com_peso: set[str], orig: dict[int, dict]) -> tuple[list[dict], list[str], list[str]]:
    """Devolve (linhas no formato do banco, erros, alertas). Linha = posição na grade.
    Só valida linhas novas ou alteradas (linha antiga intacta não bloqueia o salvar)."""
    ini = pd.Timestamp(t["ano"], 3 * (t["trimestre"] - 1) + 1, 1)
    fim = ini + pd.offsets.QuarterEnd(0)
    linhas, erros, alertas = [], [], []
    for i, r in enumerate(editado.to_dict("records"), start=1):
        if pd.notna(r.get("id")) and q.linha_lancamento(r) == orig.get(int(r["id"])):
            linhas.append(orig[int(r["id"])])        # intacta
            continue
        if all(pd.isna(r.get(c)) or r.get(c) in ("", None) for c in CAMPOS_EDITAVEIS):
            linhas.append(None)          # linha nova deixada em branco: ignora
            continue
        r = dict(r)
        if pd.isna(r.get("id")):                     # padrões só para linha nova
            r["Depto"] = r.get("Depto") or depto_padrao
            r["No Plano"] = r.get("No Plano") or "Sim"
            r["Programador"] = r.get("Programador") or get_nome()
        ln = q.linha_lancamento(r)
        if ln is None:
            erros.append(f"Linha {i}: informe a Data.")
            linhas.append(None)
            continue
        if ln["depto"] not in deptos_ok:
            erros.append(f"Linha {i}: você não pode lançar no Depto {ln['depto']}.")
        if not (ini.date() <= ln["data"] <= fim.date()):
            erros.append(f"Linha {i}: data {ln['data']:%d/%m/%Y} fora do {t['rotulo']}.")
        if ln["no_plano"] not in ("Sim", "Não"):
            erros.append(f"Linha {i}: 'No Plano' deve ser Sim ou Não.")
        if (ln["qtd_real"] or 0) < 0 or (ln["qtd_prog"] or 0) < 0:
            erros.append(f"Linha {i}: quantidade negativa.")
        if ln["meta"] == q.SEM_META or f"{ln['depto']}|{ln['meta']}" not in metas_com_peso:
            alertas.append(f"Linha {i}: '{ln['meta']}' não tem peso no {ln['depto']} — não conta na curva.")
        if (ln["qtd_real"] or 0) < (ln["qtd_prog"] or 0) and not ln["justificativa"]:
            alertas.append(f"Linha {i}: realizado abaixo do programado sem Justificativa.")
        linhas.append(ln)
    return linhas, erros, alertas


def _diff(orig: dict[int, dict], editado: pd.DataFrame, linhas: list):
    novos, alterados, vistos = [], {}, set()
    for r, ln in zip(editado.to_dict("records"), linhas):
        if ln is None:
            continue
        if pd.isna(r.get("id")):
            novos.append(ln)
        else:
            lid = int(r["id"])
            vistos.add(lid)
            if ln != orig.get(lid):
                alterados[lid] = ln
    excluidos = [lid for lid in orig if lid not in vistos]
    return novos, alterados, excluidos

# endregion


def render_lancamentos() -> None:
    perm.require(perm.pode_lancar())
    t = comum.exige_trimestre()
    tid = int(t["id"])
    so_leitura = t["status"] == "fechado" and not perm.pode_editar_fechado()
    titulo(f"Lançamentos — {t['rotulo']}",
           "Corrija direto na grade · linha em branco no fim = incluir · selecione e apague = excluir · "
           "nada é gravado até clicar em Salvar")
    if so_leitura:
        st.warning("🔒 Trimestre fechado: somente leitura. Peça ao administrador para reabrir.")

    pesos, plano, lanc = comum.dados_trimestre(tid)
    deptos = perm.deptos_permitidos(sorted(set(comum.deptos_cadastrados()) | set(pesos["Depto"].dropna())))
    if not deptos:
        st.error("Nenhum Depto disponível para você. Confira seu cadastro (Depto delegado).")
        st.stop()

    # ---- Filtros --------------------------------------------------------- #
    c1, c2 = st.columns([1, 3])
    depto = c1.selectbox("Depto", deptos, disabled=len(deptos) == 1)
    todas = list(range(int(t["semana_inicio"]), int(t["semana_fim"]) + 1))
    atual = _semana_atual(t)
    semanas = c2.multiselect("Semanas (vazio = todas)", todas, default=[atual] if atual else [],
                             key=f"sem_{tid}_{depto}")

    _, _, catalogo, listas = comum.cadastros()

    def listas_tipo(tipo):
        df = listas[(listas["tipo"] == tipo) & listas["ativo"].astype(bool) & listas["depto"].isin(["", depto])]
        return sorted(df["valor"].unique().tolist())

    metas_depto = sorted(pesos.loc[pesos["Depto"] == depto, "Descrição Meta"].dropna().unique().tolist())
    metas_com_peso = set(pesos["Depto"] + "|" + pesos["Descrição Meta"])
    base = _base_editor(lanc, depto, semanas)
    metas = sorted(set(metas_depto) | set(base["Descrição Meta"].dropna()))
    equipes = sorted(set(listas_tipo("Equipe")) | set(base["Equipe"].dropna().astype(str)))

    # ---- Plano da semana (referência + pré-preenchimento) ----------------- #
    chave_pre = f"pre_{tid}_{depto}_{','.join(map(str, semanas))}"
    pl = _plano_para_lancar(plano, depto, semanas)
    with st.expander(f"📌 Plano PCM congelado — {depto} · "
                     f"{'semana(s) ' + ', '.join(map(str, semanas)) if semanas else 'trimestre todo'} "
                     f"({len(pl)} linha(s))"):
        if pl.empty:
            st.caption("Sem plano para o filtro.")
        else:
            st.dataframe(pl[["Semana", "Data Planejada", "Descrição Meta", "Equipe", "Ativo",
                             "Quantidade Programada", "Observação"]],
                         hide_index=True, width="stretch",
                         column_config={"Data Planejada": st.column_config.DateColumn(format="DD/MM/YYYY")})
            if not so_leitura and st.button("➕ Trazer estas linhas do plano para lançar", key=f"btn_{chave_pre}"):
                st.session_state[chave_pre] = pl
                st.rerun()

    pre = st.session_state.get(chave_pre)
    if pre is not None and not pre.empty:
        novos = pd.DataFrame({
            "Depto": pre["Depto"], "Data": pd.to_datetime(pre["Data Planejada"]),
            "Descrição Meta": pre["Descrição Meta"], "Nº Material": pre["Nº Material"],
            "Equipe": pre["Equipe"], "Ativo": pre["Ativo"], "Tipo Material": pre["Tipo Material"],
            "Quantidade Programada": pre["Quantidade Programada"], "No Plano": "Sim",
            "Programador": get_nome()}).reindex(columns=COLS)
        novos["Semana"] = semana_excel(novos["Data"])
        base_ed = pd.concat([base, novos], ignore_index=True)
        st.info(f"{len(pre)} linha(s) do plano pré-preenchidas no fim da grade. "
                "Informe a Quantidade Realizada e clique em Salvar (ou Descartar).")
    else:
        base_ed = base

    # ---- Grade ----------------------------------------------------------- #
    relacao = listas_tipo("Ativo")
    ativos = sorted(set(relacao) | (set(base_ed["Ativo"].dropna().astype(str)) - {""})) if relacao else []
    editado = st.data_editor(
        base_ed, key=f"ed_{chave_pre}", num_rows="fixed" if so_leitura else "dynamic",
        disabled=so_leitura, hide_index=True, width="stretch", height=520,
        column_config=_config_colunas(deptos, metas, equipes, ativos, listas_tipo, so_leitura))

    if so_leitura:
        return
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("💾 Salvar", type="primary", key=f"salvar_{chave_pre}"):
        orig = _originais(base)
        linhas, erros, alertas = _validar(editado, t, deptos, depto, metas_com_peso, orig)
        if erros:
            st.error("Nada foi gravado. Corrija:\n\n- " + "\n- ".join(erros[:20]))
        else:
            novos, alterados, excluidos = _diff(orig, editado, linhas)
            if not (novos or alterados or excluidos):
                st.info("Nenhuma alteração para salvar.")
            else:
                q.salvar_edicao_lancamentos(tid, novos, alterados, excluidos, get_login(), deptos)
                st.session_state.pop(chave_pre, None)
                st.session_state.pop(f"ed_{chave_pre}", None)
                comum.limpar_cache()
                st.session_state["msg_lanc"] = (f"✅ Gravado: {len(novos)} novo(s), {len(alterados)} alterado(s), "
                                                f"{len(excluidos)} excluído(s).", alertas)
                st.rerun()
    if b2.button("↩️ Descartar", key=f"desc_{chave_pre}"):
        st.session_state.pop(chave_pre, None)
        st.session_state.pop(f"ed_{chave_pre}", None)
        st.rerun()

    msg = st.session_state.pop("msg_lanc", None)
    if msg:
        st.success(msg[0])
        for a in msg[1][:15]:
            st.warning(a)
    st.caption(f"{len(base)} lançamento(s) no filtro · SLA e Unidade em Configurações → SLA e Unidades.")
