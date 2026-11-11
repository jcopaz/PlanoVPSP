# Plano VP — Documentação técnica

Para quem vai **manter, publicar ou evoluir** o app (pessoa ou agente de IA). Atualizada em
**11/11/2026, versão 5.3.3**.

| Documento | Para quê |
|---|---|
| este | como o app funciona por dentro e como mantê-lo |
| [REGRA_ADERENCIA_PCM.md](REGRA_ADERENCIA_PCM.md) | **fonte da verdade do cálculo** (regra do Power BI do PCM, evidências, como reconferir) — ler antes de mexer em `core/fisico.py` |
| [HISTORICO_PROJETO.md](HISTORICO_PROJETO.md) | linha do tempo, decisões, investigações descartadas e lições |
| [PUBLICACAO.md](PUBLICACAO.md) | passo a passo Neon + Streamlit Cloud |
| [MANUAL_USUARIO.md](MANUAL_USUARIO.md) | uso do dia a dia (programador, PCM, admin) |
| [`core/versao.py`](../core/versao.py) | versão atual e histórico de cada mudança |

**Sumário:**
1. Visão geral
2. Stack e hospedagem
3. Estrutura do código
4. Banco de dados
5. Regras de cálculo
6. Telas
7. Fluxos de dados (uploads)
8. Operação (deploy, keep-alive, scripts, backup)
9. Segurança
10. Padrões de interface (formatação e gráficos)
11. Como evoluir (convenções e validação)
12. Armadilhas conhecidas
13. Decisões registradas
14. Pendências

---

## 1. Visão geral

O plano de manutenção da Via Permanente é definido pelo **PCM** a cada trimestre. Cada Depto
(Centro de Trabalho, ex.: `V.SP.IPA`) tem um conjunto de **metas** (Descrição Meta) com **peso** e
**quantidade planejada**, distribuídas por dia na "visão congelada" (Planejamento PCM). O realizado
chega por dois caminhos: digitado pelos **programadores** na tela de Lançamentos ou importado do
**export Realizado do Power BI** (ordens do SAP). O app compara **planejado × realizado** semana a
semana, por **coordenação** e **Gerência**, com o mesmo número do painel do PCM ("Adr_Ativo").

```
 PCM / Power BI                                    Programadores
 ├─ export de pesos  (data (N).xlsx) ──┐           │ digitam a execução
 ├─ Planejamento PCM (visão congelada) ┤           ▼
 ├─ Planejado 1..N tri (histórico) ────┤     ┌────────────────┐    ┌──────────────────────┐
 └─ Realizado (ordens SAP) ────────────┼───► │  BANCO          │──► │ core/motor + fisico  │──► Dashboard
   Relação de ativos (Excel) ──────────┘     │ Neon (produção) │    │ curvas, KPIs, regra  │    (5 abas)
   Planilha de trimestre / backup ──────────►│ SQLite (local)  │    │ PCM, OPEX            │
                                             └────────────────┘    └──────────────────────┘
                                                     │
                                  Dados → Exportação (Excel modelo v3 / backup .zip)
```

## 2. Stack e hospedagem

| Peça | Versão / onde | Observação |
|---|---|---|
| Python | 3.12 | o mesmo no Streamlit Cloud e local (`.venv`) |
| Streamlit | **1.56.0 (fixo)** | último com servidor Tornado; ver §12 |
| pandas / altair / openpyxl | 3.0.6 / 6.3.0 / 3.1.5 | versões fixas em `requirements.txt` (as testadas) |
| SQLAlchemy + psycopg2 | 2.1.6 / 2.9.13 | Core (sem ORM); mesmo código em SQLite e PostgreSQL |
| matplotlib | 3.11.2 | só para `Styler.background_gradient` |
| Hospedagem | **Streamlit Community Cloud** — `https://planovpsp.streamlit.app` | deploy automático a cada `git push` na `main` do repositório **público** `jcopaz/PlanoVPSP` |
| Banco | **Neon** PostgreSQL (São Paulo, plano Free) | URL só nos Secrets do Streamlit Cloud |
| Keep-alive | GitHub Actions `keep-alive.yml` a cada 6 h | §8.2 |
| Hugging Face Spaces | **inativo** | Dockerfile + `sync-hf.yml` prontos; exige plano PRO (§13) |

Tema e servidor em [`.streamlit/config.toml`](../.streamlit/config.toml) (`useStarlette = false`,
tema claro, `gatherUsageStats = false`).

## 3. Estrutura do código

Mesmo padrão do MRS Sentinel. **Regra de ouro:** telas não montam SQL e `core/` não usa Streamlit
(exceto `ui.py`) — o cálculo roda em script e em teste sem abrir o app.

| Camada | Pasta | Regra |
|---|---|---|
| Entrada | `app.py` | configura a página, valida o usuário e roteia: 1º admin → login → troca de senha → menu + tela |
| Acesso | `auth/` | sessão, senha, perfis, telas de login |
| Dados | `database/` | conexão, tabelas, **todo** SQL |
| Negócio | `core/` | cálculo, leitura/escrita de Excel, importação do PCM, gráficos |
| Telas | `modules/` | uma tela por arquivo; chamam `core/` e `database/queries.py` |
| Operação | `scripts/` | linha de comando: usuário, carga em lote, conferência com o PCM, keep-alive |
| Testes | `tests/` | regra do PCM e lista de ativos (`python tests/test_regra_pcm.py`) |

### 3.1 Arquivo por arquivo

**Raiz**

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | `set_page_config`, CSS, `ROTAS` (dashboard, lancamentos, dados, configuracoes). Usuário relido do banco no máximo 1×/min (`_usuario_do_banco`, cache 60 s): conta desativada sai sozinha |
| `requirements.txt` | versões fixas |
| `Dockerfile`, `deploy/hf/` | só para o Hugging Face (inativo) |
| `parametros.xlsx` | semeia a config na 1ª execução (depois tudo vem do banco) |
| `Abrir_Dashboard.bat` | atalho local no Windows |

**`auth/`**

| Arquivo | Responsabilidade |
|---|---|
| `session.py` | leitura/escrita de `st.session_state` (usuario, pagina, trimestre_id) |
| `senha.py` | PBKDF2-SHA256 600 mil iterações, sal 16 bytes, mínimo 8 caracteres com letra e número, `senha_provisoria()` |
| `permissions.py` | perfis e funções `pode_*`; `require()` interrompe a tela; `deptos_permitidos()` |
| `login.py` | telas de login, criação do 1º administrador e troca obrigatória de senha |

**`database/`**

| Arquivo | Responsabilidade |
|---|---|
| `client.py` | URL (Secrets → `PLANO_DB_URL` → `sqlite:///dados/plano.db`), normaliza `postgres://` e `postgresql+psycopg://` para psycopg2, `get_engine()` único por processo (cria tabelas, migra e semeia), `descricao_banco()` |
| `schema.py` | tabelas, `MAPA_*` (coluna do banco ↔ cabeçalho da planilha), `criar_tabelas` + `_migrar` |
| `queries.py` | todas as leituras/gravações. Cada gravação: transação + `auditoria` + `_bump` (versão dos dados) |

**`core/`**

| Arquivo | Responsabilidade |
|---|---|
| `modelo.py` | layout do modelo de planilha v3 (abas, colunas, listas, validações) — fonte única |
| `dados.py` | `para_data` (aceita ISO e dd/mm), `semana_excel` (WEEKNUM), `montar_canonico` (Pesos+Plano+Lançamentos → base canônica com semana, coordenação e pesos), leitura da planilha antiga |
| `fisico.py` | curvas Meta PCM / Realizado / Projeção, KPIs, teto por meta, regra da Gerência, tabela de atividades |
| `financeiro.py` | curva OPEX top-down a partir do `Orçamento Ger. SP.xlsx` |
| `motor.py` | ponte banco → cálculo: `parametros`, `calcular_trimestre` (Gerência + coordenações), quadro-resumo, histórico trimestral e anual |
| `importar_pcm.py` | exports do PCM: trimestre do rodapé, pesos, Planejamento, Planejado, Realizado (atribuição pelo ativo, GOEV), tipo de medição DEPTO/ATIVO, `montar_historico` |
| `planilha.py` | identifica o tipo do Excel enviado, lê (v3, antiga), escreve (modelo v3 com menus), `lista_de_ativos` |
| `config.py` | `Parametros` e valores padrão |
| `graficos.py` | gráficos Altair: curvas, coordenações, evolução, financeiro; rótulos pt-BR (§10) |
| `ui.py` | CSS, `titulo`, `card`, `pct` (2 casas, vírgula), `reais` |
| `versao.py` | `APP_VERSION` e histórico |

**`modules/`**

| Arquivo | Tela |
|---|---|
| `home.py` | menu lateral: seletor de trimestre, botões, Sair, versão centralizada; alerta se o banco for o SQLite temporário |
| `comum.py` | cache por versão dos dados, `trimestre_corrente` / `trimestre_ativo`, `voltar_ao_corrente`, cadastros, `salvar_temporario` |
| `dashboard.py` | Resumo, Gerencial, Por Coordenação, Financeiro, Evolução |
| `lancamentos.py` | grade editável linha a linha (validação, diff, gravação) |
| `dados.py` | Upload (4 tipos) e Exportação (Excel do trimestre, backup .zip) |
| `configuracoes.py` | SLA e Unidades, Equipes, Listas, Coordenações, Trimestres (inclui restaurar cópia), Parâmetros, Usuários, Auditoria |

## 4. Banco de dados

Definido em [`database/schema.py`](../database/schema.py). Roda igual em SQLite e PostgreSQL/Neon.

| Tabela | Conteúdo | Chave / índice |
|---|---|---|
| `trimestres` | ano, trimestre, semana_inicio/fim, status (aberto/fechado), observação | único (ano, trimestre) |
| `pesos` | peso de cada meta por Depto no trimestre | único (trimestre_id, depto, meta) |
| `plano` | visão congelada do PCM: 1 linha por dia/meta/equipe | índice trimestre_id |
| `lancamentos` | execução: quantidades, No Plano, justificativa (TEXT), status, programador, `origem` (`upload`/`app`), criado_por/alterado_por | índice trimestre_id |
| `lancamentos_copia` | cópia (JSON) dos lançamentos de um trimestre antes de upload, exclusão ou restauração; sem FK, sobrevive à exclusão do trimestre; 10 mais recentes por trimestre | id |
| `metas_catalogo` | **Unidade e SLA** por Depto × Meta (vale para todos os trimestres) | único (depto, meta) |
| `listas` | menus: `Equipe`, `Ativo`, `Justificativa`, `Status`, `Tipo Material`, `Grupo`; `depto = ""` vale para todos | único (tipo, valor, depto) |
| `coordenacoes` | Depto → Coordenação → Centro de Custo; entra na Gerência | depto |
| `config` | parâmetros chave/valor (faixas, rótulo da Gerência, grupos fora, metas DEPTO, orçamento, `env.*`, `_versao_dados`) | chave |
| `usuarios` | login (matrícula), nome, e-mail, hash, perfil, Depto delegado, ativo, `deve_trocar_senha` | único login |
| `auditoria` | quem fez o quê: login, uploads, edições, configurações, restaurações | id |

**Conexão** — primeira que existir: `st.secrets["database"]["url"]` → variável `PLANO_DB_URL` →
`sqlite:///dados/plano.db`. Na rede MRS, conexão direta ao Neon exige `sslnegotiation=direct` na URL
(o firewall derruba o SSLRequest padrão); no Streamlit Cloud, não.

**Criação e migração** — `get_engine()` roda `create_all` (tabela nova nasce sozinha) e
`schema._migrar` (idempotente), que guarda os ajustes em tabelas existentes. Hoje: adiciona
`lancamentos.origem` e muda `justificativa` de VARCHAR(80) para TEXT no PostgreSQL. Coluna nova ou
tipo alterado → acrescentar em `_migrar` e subir **MAJOR**.

**Tamanho de texto** — o PostgreSQL recusa texto maior que a coluna (`DataError`); o SQLite aceita
sem avisar. `queries._cabe` corta campos `String(n)` antes de todo insert/update de pesos, plano,
lançamentos e listas.

**Cache por versão dos dados** — toda gravação incrementa `config._versao_dados` (`_bump`). As
leituras das telas (`modules/comum.py`) usam `st.cache_data` com essa versão na chave; a própria
versão fica em cache 10 s. Resultado: navegar não consulta o banco (o app nos EUA fala com o Neon em
São Paulo a ~0,15 s por consulta). Quem grava chama `comum.limpar_cache()` e vê na hora; os demais
usuários, em até 10 s. Também protege a cota de tráfego do Neon.

## 5. Regras de cálculo

Detalhes, evidências e variantes descartadas: [REGRA_ADERENCIA_PCM.md](REGRA_ADERENCIA_PCM.md).

**Semana** = `WEEKNUM` do Excel (domingo inicia; 1º/jan = semana 1). Existe **semana 53**
(27–31/12/2026). A janela do trimestre vem do calendário (`queries.janela_semanas`: 4º tri/2026 =
40–53) e pode ser ajustada em Configurações → Trimestres.

**Pesos** (`dados.montar_canonico`):
```
Plano Trimestral (Depto, Meta) = Σ Quantidade Programada do plano congelado
Peso Item       = Peso / Σ Peso do Depto (só metas com plano > 0; grupos fora da aderência = 0)
Peso Unitário   = Peso Item / Plano Trimestral
Peso Planejado Linha = Qtd Programada × Peso Unitário
Peso Realizado Linha = Qtd Realizada  × Peso Unitário   (No Plano = Sim)
```
Peso = **Peso Item Inicial** do export do PCM, fixo por meta (o PCM só redistribui entre as metas
com plano; 76/76 conferidos).

**Coordenação (regra "Adr_Ativo" do PCM)**:
```
Aderência = Σ_meta Peso Item × min(Realizado, Plano Trimestral) / Plano Trimestral
```
- **Teto por meta** (`fisico._peso_realizado_limitado`, acumulado semana a semana).
- **Realizado do PCM** (`importar_pcm.ler_realizado`): conta se "Considera Plano? = Sim" **ou** ordem
  "Encerrada"; atribuído pela **Gerência + Centro de trabalho Ativo** (onde fica o ativo), inclusive
  execução da **GOEV**. "Motivo de Perda" vira Justificativa quando real < programado.
- **Grupos fora** (config `grupos_fora_aderencia`, padrão "Saneamento Vegetal;Drenagem"): peso zero.

**Gerência** (regra própria do PCM, não é média das coordenações):
```
Gerência = Σ_meta [Σ_coord Peso Item] × Realizado_Ger / Σ_coord Plano   ÷  nº de coordenações
  metas DEPTO: Realizado_Ger = min(Σ volume de TODAS as coordenações, Σ plano)  (sobra cobre falta)
  metas ATIVO: Realizado_Ger = Σ realizado já limitado em cada coordenação
```
A lista de metas DEPTO (config `metas_medicao_depto`) é gravada sozinha ao importar o export de
pesos (`tipos_de_medicao` / `atualizar_metas_depto`) e editável em Configurações → Parâmetros.
Conferência: coordenações 11/12 dentro de 0,5 p.p. do Power BI; Gerência 1º–3º tri a ≤ 0,5 p.p.
Variação de até ~1 p.p. foi aceita e é avisada no Resumo.

**Curvas** (`fisico.calcular`), acumuladas por semana:
- Meta PCM = Σ Peso Planejado ÷ divisor (1 na coordenação; nº de coordenações na Gerência);
- Realizado = Σ Peso Realizado com teto ÷ divisor;
- Projeção = realizado na semana atual + ritmo médio × semanas restantes. **Semana atual** = última
  semana com lançamento "Sim" dentro da janela.

**Tendência** = meta (padrão 100%) − projeção de fechamento, nas faixas configuráveis (leve 5%,
risco 10%, alto 15%). Sem lançamento: "Aguardando Lançamentos".

**Dias de equipe p/ concluir** = ⌈Pendente ÷ SLA⌉; SLA = produção esperada da equipe por dia
(`metas_catalogo`).

**Ano** (Evolução) = média simples das aderências trimestrais carregadas (premissa não validada com o
PCM). O trimestre em andamento entra com a aderência acumulada até a última semana lançada.

**OPEX** (`financeiro.py`): envelope = aba `PLAN ORÇ` do `Orçamento Ger. SP.xlsx` (pacotes e centros
de custo configurados) × curva física; rateio por item conforme o peso. Precisa do arquivo na pasta
do app (§12, risco de dado público).

## 6. Telas

**Menu lateral** (`home.py`): seletor de trimestre (🔒 = fechado), navegação, Sair, versão
centralizada. Alerta amarelo só se o banco for o SQLite temporário.

**Trimestre exibido** — ao entrar, `comum.trimestre_ativo` usa `trimestre_corrente` (o da data de
hoje; se ele não existir, o mais recente já iniciado, com aviso). Upload não troca o trimestre
exibido. Ao escolher outro no menu, o Dashboard mostra aviso e o botão "↩️ Trimestre corrente"
(`on_click=comum.voltar_ao_corrente`, que também limpa o seletor `sb_trimestre`).

**Abas com estado** — Dashboard, Dados e Configurações usam `st.tabs(..., key=..., on_change="rerun")`
e só executam a aba aberta (`tab.open`). Sem isso, um "Salvar" que recarrega a página voltava para a
primeira aba.

| Tela | Conteúdo |
|---|---|
| **Dashboard → Resumo** | cartões da Gerência (aderência do trimestre, projeção, mínimo semanal, último lançamento), cartão por coordenação, quadro-resumo, atividades que mais pesam no que falta |
| **Dashboard → Gerencial** | curva da Gerência com valor em cada ponto; curvas das coordenações com filtros de coordenação e de linhas (Realizado / Meta PCM); quadro e atividades |
| **Dashboard → Por Coordenação** | curva e atividades da coordenação (filtro por equipe e atividade), SLA, dias de equipe, motivos |
| **Dashboard → Financeiro** | cartões em R$, curva OPEX com seleção de linhas e rótulos em R$, tabela "OPEX rateado por item" |
| **Dashboard → Evolução** | barras por trimestre e média do ano, com o percentual na base de cada barra (sem tabelas) |
| **Lançamentos** | grade por Depto e semanas; "Trazer estas linhas do plano"; Ativo vira lista suspensa quando há relação de ativos; ao salvar, valida só linhas novas/alteradas, calcula o diff e grava numa transação |
| **Dados → Upload** | 4 tipos (§7); só admin e PCM |
| **Dados → Exportação** | Excel do trimestre no modelo v3 (reimportável) e backup .zip (todos os trimestres + cadastros) |
| **Configurações** | SLA e Unidades, Equipes (por Depto), Listas (inclui Ativo), Coordenações, Trimestres (janela, status, excluir, ♻️ restaurar cópia), Parâmetros, Usuários, Auditoria |

**Validação dos lançamentos** (`lancamentos._validar`): bloqueia data vazia, Depto fora do escopo do
usuário, data fora do trimestre, "No Plano" diferente de Sim/Não e quantidade negativa; avisa (sem
bloquear) meta sem peso no Depto e realizado abaixo do programado sem Justificativa. Trimestre
fechado: somente leitura, exceto para o administrador.

## 7. Fluxos de dados (uploads)

Todos em **Dados → Upload** (admin e PCM). Regra comum: **reenviar substitui, não duplica**.

| Tipo | Entrada | Efeito |
|---|---|---|
| **Plano do trimestre** | export de pesos + Planejamento PCM | trimestre lido do rodapé (`Tri/Ano é Tri 4/26`; a célula Tri/Ano guarda o trimestre no mês) → `substituir_plano` (pesos + plano; **lançamentos intactos**) → `completar_catalogo` (metas novas sem SLA) → `adicionar_equipes` → metas DEPTO na config |
| **Realizado do trimestre** | export Realizado do Power BI | `montar_historico` só com o Realizado → tabela por Depto (no export, "Sim", hoje no sistema, digitados no app) → `substituir_lancamentos(..., deptos=[...])` troca **só os Deptos marcados**. Padrão: Deptos sem lançamento digitado no app, para a mesma ordem não contar duas vezes |
| **Planilha de trimestre** | modelo v3, backup, planilha antiga ou exports Planejado + Realizado + pesos (vários arquivos juntos) | prévia por trimestre + escolha dos trimestres; substitui plano (se veio) e **todos** os lançamentos dos trimestres escolhidos. Realizado de trimestre sem plano é ignorado; ordem sem meta vira `(SEM META)` ou fica de fora |
| **Lista de ativos** | Excel com a relação | coluna do ativo e, opcional, do Depto/Coordenação (sugeridas pelo nome) → `planilha.lista_de_ativos` → `salvar_listas("Ativo")` substitui a lista inteira; Depto desconhecido vale para todos (com aviso) |

**Proteções** (v5.0.0):
- **Trimestre fechado** não aceita upload, exceto o administrador (`dados._fechado`, checado na tela e
  em `_gravar`).
- **Confirmação obrigatória** quando o upload vai apagar lançamentos digitados no app (`origem =
  'app'` ou com `alterado_por`).
- **Cópia automática**: `substituir_lancamentos`, `excluir_trimestre` e `restaurar_copia` gravam, na
  mesma transação, o estado atual em `lancamentos_copia`. Restaurar: Configurações → Trimestres → ♻️
  (admin); o estado atual vira nova cópia, então a restauração pode ser desfeita.
- **Erro no meio**: cada substituição é uma transação; num upload de vários trimestres, os anteriores
  ao erro ficam gravados — a tela orienta reenviar (`dados._executar`).
- **Sem cópia**: edição/exclusão linha a linha em Lançamentos (fica na auditoria) e plano/pesos
  (reimportáveis do PCM).

## 8. Operação

### 8.1 Deploy
`git push` na `main` → o Streamlit Cloud reinstala em 1–2 min. Secrets em App → ⋮ → Settings →
Secrets (`[database] url = "postgresql+psycopg2://…?sslmode=require"`). Detalhes:
[PUBLICACAO.md](PUBLICACAO.md). **Nunca** colocar a URL do banco no código, em commit ou no chat.

### 8.2 Keep-alive (app sempre acordado)
O Streamlit Cloud põe o app para dormir após ~12 h sem visitas, e só conta visita de **navegador de
verdade** (sessão websocket): um `curl` não basta.

- Workflow [`.github/workflows/keep-alive.yml`](../.github/workflows/keep-alive.yml): a cada 6 h
  (`17 */6 * * *`, UTC) e manual (Actions → Keep alive → Run workflow).
- Script [`scripts/keep_alive.py`](../scripts/keep_alive.py): abre o app num Chromium sem tela
  (Playwright 1.55.0); se estiver dormindo, clica em "Yes, get this app back up!"; espera até 4 min
  pelo texto "PLANO VP" da tela de login em qualquer frame. Se não carregar, o job falha e o GitHub
  avisa por e-mail.
- Testado em 11/11/2026 contra o app real: acordou o app que estava dormindo; com o app acordado,
  levou 17 s.
- Outra URL: variável `APP_URL` em Settings → Secrets and variables → Actions → Variables.
- ⚠️ O GitHub **desliga agendamentos** de repositório sem commit há 60 dias (avisa por e-mail).
  Religar em Actions → Keep alive → *Enable workflow*.
- Custo zero: repositório público tem minutos de Actions ilimitados; o Streamlit Cloud não cobra
  horas. Rodar localmente:
  `pip install playwright==1.55.0 && python -m playwright install chromium && python scripts/keep_alive.py`.

### 8.3 Scripts (`scripts/`)

| Script | Uso |
|---|---|
| `criar_usuario.py` | criar usuário ou resetar senha direto no banco (`LOGIN --resetar`); recupera o admin |
| `carregar_no_banco.py` | carga em lote de planilhas de trimestre ou do plano do PCM |
| `conferir_pcm.py` | **obrigatório ao mexer no cálculo**: app × Power BI com CSV de referência; sai com erro se divergir > 0,5 p.p. |
| `importar_plano_pcm.py` | gera a planilha v3 do trimestre a partir dos exports do PCM |
| `converter_planilha_antiga.py` | planilha antiga (Diário + Planilha de Peso) → modelo v3 |
| `gerar_modelo.py` | `modelos/Modelo_…` (em branco) e `Exemplo_…` (dados fictícios) |
| `gerar_parametros.py` | `parametros.xlsx` padrão |
| `keep_alive.py` | §8.2 |

Para apontar um script ao Neon a partir da rede MRS, defina `PLANO_DB_URL` (com
`sslnegotiation=direct`) só na sessão do terminal e apague depois — ver [PUBLICACAO.md](PUBLICACAO.md).

### 8.4 Rotina
| Quando | O quê |
|---|---|
| Início do trimestre | Upload → Plano do trimestre; conferir SLA das metas novas |
| Semanal | programadores lançam; ou PCM sobe o Realizado do Power BI dos Deptos que não lançam |
| Fim do trimestre | conferir com o Power BI (`conferir_pcm.py`); status **fechado**; **backup .zip** |
| Mensal | Neon → Usage (storage e network transfer) |

## 9. Segurança

- Senhas PBKDF2-SHA256 (600 mil iterações, sal aleatório); nunca em texto. Conta nova ou senha
  resetada nasce com `deve_trocar_senha`.
- Permissões reais (`perm.require` na tela) e defesa no banco: `salvar_edicao_lancamentos` só altera
  e exclui registros dos Deptos permitidos (`PermissionError` no resto).

| Ação | admin | pcm | programador | leitor |
|---|---|---|---|---|
| Dashboard e exportar | ✅ | ✅ | ✅ | ✅ |
| Lançar / corrigir | ✅ | ✅ | só o seu Depto | ❌ |
| Upload | ✅ | ✅ | ❌ | ❌ |
| SLA / Equipes | ✅ | ✅ | só o seu Depto | ❌ |
| Listas, coordenações, trimestres, parâmetros | ✅ | ✅ | ❌ | ❌ |
| Usuários, auditoria, excluir/restaurar trimestre, editar fechado | ✅ | ❌ | ❌ | ❌ |

- Não é possível rebaixar ou desativar o **último administrador ativo**, nem o próprio acesso.
- O 1º administrador só é criado com a tabela de usuários vazia (checagem e insert na mesma
  transação).
- Segredos só nos Secrets do Streamlit Cloud ou em `.streamlit/secrets.toml` (no `.gitignore`).
- **Repositório público**: dados reais ficam fora do Git (`.gitignore`: `dados/`, exports do PCM,
  planilhas de trimestre, relações de ativos/equipes/serviços). ⚠️ Exceções hoje versionadas: ver
  §12.

## 10. Padrões de interface

| Item | Padrão | Onde |
|---|---|---|
| Percentual (cartões, rótulos, tooltips) | 2 casas, vírgula: `95,90%` | `ui.pct`, `graficos.pct_br` |
| Eixo de percentual | inteiro `.0%` | gráficos |
| Percentual em tabela | formato `"percent"` do Streamlit (2 casas; separador conforme o navegador) | `FMT_PCT` |
| Reais em cartão e gráfico | `R$ 657.389` (sem casas) | `ui.reais`, eixo com `labelExpr` |
| Reais em tabela | `R$ 370.051,23` pelo **pandas Styler** (exibição formatada, ordenação numérica) | `dashboard._aba_financeiro` |
| Rótulos nas curvas | valor só quando muda em relação à semana anterior e nunca 0; Realizado abaixo do ponto, metas acima; a projeção não repete o valor da semana atual | `graficos._rotulos` |
| Cores por coordenação | domínio fixo (`todas`) — a cor não muda ao filtrar | `curvas_coordenacoes` |
| Barras da Evolução | percentual na base; texto branco, escuro quando a barra é baixa (< 12%) | `graficos.evolucao` |

## 11. Como evoluir

- **Tela nova**: `modules/nova.py` com `render_nova()` → `app.py::ROTAS` → botão em `home.py::MENU`.
- **Aba nova numa tela**: acrescentar na lista de abas; as abas já têm `key` e execução só da aberta.
- **Coluna nova no lançamento**: `schema.py` (tabela + `MAPA_LANC`) → `_migrar` → `modelo.COLS_LANC` →
  `queries.linha_lancamento` → **MAJOR**.
- **Regra de cálculo**: sempre em `core/` (sem Streamlit) → `python tests/test_regra_pcm.py` →
  `scripts/conferir_pcm.py` contra o Power BI → atualizar REGRA_ADERENCIA_PCM.md.
- **Versão** (SemVer, `core/versao.py`): PATCH correção/visual; MINOR funcionalidade compatível; MAJOR
  tela nova, fluxo, segurança, integridade de dado ou schema. Toda mudança de comportamento: bump +
  linha no histórico de `versao.py` + linha em HISTORICO_PROJETO.md.
- **Testar uma tela sem navegador**: `streamlit.testing.v1.AppTest` com `PLANO_DB_URL` apontando para
  uma **cópia** do SQLite (nunca o banco real), preenchendo `session_state["usuario"]` e
  `session_state["pagina"]`.
- **Ver um gráfico como imagem**: `vl-convert-python` (`vlc.vegalite_to_png(chart.to_dict())`) — não
  está no `requirements.txt`; instalar à parte.
- **Revisão**: toda mudança de código passa por revisão em duas lentes — correção (bugs, perda de
  dado, casos de borda) e simplicidade (o que dá para tirar).
- **Commits**: nunca incluir dados reais; conferir `git status` antes (planilhas soltas na pasta são
  comuns).

## 12. Armadilhas conhecidas

| Sintoma | Causa | Solução adotada |
|---|---|---|
| "Failed to fetch dynamically imported module …js" | servidor uvicorn do Streamlit ≥ 1.57 no Cloud (~20% de falhas) e instabilidade da plataforma (~15%) | Streamlit fixo em 1.56.0 + `useStarlette = false`; usuário usa **F5** (não Ctrl+Shift+R). Antes de subir a versão: app de teste, 40 chamadas a `/_stcore/health`, 0 falhas |
| `DataError` só no Neon | texto maior que a coluna (SQLite não confere) | `_cabe` + `justificativa` TEXT; testar uploads também contra PostgreSQL |
| Eixo mostrando "0%" e tooltip "30.756400%" | formato `"%"` do Vega sai com 6 casas e corta o rótulo | `.0%` no eixo; rótulos prontos em pt-BR |
| Formato `"$"` mostrando dólar | d3-format é en-US | `labelExpr` com `R$` e ponto no milhar |
| Aba volta para a primeira após "Salvar" | `st.tabs` sem estado | `key` + `on_change="rerun"` |
| Seletor do menu "desfaz" a troca de trimestre | widget `sb_trimestre` guarda o valor antigo | trocar em callback (`on_click`) e limpar a chave |
| `column_config` ignora o Styler | `column_config` tem precedência | formatar R$ pelo Styler e não passar `column_config` nessas colunas |
| Data ISO lida como dia/mês | `dayfirst` em texto `2026-10-05` | `dados.para_data` |
| Neon recusa conexão na rede MRS | firewall derruba o SSLRequest | `sslnegotiation=direct` (só local) |
| App vazio após reiniciar | sem Secret → SQLite temporário | alerta no menu lateral; conferir Secrets |
| Keep-alive parou | GitHub desliga cron após 60 dias sem commit | religar o workflow |
| ⚠️ **Dados reais no repositório público** | `Orçamento Ger. SP.xlsx` (usado pelo Financeiro online) e `Plano de Manutenção 2º Trimestre - SP.xlsx` estão versionados desde antes do `.gitignore` | **pendente de decisão**: tornar o repositório privado (o Streamlit Cloud aceita) ou levar o orçamento para o banco por upload e remover os arquivos do histórico |

## 13. Decisões registradas

| Data | Decisão | Motivo |
|---|---|---|
| 03/11/2026 | Planilha sem fórmulas; Python calcula semana e pesos | fórmulas quebravam (JIC sem peso no 2º tri) |
| 03/11/2026 | Curva planejada = Planejamento PCM congelado | é o "norte" do trimestre |
| 03/11/2026 | Login próprio PBKDF2 (não Supabase Auth) | org Supabase Free bloqueada em out/2026; funciona em SQLite e Neon |
| 03/11/2026 | SQLite local + Neon em produção, mesma camada SQLAlchemy | publicar trocando só a URL |
| 03/11/2026 | SLA por Depto × Meta | produção esperada da equipe, configurada pela coordenação |
| 03/11/2026 | Janela de semanas pelo calendário (4º tri/2026 = 40–53) | 2026 tem semana 53 com plano |
| 03/11/2026 | **Streamlit Community Cloud** (Hugging Face e Render descartados) | HF exige PRO (cota cpu-basic = 0); Render Free divide 750 h/mês com o Gestão_OS; perda de ~15% de requisições é da plataforma, contornada com F5 |
| 03/11/2026 | Cache por versão dos dados | 0 consultas por navegação (latência EUA ↔ SP) |
| 04/11/2026 | Aderência = regra oficial do PCM | número igual ao Power BI |
| 04/11/2026 | Gerência pela regra própria do PCM | export consolidado `data (10)`, 19/19 metas |
| 04/11/2026 | Variação < 1 p.p. aceita; mantido o modelo de menor variação | realizado oficial por meta testado: ganho de 0,04 p.p., descartado |
| 04/11/2026 | Proteção dos lançamentos (cópia, confirmação, bloqueio de fechado) | evitar perder o que os programadores digitaram |
| 06/11/2026 | Dashboard abre no trimestre corrente | resultado do momento, não o último importado |
| 10/11/2026 | Realizado do Power BI por Depto | uma fonte por Depto, sem contagem dupla |
| 11/11/2026 | Keep-alive com navegador sem tela no GitHub Actions | o app não dorme; GET simples não conta como visita |

## 14. Pendências

- **Decidir sobre os dados reais versionados** (§12): repositório privado ou orçamento no banco.
- Confirmar a Gerência do 2º e 3º tri com o export consolidado de cada trimestre.
- Validar com o PCM a regra do **ano** (hoje média dos trimestres).
- Orçamento (curva OPEX) por upload, no banco, em vez do Excel na pasta.
- Disciplinas **E/I** e outras gerências: cadastrar coordenações e validar pesos.
- Login corporativo / **HubSP** (SSO por ticket JWT, identidade pelo `usuarios.email`).
- Migrações versionadas, se `_migrar` crescer demais.
- Hospedagem paga (Render Starter ou HF PRO), se a instabilidade do Streamlit Cloud incomodar.
