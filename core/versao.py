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
# 3.1.2 (04/11/2026): desempenho — versão dos dados em cache de 10 s e usuário
#   logado em cache de 60 s; navegação passa de 8–26 consultas por clique (1–7 s,
#   app nos EUA x Neon em SP) para 0; troca de senha limpa o cache do usuário.
# 3.2.0 (04/11/2026): histórico direto dos exports do Power BI do PCM — o upload
#   "Planilha de trimestre" aceita vários arquivos: Planejado (1..N trimestres),
#   Realizado (ordens SAP: Qtd. Real, Considera Plano?, Motivo de Perda) e o export
#   de pesos (Peso Item Inicial, fixo por meta — reproduz os pesos do 1º e 3º tri,
#   76/76). Leitor da planilha antiga usa só dados digitados (lê a do 1º tri).
# 4.0.0 (04/11/2026): aderência = regra oficial do PCM ("Adr_Ativo" do Power BI),
#   conferida nos 4 trimestres de 2026 (11/12 coordenações a até 0,4 p.p.):
#   - realizado de cada meta com TETO no plano (fazer 132 de 40 conta 40);
#   - Realizado do PCM: conta para o plano "Considera Plano? = Sim" OU ordem
#     Encerrada; atribuído ao Depto do ATIVO (inclui a GOEV — socaria mecanizada);
#   - grupos Saneamento Vegetal e Drenagem fora da aderência da Via (configurável).
#   Também: datas em texto ISO (2026-10-05) eram lidas como dia/mês.
# 4.1.0 (04/11/2026): visão por material na regra do PCM (Aderência PCM com teto,
#   Peso na Visão, Contribuição — Σ Contribuição = aderência da visão);
#   scripts/conferir_pcm.py (app x Power BI); docs/REGRA_ADERENCIA_PCM.md e
#   docs/HISTORICO_PROJETO.md guardam a regra, as evidências e as decisões.
# 4.1.1 (04/11/2026): investigação da Gerência registrada (não é média; 12 fórmulas
#   testadas, nenhuma bate) e aviso no Resumo de que a Gerência é estimativa.
# 4.2.0 (04/11/2026): Gerência pela regra do PCM (export consolidado data (10),
#   19/19 metas): meta pesa Σ Peso Redist das coordenações; metas "Tipo de medição
#   = DEPTO" somam o volume de todas as coordenações (com teto no plano somado),
#   ATIVO somam o realizado limitado de cada uma; ÷ nº de coordenações. Tipo de
#   medição lido do export de pesos (config metas_medicao_depto). Conferência:
#   Gerência 1º–3º tri a ≤0,5 p.p. do Power BI.
# 4.2.1 (04/11/2026): aviso no Resumo de que pode haver pequena variação (até ~0,5 p.p.)
#   em relação ao Power BI; decisão registrada (variação <1 p.p. aceita).
# 5.0.0 (04/11/2026): proteção dos lançamentos. Corrige DataError no Neon ao subir o
#   Realizado (Motivo de Perda > 80 caracteres): justificativa vira TEXT e todo texto
#   maior que a coluna é cortado antes de gravar. Schema: lancamentos.origem
#   (upload|app) e tabela lancamentos_copia — migração automática (schema._migrar).
#   Upload bloqueado em trimestre fechado (exceto admin); confirmação quando o upload
#   apagar lançamentos digitados no app; cópia automática antes de substituir, excluir
#   ou restaurar, com restauração em Configurações → Trimestres (admin).
# 5.1.0 (06/11/2026): Dashboard abre no trimestre corrente, pela data de hoje (antes: o
#   último da lista, ou o último importado), com aviso e botão de volta ao ver outro
#   trimestre. Lista de ativos por upload (Dados → Upload): lista suspensa da coluna
#   Ativo em Lançamentos, por Depto quando o arquivo traz a coluna.
# 5.2.0 (10/11/2026): Upload "Realizado do trimestre (export do Power BI)": troca os
#   lançamentos só dos Deptos escolhidos (padrão: os sem lançamento digitado no app).
#   Gráfico Gerencial das coordenações com filtro de coordenações e de linhas.
# 5.3.0 (10/11/2026): valor da aderência escrito em cada ponto das curvas (Gerência e
#   coordenações) e na base de cada barra da Evolução (tabelas removidas); eixos e
#   tooltips com % correto (o "%" do Vega saía com 6 casas e cortava o eixo: "0%").
#   Financeiro com seleção das linhas do gráfico.

APP_VERSION = "5.3.0"
APP_NOME = "Plano VP"
