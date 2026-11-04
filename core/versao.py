# core/versao.py — Versão única do Plano VP (SemVer: MAJOR.MINOR.PATCH)
#
# Fonte única da versão (tela de login, menu lateral, "Sobre"). Mesmo critério
# do MRS Sentinel / Gestão_OS — todo commit que muda comportamento sobe a versão:
#   PATCH: correção pontual sem mudar comportamento/fluxo (bugfix, texto, cor).
#   MINOR: funcionalidade nova compatível (filtro, coluna, opção nova).
#   MAJOR: tela/aba nova, reorganização de fluxo, correção de segurança ou de
#          integridade de dado, mudança de schema de banco.
#   Commit que mistura tipos sobe pelo nível MAIS ALTO presente.
# Sem chamadas st.* aqui (é importado antes do set_page_config).
#
# HISTÓRICO
# 1.0.0 (jun/2026): dashboard único (app_v1_backup.py) lendo a planilha do
#   2º tri — curva Meta PCM x Realizado x Projeção.
# 2.0.0 (11/09/2026): modular (core/), replicável por trimestre via
#   parametros.xlsx, curva OPEX top-down (envelope da PLAN ORÇ).
# 2.1.0 (03/11/2026): modelo de planilha v3 sem fórmulas (Pesos / Plano_PCM /
#   Lancamentos / Listas); Python calcula semana (WEEKNUM), coordenação e pesos;
#   conversor da planilha antiga.
# 2.2.0 (03/11/2026): importador dos exports do PCM (pesos = Peso Item Redist;
#   Planejamento congelado = curva planejada); 4º tri = semanas 40-53.
# 3.0.0 (03/11/2026): aplicação completa no padrão do Sentinel — login próprio
#   (PBKDF2) com perfis admin/pcm/programador/leitor, banco de dados (SQLite
#   local ou PostgreSQL/Neon) com histórico de trimestres, telas Dashboard
#   (Resumo, Gerencial, Por Coordenação, Financeiro, Evolução), Lançamentos
#   (edição linha a linha), Dados (upload do PCM / histórico e exportação em
#   Excel no modelo v3) e Configurações (SLA por Depto, equipes, listas,
#   coordenações, trimestres, parâmetros, usuários, auditoria). SLA vira
#   "Dias de equipe p/ concluir" (Pendente ÷ SLA). Documentação em docs/.
# 3.0.1 (03/11/2026): URL do banco aceita postgresql://, postgres:// e
#   postgresql+psycopg:// (convertidas para psycopg2) — corrige "No module named
#   'psycopg'" no Streamlit Cloud.
# 3.0.2 (03/11/2026): requirements.txt com versões fixas (as testadas) — o Cloud
#   tinha instalado Streamlit 1.66.1 / pandas 3.1.0, não testados.
# 3.0.3 (03/11/2026): Streamlit fixado em 1.56.0 (último com servidor Tornado).
#   No Streamlit Cloud o servidor uvicorn (1.57+) perdia ~20% das requisições
#   ("Failed to fetch dynamically imported module ... TextInput.js"); outro app
#   com Tornado respondeu 100% no mesmo teste.
# 3.1.0 (03/11/2026): deploy no Hugging Face Spaces (Dockerfile + workflow
#   sync-hf.yml que envia a main para o Space a cada push). Motivo: apps da conta
#   no Streamlit Cloud perdiam ~15% das requisições (Sentinel também); Render
#   gratuito descartado (750 h/mês já tomadas pela API do Gestão_OS).
# 3.1.1 (03/11/2026): Hugging Face exige PRO em conta nova (cota cpu-basic = 0);
#   hospedagem volta a ser o Streamlit Cloud. Workflow OIDC mantido para o PRO.

APP_VERSION = "3.1.1"
APP_NOME = "Plano VP"
