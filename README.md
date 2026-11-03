# 🚂 Dashboard de Manutenção — Via Permanente (Gerência Malha SP)

Curva do plano físico (Meta PCM × Realizado × Projeção pelo ritmo médio) **e**
curva OPEX financeira (Orçado Planejado × Realizado × Projetado), replicável em
qualquer trimestre trocando só o `parametros.xlsx`.

---

## Como rodar localmente

**Windows (Python portátil incluso):**

```
Abrir_Dashboard.bat
```

**Qualquer ambiente com Python 3.10+:**

```bash
pip install -r requirements.txt
python scripts/gerar_parametros.py      # cria parametros.xlsx se não existir
streamlit run app.py
```

---

## Planilha do trimestre — modelo v3 (sem fórmulas)

Modelos em [`modelos/`](modelos/) (gerados por `python scripts/gerar_modelo.py`):

- **`Modelo_Plano_Trimestre.xlsx`** — em branco, para cada novo trimestre.
- **`Exemplo_Plano_Trimestre.xlsx`** — preenchido com dados **fictícios** (4º tri/2026).

| Aba | Quem preenche | Quando |
|---|---|---|
| `Pesos` | PCM | 1x por trimestre — peso **relativo** de cada meta por Depto (não precisa somar 1) |
| `Plano_PCM` | 1 pessoa | início do trimestre — cópia das linhas da planilha do PCM |
| `Lancamentos` | programadores | ao longo do trimestre — execução (`No Plano` = Sim) e extra plano (`Não`) |
| `Listas` | quem administra | opções dos menus suspensos (equipes, justificativas...) |

Não há fórmulas: **Semana** (= `WEEKNUM` do Excel), **Coordenação** (aba `Coordenacoes`
do parametros.xlsx), **Plano Trimestral** (soma do Plano_PCM) e todos os **pesos**
(`Peso ÷ soma do Depto ÷ Plano Trimestral`) são calculados em `core/dados.py`.
O formato antigo (`Diário` + `Planilha de Peso`) continua sendo lido.

### Início do trimestre: importar do PCM (1 pessoa)

Baixe do painel do PCM os dois exports do trimestre e rode:

```bash
python scripts/importar_plano_pcm.py "data (9).xlsx" --planejamento "Planejamento PCM.xlsx" \
    --catalogo "dados/Plano_<trimestre anterior>.xlsx"
```

- **`data (9).xlsx`** (pesos por meta) → aba `Pesos` com o **Peso Item Redist** (coluna G).
- **`Planejamento PCM.xlsx`** (visão congelada, plano por dia) → aba `Plano_PCM`: é a
  **curva planejada** (Meta PCM). Sem ele, o plano trimestral é dividido igualmente pelas semanas.
- `--catalogo` copia Unidade/SLA das metas (o export não traz).
- O trimestre vem do rodapé do export (`Tri/Ano é Tri 4/26`).
- Gera `dados/Plano_<ano>_T<tri>.xlsx`, com `Lancamentos` em branco e o menu de
  Equipes já preenchido. Rodar de novo com `--forcar` troca o plano e **mantém os lançamentos**.

Depois disso, os **programadores** lançam na aba `Lancamentos` o que executaram,
com base na programação deles; o dashboard compara com a curva congelada do PCM.

Migrar uma planilha antiga: `python scripts/converter_planilha_antiga.py "<arquivo>.xlsx"`
→ grava em `dados/` (pasta fora do Git: dados reais não vão para o GitHub).

---

## Trocar de trimestre (sem tocar em código)

Abra **`parametros.xlsx`** → aba **`Config`**:

| Parâmetro          | O que colocar                                             |
|--------------------|----------------------------------------------------------|
| `trimestre`        | `1`, `2`, `3` ou `4`                                      |
| `arquivo_plano`    | nome do workbook do trimestre (o que os colaboradores preenchem) |
| `arquivo_orcamento`| `Orçamento Ger. SP.xlsx` (para a aba Financeiro)          |
| `semana_inicio` / `semana_fim` | só se quiser forçar (senão usa a aba `Trimestres`) |

Coloque o novo workbook do trimestre na **mesma pasta** e recarregue o app
(no menu do Streamlit → *Rerun*, ou `C` para limpar cache).

### Outras abas do `parametros.xlsx`

- **`Trimestres`** — janelas de semana e meses de cada trimestre.
- **`Coordenacoes`** — de-para `Depto → Coordenação → Centro de Custo` e quais
  entram na visão *Gerência* (o antigo `÷3` fixo virou contagem automática).
- **`Envelope_OPEX`** — quais **Pacotes** e **Centros de Custo** da aba `PLAN ORÇ`
  compõem o envelope OPEX de manutenção, e se o *Realizado contábil* vem da
  `PLAN ORÇ` ou da aba `Realizado Analitico`.

---

## Modelo da curva financeira (top-down)

Não existe custo unitário confiável por item de manutenção, então:

1. **Envelope OPEX do período** = soma da aba `PLAN ORÇ` (Orçamento Ger. SP),
   filtrando os pacotes de manutenção e os centros de custo da visão escolhida.
2. **Orçado Planejado** = envelope × curva física planejada (Meta PCM).
   **Realizado** = envelope × aderência física realizada.
   **Projetado** = envelope × projeção física (ritmo médio).
3. **Por item** = envelope rateado pelo peso planejado/realizado de cada
   `Descrição Meta` (aproximação contábil, não de engenharia).
4. **Referências**: *Orçamento OPEX oficial* e *Realizado contábil SAP* — as
   curvas mensais reais da `PLAN ORÇ`. A diferença entre o *Realizado* derivado
   (avanço físico) e o *Realizado SAP* mostra o descolamento entre execução e
   lançamento contábil (faturamento).

---

## Publicar na web (Streamlit Community Cloud)

1. Suba este projeto para um repositório GitHub. **Precisam ir junto:**
   `app.py`, `core/`, `parametros.xlsx`, `requirements.txt`, `.streamlit/`,
   o workbook do trimestre e `Orçamento Ger. SP.xlsx`.
   *(o `.gitignore` já exclui `python_portatil/` e as Base-Zero de preços,
   que o app não usa.)*
2. Em <https://share.streamlit.io> → **New app** → aponte para `app.py`.
3. A cada novo trimestre: atualize `parametros.xlsx` + o novo workbook no
   repositório; o deploy recarrega sozinho.

---

## Estrutura

```
app.py                  Streamlit — só orquestra a tela
core/
  config.py             lê parametros.xlsx (com defaults embutidos)
  modelo.py             abas/colunas/menus do modelo v3 (fonte única)
  importar_pcm.py       exports do PCM (pesos + planejamento congelado) -> modelo v3
  dados.py              carga do modelo v3 ou do Diário antigo; calcula semana e pesos
  fisico.py             curvas físicas + KPIs (lógica da v1, isolada)
  financeiro.py         envelope OPEX da PLAN ORÇ + curvas R$ + rateio por item
  graficos.py           Altair (substitui streamlit-echarts, incompatível)
scripts/gerar_parametros.py   gera o parametros.xlsx padrão
scripts/gerar_modelo.py       gera modelos/ (modelo em branco + exemplo fictício)
scripts/converter_planilha_antiga.py   Diário antigo -> modelo v3 (saída em dados/)
scripts/importar_plano_pcm.py          exports do PCM -> dados/Plano_<ano>_T<tri>.xlsx
modelos/                Modelo_ e Exemplo_Plano_Trimestre.xlsx
parametros.xlsx         ← editado a cada trimestre
app_v1_backup.py        versão anterior (referência)
```
