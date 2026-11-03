# modules/dados.py — Upload (plano do PCM / histórico) e exportação (backup)
#
# Upload (admin e PCM):
#   A) Plano do trimestre — exports do PCM: "data (N).xlsx" (pesos por meta,
#      coluna Peso Item Redist) + "Planejamento PCM.xlsx" (visão congelada, por
#      dia). Cria o trimestre se não existir; troca Pesos/Plano e MANTÉM os
#      lançamentos. Equipes do planejamento entram na lista de Equipes.
#   B) Planilha de trimestre — modelo v3 (inclusive backup exportado daqui) ou a
#      planilha antiga (Diário + Planilha de Peso). Serve para carregar o
#      HISTÓRICO (trimestres passados com plano e realizado).
# Exportação (todos): planilha do trimestre no modelo v3 (mesmo layout do
#   Excel) e backup completo (.zip com todos os trimestres + cadastros).

import io
import os
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st

from auth import permissions as perm
from auth.session import get_login, set_trimestre_id
from core import config, importar_pcm, modelo, motor, planilha
from core.ui import titulo
from database import queries as q
from modules import comum


# region ====================== SESSÃO 1: Utilitários ======================

def _parametros_para(ano: int, tri: int) -> config.Parametros:
    cfg, coords, _, _ = comum.cadastros()
    ini, fim = q.janela_semanas(ano, tri)
    return motor.parametros(cfg, coords, ano, tri, ini, fim)


def _gravar(ano, tri, pesos, plano, lanc, trocar_plano: bool, trocar_lanc: bool) -> str:
    usuario = get_login()
    tid = q.garantir_trimestre(int(ano), int(tri), usuario)
    partes = []
    if trocar_plano:
        n_p, n_l = q.substituir_plano(tid, pesos, plano, usuario)
        q.completar_catalogo(pesos, usuario)
        partes.append(f"{n_p} pesos e {n_l} linhas de plano")
    if trocar_lanc:
        partes.append(f"{q.substituir_lancamentos(tid, lanc, usuario)} lançamentos")
    pares = set()
    for df in (plano, lanc):
        if df is not None and not df.empty and "Equipe" in df:
            pares |= {(str(d).strip().upper(), str(e).strip())
                      for d, e in zip(df["Depto"], df["Equipe"]) if pd.notna(d) and pd.notna(e) and str(e).strip()}
    n_eq = q.adicionar_equipes(pares, usuario)
    comum.limpar_cache()
    set_trimestre_id(tid)
    return f"✅ {tri}º tri/{ano}: " + " + ".join(partes) + (f" · {n_eq} equipe(s) nova(s)" if n_eq else "")


def _ja_existe(ano, tri) -> dict | None:
    tri_df = comum.trimestres()
    m = tri_df[(tri_df["ano"] == ano) & (tri_df["trimestre"] == tri)] if not tri_df.empty else tri_df
    return None if m.empty else m.iloc[0].to_dict()


def _listas_export(listas: pd.DataFrame, pesos: pd.DataFrame) -> dict:
    out = dict(modelo.LISTAS_PADRAO)
    for tipo in ("Justificativa", "Status", "Tipo Material", "Grupo"):
        v = listas.loc[listas["tipo"] == tipo, "valor"].dropna().unique().tolist()
        if v:
            out[tipo] = sorted(v)
    out["Equipe"] = sorted(listas.loc[listas["tipo"] == "Equipe", "valor"].dropna().unique().tolist())
    out["Depto"] = sorted(set(comum.deptos_cadastrados()) | set(pesos["Depto"].dropna()))
    return out


def planilha_do_trimestre(tid: int) -> bytes:
    """Excel do trimestre no modelo v3 (Pesos com Unidade/SLA do catálogo)."""
    pesos, plano, lanc = comum.dados_trimestre(tid)
    _, _, catalogo, listas = comum.cadastros()
    pe = pesos.merge(catalogo[["Depto", "Descrição Meta", "Unidade", "SLA"]],
                     on=["Depto", "Descrição Meta"], how="left")
    return planilha.para_bytes(pe, plano, lanc.drop(columns=["id"], errors="ignore"), _listas_export(listas, pesos))

# endregion


# region ====================== SESSÃO 2: Upload ======================

def _upload_pcm():
    st.markdown("**1.** Export de pesos do PCM (ex.: `data (9).xlsx`, com a coluna *Peso Item Redist*)  \n"
                "**2.** Planejamento PCM congelado (ex.: `Planejamento PCM.xlsx`, plano por dia) — "
                "é a curva planejada; sem ele o plano é dividido igualmente pelas semanas.")
    c1, c2 = st.columns(2)
    f_pesos = c1.file_uploader("Export de pesos", type=["xlsx"], key="up_pcm_pesos")
    f_plan = c2.file_uploader("Planejamento PCM (opcional)", type=["xlsx"], key="up_pcm_plan")
    if not f_pesos:
        return
    try:
        cam_pesos = comum.salvar_temporario(f_pesos)
        cam_plan = comum.salvar_temporario(f_plan) if f_plan else None
        tri_ano = importar_pcm.trimestre_do_export(pd.read_excel(cam_pesos, header=None))
        if tri_ano is None:
            st.error("Não achei o trimestre no export (rodapé 'Tri/Ano é Tri 4/26').")
            return
        ano, tri = tri_ano
        _, _, catalogo, _ = comum.cadastros()
        r = importar_pcm.importar(cam_pesos, _parametros_para(ano, tri), catalogo, cam_plan)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler os arquivos: {e}")
        return
    pesos, plano = pd.DataFrame(r.pesos), pd.DataFrame(r.plano)
    st.markdown(f"#### {r.trimestre}º tri/{r.ano} — {len(pesos)} metas · {len(plano)} linhas de plano")
    for a in r.avisos:
        st.warning(a)
    with st.expander("Pré-visualizar"):
        st.dataframe(pesos, hide_index=True, width="stretch")
        st.dataframe(plano.head(200), hide_index=True, width="stretch")
    existe = _ja_existe(r.ano, r.trimestre)
    if existe is not None and existe["linhas_plano"] > 0:
        st.info(f"O {existe['rotulo']} já tem plano ({existe['linhas_plano']} linhas). Importar vai SUBSTITUIR "
                f"pesos e plano; os {existe['lancamentos']} lançamentos são mantidos.")
    if pesos.empty:
        st.error("Nada para importar.")
        return
    if st.button("📥 Importar plano do PCM", type="primary"):
        st.session_state["msg_dados"] = _gravar(r.ano, r.trimestre, pesos, plano, None, True, False)
        st.rerun()


def _upload_planilha():
    st.markdown("Planilha do trimestre no **modelo v3** (ou um backup exportado daqui) ou a **planilha antiga** "
                "(Diário + Planilha de Peso). Use para carregar o **histórico** de trimestres passados.")
    f = st.file_uploader("Planilha do trimestre", type=["xlsx", "xlsm"], key="up_planilha")
    if not f:
        return
    try:
        caminho = comum.salvar_temporario(f)
        tipo = planilha.identificar(caminho)
        if tipo in ("pcm_pesos", "pcm_planejamento"):
            st.error("Este é um export do PCM: use a opção **Plano do trimestre (exports do PCM)**.")
            return
        pesos, plano, lanc = planilha.ler(caminho, config.carregar())
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler a planilha: {e}")
        return
    sugerido = planilha.trimestre_dos_dados(plano, lanc) or (datetime.today().year, 1)
    st.caption(f"Formato reconhecido: **{'modelo v3' if tipo == 'v3' else 'planilha antiga (Diário)'}** · "
               f"{len(pesos)} pesos · {len(plano)} linhas de plano · {len(lanc)} lançamentos")
    c1, c2 = st.columns(2)
    ano = c1.number_input("Ano", 2020, 2100, int(sugerido[0]), key="up_ano")
    tri = c2.selectbox("Trimestre", [1, 2, 3, 4], index=int(sugerido[1]) - 1, key="up_tri")
    existe = _ja_existe(ano, tri)
    c3, c4 = st.columns(2)
    trocar_plano = c3.checkbox("Gravar Pesos + Plano", value=len(plano) > 0)
    trocar_lanc = c4.checkbox("Gravar Lançamentos", value=len(lanc) > 0)
    if existe is not None:
        st.warning(f"O {existe['rotulo']} já existe ({existe['linhas_plano']} linhas de plano, "
                   f"{existe['lancamentos']} lançamentos). O que estiver marcado acima será SUBSTITUÍDO.")
    if st.button("📥 Importar planilha", type="primary", disabled=not (trocar_plano or trocar_lanc)):
        st.session_state["msg_dados"] = _gravar(ano, tri, pesos, plano, lanc, trocar_plano, trocar_lanc)
        st.rerun()

# endregion


# region ====================== SESSÃO 3: Exportação ======================

def _exportar():
    tri = comum.trimestres()
    if tri.empty:
        st.info("Nada para exportar ainda.")
        return
    t = comum.trimestre_ativo()
    rotulos = dict(zip(tri["rotulo"], tri["id"]))
    escolha = st.selectbox("Trimestre", list(rotulos), index=list(rotulos.values()).index(t["id"]), key="exp_tri")
    tid = int(rotulos[escolha])
    nome = f"Plano_VP_{escolha.replace('º tri/', 'T').replace(' ', '')}_{datetime.now():%Y%m%d}.xlsx"
    st.download_button("⬇️ Baixar planilha do trimestre (modelo Excel)", planilha_do_trimestre(tid),
                       file_name=nome, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Mesmo layout da planilha (Pesos, Plano_PCM, Lancamentos, Listas). Pode ser reenviada em "
               "Upload → Planilha de trimestre para restaurar.")

    st.markdown("---")
    st.markdown("**Backup completo** — todos os trimestres + cadastros (SLA, listas, coordenações, configuração).")
    if st.button("📦 Gerar backup completo (.zip)"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for _, row in tri.iterrows():
                z.writestr(f"trimestres/Plano_{row['ano']}_T{row['trimestre']}.xlsx",
                           planilha_do_trimestre(int(row["id"])))
            cfg, coords, catalogo, listas = comum.cadastros()
            cad = io.BytesIO()
            with pd.ExcelWriter(cad, engine="openpyxl") as xw:
                catalogo.to_excel(xw, sheet_name="SLA_Unidades", index=False)
                listas.to_excel(xw, sheet_name="Listas", index=False)
                coords.to_excel(xw, sheet_name="Coordenacoes", index=False)
                pd.DataFrame(sorted(cfg.items()), columns=["chave", "valor"]).to_excel(
                    xw, sheet_name="Config", index=False)
                tri.drop(columns=["rotulo"], errors="ignore").to_excel(xw, sheet_name="Trimestres", index=False)
            z.writestr("cadastros.xlsx", cad.getvalue())
        st.download_button("⬇️ Baixar backup", buf.getvalue(), file_name=f"Backup_Plano_VP_{datetime.now():%Y%m%d_%H%M}.zip",
                           mime="application/zip")

# endregion


def render_dados() -> None:
    titulo("Dados", "Upload do plano do PCM e do histórico · exportação da planilha (backup)")
    msg = st.session_state.pop("msg_dados", None)
    if msg:
        st.success(msg)
    abas = st.tabs(["⬆️ Upload", "⬇️ Exportação"])
    with abas[0]:
        if not perm.pode_upload():
            st.info("🔒 Upload disponível para os perfis Administrador e PCM.")
        else:
            tipo = st.radio("O que você vai enviar?", ["Plano do trimestre (exports do PCM)",
                                                      "Planilha de trimestre (modelo v3, backup ou planilha antiga)"],
                            horizontal=True)
            if tipo.startswith("Plano"):
                _upload_pcm()
            else:
                _upload_planilha()
    with abas[1]:
        _exportar()
