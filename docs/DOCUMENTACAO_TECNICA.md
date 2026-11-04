# Plano VP — Documentação técnica

Para quem vai **manter ou evoluir** o código. Uso do dia a dia: [MANUAL_USUARIO.md](MANUAL_USUARIO.md).
Versão atual e histórico: [`core/versao.py`](../core/versao.py).

---

## 1. Visão geral

O plano de manutenção da Via Permanente é definido pelo **PCM** a cada trimestre:
para cada Depto (Centro de Trabalho, ex. `V.SP.IPA`) há um conjunto de **metas**
(Descrição Meta) com **peso** e **quantidade planejada**, distribuídas por dia
(a "visão congelada"). Os **programadores** de cada coordenação lançam o que as
equipes executaram. O app compara **planejado × realizado** semana a semana.

```
 PCM (Power BI)                         Programadores
 ├─ data (N).xlsx  ── pesos ──┐         │ lançam execução
 └─ Planejamento PCM.xlsx ────┤         ▼
                              ▼    ┌──────────────┐     ┌─────────────────────┐
   Dados → Upload ───────────────► │   BANCO      │ ──► │ core/motor + fisico │ ──► Dashboard
   (planilhas passadas, backups)   │ (SQLite/Neon)│     │   (curvas, KPIs)    │
                                   └──────────────┘     └─────────────────────┘
                                          │
                              Dados → Exportação (Excel modelo v3 = backup)
```

## 2. Arquitetura (mesmo padrão do MRS Sentinel)

| Camada | Pasta | Regra |
|---|---|---|
| Entrada | `app.py` | só configura a página e roteia (login → troca de senha → menu → tela) |
| Acesso | `auth/` | sessão (`session.py`), senha PBKDF2 (`senha.py`), perfis (`permissions.py`), telas de login (`login.py`) |
| Dados | `database/` | conexão (`client.py`), tabelas (`schema.py`), **todo** SQL (`queries.py`) |
| Negócio | `core/` | cálculo e conversões — **sem Streamlit** (exceto `ui.py`), testável por script |
| Telas | `modules/` | uma tela por arquivo; chamam `core/` e `database/queries.py`, nunca SQL direto |
| Operação | `scripts/` | tarefas de linha de comando (usuário, carga em lote, modelos) |

Arquivos de `core/`:

| Arquivo | Responsabilidade |
|---|---|
| `modelo.py` | layout do modelo de planilha v3 (abas, colunas, menus) — fonte única |
| `dados.py` | `montar_canonico()`: Pesos+Plano+Lançamentos → formato canônico com semana, coordenação e pesos calculados; `semana_excel()`; leitura da planilha antiga |
| `fisico.py` | curvas Meta PCM / Realizado / Projeção e KPIs (aderência, tendência, mínimo semanal, dias de equipe) |
| `financeiro.py` | curva OPEX top-down a partir do `Orçamento Ger. SP.xlsx` |
| `motor.py` | ponte banco → cálculo: monta `Parametros`, calcula trimestre (Gerência + coordenações), histórico trimestral/anual |
| `importar_pcm.py` | lê os 2 exports do PCM (pesos e planejamento congelado) |
| `planilha.py` | lê (v3/antiga) e escreve (modelo v3) o Excel — upload e exportação |
| `config.py` | `Parametros` e defaults (o `parametros.xlsx` hoje só semeia o banco na 1ª execução) |
| `graficos.py` | gráficos Altair |
| `ui.py` / `versao.py` | estilo/cartões e versão |

## 3. Banco de dados

Definido em [`database/schema.py`](../database/schema.py) (SQLAlchemy Core). Roda igual em
**SQLite** (local) e **PostgreSQL/Neon** (produção). Tabelas são criadas na 1ª conexão
(`criar_tabelas`) e os cadastros padrão semeados (`queries.semear_padroes`).

| Tabela | Conteúdo | Chave |
|---|---|---|
| `trimestres` | ano, trimestre, semana_inicio/fim, status (aberto/fechado) | (ano, trimestre) |
| `pesos` | peso de cada meta por Depto no trimestre | (trimestre_id, depto, meta) |
| `plano` | visão congelada do PCM: 1 linha por dia/meta/equipe | id |
| `lancamentos` | execução lançada (com criado_por/alterado_por) | id |
| `metas_catalogo` | **Unidade e SLA** por Depto × Meta (vale para todos os trimestres) | (depto, meta) |
| `listas` | Equipe (por Depto), Justificativa, Status, Tipo Material, Grupo | (tipo, valor, depto) |
| `coordenacoes` | Depto → Coordenação → Centro de Custo, entra na Gerência | depto |
| `config` | parâmetros chave/valor (faixas, orçamento, `env.*` do envelope OPEX, `_versao_dados`) | chave |
| `usuarios` | login, nome, perfil, depto delegado, hash da senha | login |
| `auditoria` | quem fez o quê (login, uploads, edições, configurações) | id |

**Conexão** (`database/client.py`), primeira que existir: `st.secrets["database"]["url"]`
→ variável `PLANO_DB_URL` → `sqlite:///dados/plano.db`.
Neon na rede MRS exige `sslnegotiation=direct` na URL (firewall derruba o SSLRequest padrão).

**Cache**: toda gravação incrementa `config._versao_dados`; as leituras das telas usam
`st.cache_data` com essa versão na chave ([`modules/comum.py`](../modules/comum.py)).
A própria versão fica em cache por **10 s** e o usuário logado por **60 s** (`app.py`): a
navegação normal faz **0 consultas** ao banco. Isso importa porque o app (Streamlit Cloud, EUA)
fala com o Neon (São Paulo) a ~0,15 s por consulta — antes eram 8–26 consultas por clique
(1–7 s). Quem grava limpa o cache e vê na hora; os demais usuários, em até 10 s. Também evita o
estouro de tráfego do Neon visto no Gestão_OS (out/2026).

**Mudança de schema**: não há migração automática de colunas. Para alterar uma tabela
existente em produção, escreva o `ALTER TABLE` em `database/migracoes/AAAA-MM-DD_descricao.sql`,
rode no Neon e suba **MAJOR** em `core/versao.py`. Tabela nova é criada sozinha.

## 4. Regras de cálculo (validadas contra a planilha do 2º tri/2026)

**Semana** = `WEEKNUM(data)` do Excel (domingo inicia a semana; 1º/jan é a semana 1).
Por isso um ano pode ter **semana 53** (ex.: 27–31/12/2026). A janela de cada trimestre é
calculada pela 1ª e última data do trimestre (4º tri/2026 = 40–53) e pode ser ajustada em
Configurações → Trimestres.

**Pesos** (`dados.montar_canonico`):
```
Plano Trimestral (Depto, Meta) = Σ Quantidade Programada do plano congelado
Peso Item       = Peso / Σ Peso do Depto (só metas com Plano Trimestral > 0)
Peso Unitário   = Peso Item / Plano Trimestral
```
O PCM envia o **Peso Item Redist** (coluna G), que já é o Peso Item Inicial normalizado
entre as metas com plano — a normalização acima não o altera.

**Por linha**:
```
Peso Planejado Linha = Qtd Programada × Peso Unitário    (linhas do plano)
Peso Realizado Linha = Qtd Realizada × Peso Unitário     (lançamentos com No Plano = Sim)
Peso Extra Linha     = Qtd Realizada × Peso Unitário     (lançamentos com No Plano = Não)
```

**Regra oficial do PCM ("Adr_Ativo" do Power BI) — v4.0.0**, conferida nos 4 trimestres de 2026
(11 de 12 coordenações a até 0,4 p.p.; a 12ª é o 4º tri em andamento):
```
Aderência da coordenação = Σ_meta  Peso Item Redist × min(Realizado, Plano Trimestral) / Plano Trimestral
```
- **Teto por meta**: o realizado acumulado de cada Depto|Meta só conta até o plano dela
  (`fisico._peso_realizado_limitado`, semana a semana). Fazer 132 de 40 conta 40.
- **Realizado do PCM** (`importar_pcm.ler_realizado`): conta para o plano a ordem com
  "Considera Plano? = Sim" **ou** com a ordem "Encerrada" (o "CONC" das colunas do PCM); a execução
  é da coordenação **onde fica o ativo** ("Centro de trabalho Ativo" + Gerência), inclusive a feita
  pela **GOEV** (socaria mecanizada).
- **Grupos fora da aderência** (config `grupos_fora_aderencia`, padrão "Saneamento Vegetal;Drenagem"):
  peso zerado antes da normalização. No 2º tri/2026 o PCM pôs essas metas nos centros de Via, mas
  não as pesou; no 4º tri elas estão nos centros I.SP.

**Curvas** (`fisico.calcular`), acumuladas semana a semana, valor de 0 a 1 por Depto:
- *Meta PCM* = Σ Peso Planejado ÷ nº de coordenações da visão (1 ou as que "entram na Gerência");
- *Realizado* = Σ Peso Realizado (com teto por meta) ÷ mesmo divisor;
- *Projeção* = realizado na semana atual + ritmo médio × semanas restantes.
  Semana atual = última semana com lançamento "No Plano = Sim".

**Tendência**: gap = meta (100%) − projeção de fechamento; faixas configuráveis
(leve 5% / risco 10% / alto 15%). Sem nenhum lançamento: "Aguardando Lançamentos".

**Dias de equipe p/ concluir** = ⌈Pendente ÷ SLA⌉, SLA = produção esperada da equipe por dia
(`metas_catalogo`, por Depto × Meta).

**Histórico anual** = média das aderências trimestrais (cada trimestre vale 100% do seu plano).
Trimestre em andamento entra com a aderência acumulada até a última semana lançada.

**OPEX** (`financeiro.py`): envelope = soma da aba `PLAN ORÇ` (pacotes e centros de custo
configurados) × curva física; precisa do arquivo de orçamento na pasta do app.

## 5. Fluxos

**Início do trimestre** — Dados → Upload → exports do PCM:
`importar_pcm.trimestre_do_export` (rodapé `Tri/Ano é Tri 4/26`; a célula Tri/Ano grava o
4º tri como 01/04/2026 — o mês é o número do trimestre) → `importar_pcm.importar` (filtra os
Deptos cadastrados, confere Σ planejamento = Plano Trimestral, descarta datas fora do
trimestre) → `queries.substituir_plano` (pesos + plano; lançamentos intactos) →
`completar_catalogo` (metas novas entram sem SLA) → `adicionar_equipes`.

**Lançamento** — `modules/lancamentos.py`: grade com os lançamentos do Depto/semanas;
"Trazer o plano" pré-preenche as linhas do plano congelado. Ao salvar: só linhas
novas/alteradas são validadas (linha antiga intacta não bloqueia), calcula-se o diff
(novos/alterados/excluídos) e grava numa transação com auditoria. Trimestre fechado =
somente leitura (exceto admin).

**Histórico pelos exports do PCM** — `importar_pcm.montar_historico`: Planejado (N trimestres,
separados pela data) + Realizado (ordens SAP; trimestre = da Data Programada, igual à coluna
Trimestre do PCM; `Considera Plano?` → No Plano; `Motivo de Perda` → Justificativa quando
real < programado) + export de pesos. **Peso = Peso Item Inicial** (coluna F), fixo por meta: o PCM só o
redistribui entre as metas com plano (conferido contra as planilhas do 1º e 3º tri/2026, 76/76).
Realizado sem meta (fora do catálogo) e de trimestres sem plano (ordens 2023–2025) ficam de fora.

**Histórico** — planilha antiga ou v3 → `planilha.ler` → trimestre deduzido pelas datas
→ substitui pesos/plano e/ou lançamentos. Lançamento antigo sem meta é guardado como
`(SEM META)` (não pesa; aparece para correção).

**Backup** — Dados → Exportação: Excel do trimestre no modelo v3 (reimportável) ou .zip
com todos os trimestres + cadastros. Recomendado: exportar o .zip ao fechar cada trimestre.

## 6. Segurança e acesso

- Senha: PBKDF2-SHA256, 600 mil iterações, sal aleatório (`auth/senha.py`). Nunca em texto.
- Conta nova / senha resetada nasce com `deve_trocar_senha` → tela obrigatória de troca.
- Permissões em `auth/permissions.py`; cada tela chama `perm.require(...)` (bloqueio real).
- Programador com Depto delegado só lança e configura SLA/Equipes do seu Depto — validado na
  tela e também no banco (`salvar_edicao_lancamentos` só altera/exclui registros dos Deptos
  permitidos e recusa o resto com `PermissionError`).
- O usuário é relido do banco no máximo a cada 60 s (`app.py::_usuario_ainda_valido`): conta
  desativada sai e mudança de perfil/Depto vale em até 1 minuto, sem novo login. Troca de
  senha limpa esse cache na hora.
- Não é possível rebaixar/desativar o **último administrador ativo**, nem o próprio acesso.
- O 1º administrador só é criado com a tabela de usuários vazia (checagem e insert na mesma transação).
- Segredos só em `.streamlit/secrets.toml` (no `.gitignore`) ou nos Secrets do Streamlit Cloud.
- Dados reais (`dados/`, exports do PCM) não vão para o GitHub — o repositório é público.

## 7. Como evoluir

- **Tela nova**: `modules/nova.py` com `render_nova()` → `app.py::ROTAS` → botão em `modules/home.py::MENU`.
- **Coluna nova no lançamento**: `database/schema.py` (tabela + `MAPA_LANC`) → `core/modelo.py::COLS_LANC`
  → `queries.linha_lancamento` → migração SQL no Neon → MAJOR.
- **Regra de cálculo**: sempre em `core/` (sem Streamlit); rode a validação abaixo antes do commit.
- **Versão**: bump em `core/versao.py` + linha no HISTÓRICO a cada commit que muda comportamento.

**Validação mínima antes de publicar** (precisa da planilha do 2º tri na pasta):
```bash
python -c "from core import config,dados,fisico; p=config.carregar(); p.cfg['arquivo_plano']='Plano de Manutenção 2º Trimestre - SP.xlsx'; d,_,_=dados.carregar_plano(p); print(fisico.calcular(d,p,'Gerência',14,26).kpis['aderencia_atual'])"
# esperado: 0.9405 (planilha antiga) — a mesma base no modelo v3 dá 0.9418 (1 linha de JIC
# de 23/05 estava com a fórmula em branco no Excel antigo)
```

## 8. Decisões registradas

| Data | Decisão | Motivo |
|---|---|---|
| 03/11/2026 | Modelo de planilha sem fórmulas; Python calcula semana/pesos | fórmulas quebravam (linha de JIC sem peso no 2º tri) |
| 03/11/2026 | Curva planejada = Planejamento PCM congelado | é o "norte" do trimestre; programadores lançam pela própria programação |
| 03/11/2026 | Login próprio PBKDF2 (não Supabase Auth) | org Supabase Free bloqueada em out/2026; funciona igual em SQLite e Neon |
| 03/11/2026 | SQLite local + Neon em produção, mesma camada SQLAlchemy | começar já sem servidor; publicar só trocando a URL |
| 03/11/2026 | SLA por Depto × Meta em cadastro próprio | "produção esperada da equipe", configurada 1 vez por coordenação |
| 03/11/2026 | Hospedagem no Hugging Face Spaces (Docker + sync pelo GitHub Actions) | Streamlit Cloud perdia ~15% das requisições; Render free compartilha 750 h com o Gestão_OS |
| 04/11/2026 | Aderência = regra oficial do PCM (teto por meta, Sim ou Encerrada, ativo, sem Saneamento/Drenagem) | números iguais ao Power BI (Adr_Ativo) |
| 04/11/2026 | Histórico pelos exports Planejado/Realizado do PCM; peso = Peso Item Inicial | dispensa a planilha dos programadores; Peso Inicial é fixo por meta |
| 03/11/2026 | Janela de semanas automática pelo calendário (4º tri/2026 = 40–53) | 2026 tem semana 53 com plano |

## 9. Pendências / roadmap

> **Versão do Streamlit travada em 1.56.0** (`requirements.txt`). Da 1.57 em diante o Streamlit
> usa só o servidor uvicorn/Starlette, que no Streamlit Cloud perdeu ~20% das requisições em
> 03/11/2026 (erro "Failed to fetch dynamically imported module" na tela). Antes de subir a versão:
> publicar num app de teste e medir `/_stcore/health` (ex.: 40 chamadas seguidas, 0 falhas).


- Orçamento (curva OPEX) na web: hoje lê o Excel da pasta; levar a aba PLAN ORÇ para o banco via upload.
- Login corporativo (AD/Entra ID) no lugar da senha própria.
- **HubSP (SSO)**: aceitar o ticket do portal (`?ticket=`, JWT assinado, `aud` = slug do app,
  `jti` de uso único) em `auth/` — identidade ligada pelo `usuarios.email`; o Plano VP continua
  revalidando perfil/Depto. Contrato em `HubSP/docs/02_ARQUITETURA_SSO.md`. Manter o e-mail
  dos usuários preenchido desde já.
- Migrações de schema versionadas (pasta `database/migracoes/`).
- Ampliar para as áreas E/I e Gerência VP (basta cadastrar as coordenações; validar pesos).
