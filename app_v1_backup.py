# region Imports e Configuração
import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Dashboard Manutenção VP", layout="wide", initial_sidebar_state="expanded")

# CSS Avançado: Visual Clean Executive (Premium Light)
st.markdown("""
    <style>
    [data-testid="baseButton-formSubmit"] {
        background-color: #0052cc !important; color: white !important;
        border-radius: 6px; font-weight: 700; border: none; padding: 8px; width: 100%;
        transition: all 0.2s ease-in-out;
    }
    [data-testid="baseButton-formSubmit"]:hover { background-color: #003d99 !important; transform: translateY(-2px); }
    .metric-card {
        background-color: #ffffff; border-radius: 10px; padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0;
        border-left: 6px solid #0052cc; margin-bottom: 20px;
    }
    .metric-title { color: #64748b; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; margin-bottom: 5px;}
    .metric-value { color: #0f172a; font-size: 2.2rem; font-weight: 800; line-height: 1.2; }
    .metric-sub { color: #64748b; font-size: 0.85rem; margin-top: 10px; border-top: 1px solid #f1f5f9; padding-top: 8px;}
    .trend-adiantado { border-left-color: #10b981; } .trend-leve { border-left-color: #f59e0b; }
    .trend-risco { border-left-color: #f97316; } .trend-critico { border-left-color: #ef4444; }
    </style>
""", unsafe_allow_html=True)
# endregion

# region Carregamento de Dados com Busca Dinâmica Robusta
@st.cache_data
def load_data():
    caminho_arquivo = 'Plano de Manutenção 2º Trimestre - SP.xlsx'
    
    # 1. Busca Dinâmica: Encontra a linha do cabeçalho na aba Diário baseada em palavras-chave múltiplas
    df_temp = pd.read_excel(caminho_arquivo, sheet_name='Diário', header=None, nrows=25)
    header_idx_diario = 0
    
    for i, row in df_temp.iterrows():
        valores_linha = [str(val).lower() for val in row.tolist()]
        # Procura por uma linha que tenha pelo menos 3 colunas padrão do controle
        palavras_chave = ['semana', 'equipe', 'peso', 'meta', 'plano', 'data', 'quantidade']
        acertos = sum(1 for palavra in palavras_chave if any(palavra in val for val in valores_linha))
        
        if acertos >= 3:
            header_idx_diario = i
            break
            
    # Carrega a aba Diário a partir da linha correta encontrada
    df_diario = pd.read_excel(caminho_arquivo, sheet_name='Diário', header=header_idx_diario)
    
    # Limpeza de formatação dos cabeçalhos
    df_diario.columns = df_diario.columns.astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Mapeamento flexível de colunas
    mapeamento_diario = {
        'Origem Programação': ['origem programação', 'origem programacao', 'origem', 'origem_programacao', 'tipo de programação'],
        'Chave Peso': ['chave peso', 'chave_peso'],
        'Data Planejada': ['data planejada', 'data_planejada', 'data'],
        'Semana': ['semana', 'sem'],
        'Coordenação': ['coordenação', 'coordenacao', 'coord'],
        'Equipe': ['equipe', 'turma'],
        'Descrição Meta': ['descrição meta', 'descricao meta', 'descrição', 'meta', 'atividade'],
        'Peso Planejado Linha': ['peso planejado linha', 'peso planejado'],
        'Plano': ['plano'],
        'Peso Realizado Linha': ['peso realizado linha', 'peso realizado'],
        'QUANTIDADE REALIZADA': ['quantidade realizada', 'qtd realizada', 'realizado'],
        'Quantidade Programada': ['quantidade programada', 'qtd programada', 'programado']
    }
    
    for col_correta, variacoes in mapeamento_diario.items():
        for c in df_diario.columns:
            if c.lower() in variacoes:
                df_diario.rename(columns={c: col_correta}, inplace=True)
                break
                
    try:
        # Busca Dinâmica para a Planilha de Peso
        df_temp_peso = pd.read_excel(caminho_arquivo, sheet_name='Planilha de Peso', header=None, nrows=20)
        header_idx_peso = 0
        for i, row in df_temp_peso.iterrows():
            valores_linha = [str(val).lower() for val in row.tolist()]
            if any('chave' in val and 'peso' in val for val in valores_linha):
                header_idx_peso = i
                break
                
        df_peso = pd.read_excel(caminho_arquivo, sheet_name='Planilha de Peso', header=header_idx_peso)
        df_peso.columns = df_peso.columns.astype(str).str.strip()
        
        for c in df_peso.columns:
            if c.lower() in ['chave peso', 'chave_peso']: df_peso.rename(columns={c: 'Chave Peso'}, inplace=True)
            elif c.lower() in ['unidade', 'unid']: df_peso.rename(columns={c: 'Unidade'}, inplace=True)
            elif c.lower() == 'sla': df_peso.rename(columns={c: 'SLA'}, inplace=True)
            
        df = df_diario.merge(df_peso[['Chave Peso', 'Unidade', 'SLA']], on='Chave Peso', how='left')
    except Exception as e:
        df = df_diario
        if 'Unidade' not in df.columns: df['Unidade'] = '-'
        if 'SLA' not in df.columns: df['SLA'] = '-'
        
    if 'Data Planejada' in df.columns:
        df['Data Planejada'] = pd.to_datetime(df['Data Planejada'], errors='coerce')
    if 'Semana' in df.columns:
        df['Semana'] = pd.to_numeric(df['Semana'], errors='coerce').fillna(0).astype(int)
        
    return df

df = load_data()
# endregion

# ====== TRAVA DE SEGURANÇA E DEBUG ======
if 'Origem Programação' not in df.columns:
    st.error("🚨 A coluna 'Origem Programação' (ou similar) não foi encontrada com esse nome.")
    st.warning(f"**Por favor, olhe a lista de colunas abaixo que o Python achou e me diga qual é o nome correto da coluna de Origem na sua planilha:** \n\n `{list(df.columns)}`")
    st.stop()
# ========================================

# region Filtros do Dashboard (Sidebar c/ Form)
st.markdown("<h1 style='text-align: center; color: #1e293b; padding-bottom: 20px; font-weight: 800;'>🚂 Plano de Manutenção - Via Permanente</h1>", unsafe_allow_html=True)

dic_trimestres = {
    "1º Trimestre (Sem 1 a 13)": (1, 13), "2º Trimestre (Sem 14 a 26)": (14, 26),
    "3º Trimestre (Sem 27 a 39)": (27, 39), "4º Trimestre (Sem 40 a 52)": (40, 52)
}

with st.sidebar.form(key='form_filtros'):
    st.markdown("<h2 style='color: #1e293b; font-size: 1.2rem; margin-bottom: 15px;'>⚙️ Painel de Controle</h2>", unsafe_allow_html=True)
    trimestre_selecionado = st.selectbox("Selecione o Trimestre", list(dic_trimestres.keys()), index=1)
    
    coordenacoes_lista = list(df['Coordenação'].dropna().unique()) if 'Coordenação' in df.columns else []
    coord = st.selectbox("Visão / Coordenação", ['Gerência'] + coordenacoes_lista)
    
    equipes_disponiveis = df['Equipe'].dropna().unique() if 'Equipe' in df.columns else []
    equipes_selecionadas = st.multiselect("Equipes Específicas (Opcional)", equipes_disponiveis, default=[])
    
    itens_disponiveis = df['Descrição Meta'].dropna().unique() if 'Descrição Meta' in df.columns else []
    itens_selected = st.multiselect("Itens de Manutenção (Opcional)", itens_disponiveis, default=[])
    
    submit_filtros = st.form_submit_button(label='🚀 Aplicar Filtros')

sem_inicio, sem_fim = dic_trimestres[trimestre_selecionado]

df_coord_base = df.copy() if coord == 'Gerência' else df[df['Coordenação'] == coord].copy()
if equipes_selecionadas and 'Equipe' in df_coord_base.columns:
    df_coord_base = df_coord_base[df_coord_base['Equipe'].isin(equipes_selecionadas)]
if itens_selected and 'Descrição Meta' in df_coord_base.columns:
    df_coord_base = df_coord_base[df_coord_base['Descrição Meta'].isin(itens_selected)]
if 'Semana' in df_coord_base.columns:
    df_coord_base = df_coord_base[df_coord_base['Semana'] <= sem_fim]
# endregion

# region Processamento - Curva PCM e Realizada
if coord == 'Gerência':
    pcm_base = df_coord_base[df_coord_base['Origem Programação'] == 'PCM'].copy()
    meta_pcm_semanal = (pcm_base.groupby('Semana')['Peso Planejado Linha'].sum() / 3).cumsum()
else:
    pcm_base = df_coord_base[df_coord_base['Origem Programação'] == 'PCM'].copy()
    meta_pcm_semanal = pcm_base.groupby('Semana')['Peso Planejado Linha'].sum().cumsum()

filtro_exato = (df_coord_base['Plano'] == 'Sim') & (df_coord_base['Origem Programação'] == 'Coordenação')
realizado_sim = df_coord_base[filtro_exato].copy()

if coord == 'Gerência':
    real_semanal = (realizado_sim.groupby('Semana')['Peso Realizado Linha'].sum() / 3).reset_index()
else:
    real_semanal = realizado_sim.groupby('Semana')['Peso Realizado Linha'].sum().reset_index()

todas_semanas_acumulado = pd.DataFrame({'Semana': range(sem_inicio, sem_fim + 1)})
real_semanal = pd.merge(todas_semanas_acumulado, real_semanal, on='Semana', how='left').fillna(0)
real_semanal['Acumulado'] = real_semanal['Peso Realizado Linha'].cumsum()
# endregion

# region Lógica de Projeção & KPIs (Cards)
mask_preenchimento = (df_coord_base['Origem Programação'] == 'Coordenação') & (df_coord_base['Plano'] == 'Sim') & (df_coord_base['QUANTIDADE REALIZADA'] > 0)
ultima_data = df_coord_base[mask_preenchimento]['Data Planejada'].max()
str_ultima_data = ultima_data.strftime('%d/%m/%Y') if pd.notnull(ultima_data) else "Sem registros"

semana_atual_execucao = int(realizado_sim['Semana'].max()) if not realizado_sim.empty else sem_inicio
real_acum_atual = real_semanal.loc[real_semanal['Semana'] == semana_atual_execucao, 'Acumulado'].values[0] if semana_atual_execucao in real_semanal['Semana'].values else 0

semanas_executadas = (semana_atual_execucao - sem_inicio + 1)
ritmo_medio = real_acum_atual / semanas_executadas if semanas_executadas > 0 else 0

def get_valor(semana):
    if semana <= semana_atual_execucao:
        val = real_semanal.loc[real_semanal['Semana'] == semana, 'Acumulado']
        return round(val.values[0], 4) if not val.empty else 0
    else:
        return round(real_acum_atual + (ritmo_medio * (semana - semana_atual_execucao)), 4)

df_plot = pd.DataFrame({'Semana': list(range(sem_inicio, sem_fim + 1))})
df_plot['Valor'] = df_plot['Semana'].apply(get_valor)

aderencia_projetada = get_valor(sem_fim)
gap = 1 - aderencia_projetada
semanas_restantes = max(0, sem_fim - semana_atual_execucao)

classe_trend = "metric-card"
if aderencia_projetada == 0: txt_tendencia = "Sem Planejamento"
elif semanas_restantes <= 0: txt_tendencia = "Concluído: Atingida" if aderencia_projetada >= 1 else "Concluído: Não Atingida"
else:
    if aderencia_projetada >= 1: txt_tendencia, classe_trend = "Adiantado (Garantida)", classe_trend + " trend-adiantado"
    elif gap > 0.15: txt_tendencia, classe_trend = "Atraso Crítico (>15%)", classe_trend + " trend-critico"
    elif gap > 0.10: txt_tendencia, classe_trend = "Risco Alto (10-15%)", classe_trend + " trend-risco"
    elif gap > 0.05: txt_tendencia, classe_trend = "Em Risco (5-10%)", classe_trend + " trend-risco"
    else: txt_tendencia, classe_trend = "Leve Desvio (<5%)", classe_trend + " trend-leve"

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-title">📅 Último Preenchimento</div><div class="metric-value">{str_ultima_data}</div><div class="metric-sub">Semanas Executadas: <b>{semanas_executadas}</b></div></div>', unsafe_allow_html=True)
with col2:
    aderencia_percent = f"{round((real_acum_atual)*100, 1)}%" if real_acum_atual > 0 else "0%"
    st.markdown(f'<div class="metric-card" style="border-left-color: #0052cc;"><div class="metric-title">🚀 Aderência Atual</div><div class="metric-value">{aderencia_percent}</div><div class="metric-sub">Acumulado até a Semana {semana_atual_execucao}</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="{classe_trend}"><div class="metric-title">🎯 Projeção de Fechamento</div><div class="metric-value">{txt_tendencia}</div><div class="metric-sub">Alvo da Sem. {sem_fim}: <b>{round(aderencia_projetada*100, 1)}%</b></div></div>', unsafe_allow_html=True)
# endregion

# region Construção do Gráfico (ECharts)
x_data = [str(s) for s in df_plot['Semana'].tolist()]

real_data = [round(v * 100, 2) if s <= semana_atual_execucao else None for s, v in zip(df_plot['Semana'], df_plot['Valor'])]
proj_data = [round(v * 100, 2) if s >= semana_atual_execucao else None for s, v in zip(df_plot['Semana'], df_plot['Valor'])]

meta_data = []
for s in df_plot['Semana']:
    if s in meta_pcm_semanal.index:
        meta_data.append(round(meta_pcm_semanal[s] * 100, 2))
    else:
        meta_data.append(meta_data[-1] if meta_data else 0)

options = {
    "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
    "legend": {"data": ["Meta PCM", "Realizado", "Projeção (Ritmo)"], "top": 0},
    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
    "dataZoom": [
        {"type": "slider", "show": True, "xAxisIndex": [0], "bottom": 0, "start": 0, "end": 100},
        {"type": "inside", "xAxisIndex": [0], "zoomOnMouseWheel": True}
    ],
    "xAxis": {"type": "category", "boundaryGap": False, "data": x_data, "name": "Semana"},
    "yAxis": {"type": "value", "name": "Aderência", "axisLabel": {"formatter": "{value}%"}},
    "series": [
        {
            "name": "Meta PCM", "type": "line", "data": meta_data,
            "itemStyle": {"color": "#5470C6"}, "lineStyle": {"width": 3}, "smooth": True,
            "label": {
                "show": True, "position": "top", "formatter": "{c}%",
                "backgroundColor": "#5470C6", "color": "#FFFFFF", "fontWeight": "bold", "padding": [4, 6], "borderRadius": 4
            }
        },
        {
            "name": "Realizado", "type": "line", "data": real_data,
            "itemStyle": {"color": "#91CC75"}, "lineStyle": {"width": 4},
            "areaStyle": {"color": "rgba(145, 204, 117, 0.2)"}, "smooth": True,
            "label": {
                "show": True, "position": "bottom", "formatter": "{c}%",
                "backgroundColor": "#91CC75", "color": "#FFFFFF", "fontWeight": "bold", "padding": [4, 6], "borderRadius": 4
            }
        },
        {
            "name": "Projeção (Ritmo)", "type": "line", "data": proj_data,
            "itemStyle": {"color": "#FAC858"}, "lineStyle": {"width": 3, "type": "dashed"}, "smooth": True,
            "label": {
                "show": True, "position": "top", "formatter": "{c}%",
                "backgroundColor": "#FAC858", "color": "#000000", "fontWeight": "bold", "padding": [4, 6], "borderRadius": 4
            }
        }
    ]
}

st_echarts(options=options, height="500px")
# endregion

# region Tabela Resumo Abaixo do Gráfico
st.markdown("<h3 style='color: #1e293b; margin-top: 30px; font-weight: 700;'>📋 Resumo por Atividade do Período</h3>", unsafe_allow_html=True)

df_pcm_tabela = df_coord_base[df_coord_base['Origem Programação'] == 'PCM']
resumo_pcm = df_pcm_tabela.groupby('Descrição Meta').agg({'Quantidade Programada': 'sum', 'Peso Planejado Linha': 'sum'}).reset_index().rename(columns={'Quantidade Programada': 'Plano', 'Peso Planejado Linha': 'Peso no Plano'})

df_real_tabela = df_coord_base[(df_coord_base['Origem Programação'] == 'Coordenação') & (df_coord_base['Plano'] == 'Sim')]
resumo_real = df_real_tabela.groupby('Descrição Meta').agg({'QUANTIDADE REALIZADA': 'sum', 'Data Planejada': 'nunique', 'Peso Realizado Linha': 'sum', 'Unidade': 'first', 'SLA': 'first'}).reset_index().rename(columns={'QUANTIDADE REALIZADA': 'Qtd. Realizado', 'Data Planejada': 'Dias de Equipe', 'Peso Realizado Linha': 'Aderência'})

df_extra_tabela = df_coord_base[(df_coord_base['Origem Programação'] == 'Coordenação') & (df_coord_base['Plano'] == 'Não')]
resumo_extra = df_extra_tabela.groupby('Descrição Meta').agg({'QUANTIDADE REALIZADA': 'sum'}).reset_index().rename(columns={'QUANTIDADE REALIZADA': 'Realizado (Extra Plano)'})

tabela_final = pd.merge(resumo_pcm, resumo_real, on='Descrição Meta', how='outer').fillna(0)
tabela_final = pd.merge(tabela_final, resumo_extra, on='Descrição Meta', how='outer').fillna(0)

tabela_final['Pendente'] = (tabela_final['Plano'] - tabela_final['Qtd. Realizado']).apply(lambda x: max(0, x))
tabela_final['% Realizado'] = (tabela_final['Qtd. Realizado'] / tabela_final['Plano'].replace(0, 1)).astype(float)

colunas_existentes = [col for col in ['Descrição Meta', 'Plano', 'Unidade', 'SLA', 'Dias de Equipe', 'Qtd. Realizado', 'Realizado (Extra Plano)', 'Pendente', '% Realizado', 'Peso no Plano', 'Aderência'] if col in tabela_final.columns]
st.dataframe(tabela_final[colunas_existentes].style.format({'% Realizado': '{:.1%}', 'Peso no Plano': '{:.2%}', 'Aderência': '{:.2%}', 'Plano': '{:,.1f}', 'Qtd. Realizado': '{:,.1f}', 'Realizado (Extra Plano)': '{:,.1f}', 'Pendente': '{:,.1f}'}).background_gradient(subset=['% Realizado'], cmap='Blues', vmin=0, vmax=1), use_container_width=True, hide_index=True)
# endregion