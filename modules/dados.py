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
import tempfile
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


def _gravar_tipos_medicao(arquivo_pesos) -> None:
    """Tipo de medição (DEPTO/ATIVO) das metas -> config metas_medicao_depto (regra da Gerência)."""
    tipos = importar_pcm.tipos_de_medicao(arquivo_pesos)
    if tipos:
        cfg, _, _, _ = comum.cadastros()
        novo = importar_pcm.atualizar_metas_depto(cfg.get("metas_medicao_depto", ""), tipos)
        if novo != cfg.get("metas_medicao_depto", ""):
            q.salvar_config({"metas_medicao_depto": novo}, get_login())


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
        _gravar_tipos_medicao(cam_pesos)
        st.session_state["msg_dados"] = _gravar(r.ano, r.trimestre, pesos, plano, None, True, False)
        st.rerun()


@st.cache_data(show_spinner="Lendo os exports do PCM...", max_entries=2)
def _historico_pcm(planejado: bytes | None, realizado: bytes | None, pesos: bytes | None,
                   deptos: tuple, com_sem_meta: bool, tri_com_plano: tuple):
    with tempfile.TemporaryDirectory() as pasta:
        def tmp(nome, conteudo):
            if conteudo is None:
                return None
            caminho = os.path.join(pasta, nome)
            with open(caminho, "wb") as f:
                f.write(conteudo)
            return caminho
        return importar_pcm.montar_historico(set(deptos), tmp("planejado.xlsx", planejado),
                                             tmp("realizado.xlsx", realizado), tmp("pesos.xlsx", pesos),
                                             com_sem_meta, set(tri_com_plano))


def _upload_exports_historico(por_tipo: dict) -> None:
    """Planejado (N trimestres) + Realizado + export de pesos do Power BI do PCM."""
    st.caption("Exports do PCM reconhecidos: " + ", ".join(
        f"**{rot}**" for tipo, rot in (("pcm_planejamento", "Planejado"), ("pcm_realizado", "Realizado"),
                                      ("pcm_pesos", "Pesos")) if tipo in por_tipo))
    if "pcm_planejamento" in por_tipo and "pcm_pesos" not in por_tipo:
        st.error("Envie também o **export de pesos** (ex.: `data (9).xlsx`): ele traz o *Peso Item Inicial*, "
                 "o mesmo para todos os trimestres.")
        return
    com_sem_meta = st.checkbox("Incluir ordens sem Descrição Meta (fora do catálogo do plano — não pesam na curva)")
    tri_df = comum.trimestres()
    com_plano = tuple((int(a), int(t)) for a, t, n in
                      zip(tri_df.get("ano", []), tri_df.get("trimestre", []), tri_df.get("linhas_plano", [])) if n > 0)
    try:
        hist, avisos = _historico_pcm(*(por_tipo[k].getvalue() if k in por_tipo else None
                                        for k in ("pcm_planejamento", "pcm_realizado", "pcm_pesos")),
                                      tuple(comum.deptos_cadastrados()), com_sem_meta, com_plano)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler os exports: {e}")
        return
    for a in avisos:
        st.warning(a)
    if not hist:
        st.error("Nada para importar.")
        return
    linhas = []
    for (ano, tri), d in hist.items():
        ex = _ja_existe(ano, tri)
        lanc = d.get("lanc")
        linhas.append({"Trimestre": f"{tri}º tri/{ano}",
                       "Plano (linhas)": len(d["plano"]) if "plano" in d else "— mantém o atual",
                       "Realizado (linhas)": len(lanc) if lanc is not None else "—",
                       "Considera Plano = Sim": int((lanc["No Plano"] == "Sim").sum()) if lanc is not None else "—",
                       "Hoje no sistema": (f"{ex['linhas_plano']} plano · {ex['lancamentos']} lanç." if ex else "novo")})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    escolha = st.multiselect("Trimestres a gravar", [r["Trimestre"] for r in linhas],
                             default=[r["Trimestre"] for r in linhas])
    st.caption("Para cada trimestre escolhido: o plano (se veio no Planejado) e os lançamentos são **substituídos** "
               "pelos do PCM — inclusive lançamentos feitos na tela de Lançamentos.")
    if st.button("📥 Importar do PCM", type="primary", disabled=not escolha):
        if "pcm_pesos" in por_tipo:
            _gravar_tipos_medicao(comum.salvar_temporario(por_tipo["pcm_pesos"]))
        msgs = []
        for (ano, tri), d in hist.items():
            if f"{tri}º tri/{ano}" in escolha:
                msgs.append(_gravar(ano, tri, d.get("pesos"), d.get("plano"), d.get("lanc"),
                                    "plano" in d, "lanc" in d))
        st.session_state["msg_dados"] = "  \n".join(msgs)
        st.rerun()


def _upload_planilha():
    st.markdown("Planilha do trimestre no **modelo v3** (ou um backup exportado daqui), a **planilha antiga** "
                "(Diário + Planilha de Peso) **ou os exports do Power BI do PCM** — *Planejado* (congelado, 1 ou mais "
                "trimestres), *Realizado* (ordens lançadas pelos programadores) e o *export de pesos*. Pode enviar "
                "vários arquivos juntos.")
    arquivos = st.file_uploader("Arquivos", type=["xlsx", "xlsm"], key="up_planilha", accept_multiple_files=True)
    if not arquivos:
        return
    try:
        tipados = [(f, planilha.identificar(comum.salvar_temporario(f))) for f in arquivos]
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível ler os arquivos: {e}")
        return
    contagem = pd.Series([t for _, t in tipados]).value_counts()
    repetidos = [t for t, n in contagem.items() if n > 1 and t.startswith("pcm_")]
    if repetidos:
        st.error("Envie no máximo **um arquivo de cada tipo** do PCM (Planejado, Realizado, Pesos). Repetido: "
                 + ", ".join(repetidos))
        return
    tipos = {f.name: t for f, t in tipados}
    por_tipo = {t: f for f, t in tipados}
    if {"pcm_planejamento", "pcm_realizado"} & set(por_tipo):
        _upload_exports_historico(por_tipo)
        return
    desconhecidos = [f.name for f, t in tipados if t == "desconhecido"]
    if desconhecidos:
        st.error("Formato não reconhecido: " + ", ".join(desconhecidos))
        return
    if len(arquivos) > 1:
        st.info("Planilha de trimestre (modelo v3 ou antiga): envie uma por vez.")
        return
    f = arquivos[0]
    try:
        caminho = comum.salvar_temporario(f)
        tipo = tipados[0][1]
        if tipo == "pcm_pesos":
            st.error("Só o export de pesos: para o início de trimestre use **Plano do trimestre (exports do PCM)**; "
                     "para histórico envie junto o *Planejado* e/ou o *Realizado*.")
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
