# Regra de aderência do PCM — como o app calcula e por quê

> **Leia antes de mexer em qualquer cálculo de aderência.** Este documento guarda a regra
> oficial do PCM, de onde ela veio (engenharia reversa do Power BI), as evidências, as
> premissas ainda não validadas e como reconferir. Mudou o PCM? Rode
> `scripts/conferir_pcm.py` (seção 7) antes e depois de qualquer ajuste.

Documentos relacionados: [DOCUMENTACAO_TECNICA.md](DOCUMENTACAO_TECNICA.md) (arquitetura),
[HISTORICO_PROJETO.md](HISTORICO_PROJETO.md) (decisões e lições), [MANUAL_USUARIO.md](MANUAL_USUARIO.md).

---

## 1. Resumo em uma linha

```
Aderência da coordenação = Σ_meta  Peso Item Redist × min(Realizado, Plano Trimestral) ÷ Plano Trimestral
```

É a métrica **"Adr_Ativo"** do painel Power BI do PCM. Conferida nos 4 trimestres de 2026:
**11 de 12 coordenações dentro de 0,5 p.p.** (a 12ª é o 4º tri em andamento — seção 6).

---

## 2. De onde vêm os dados (exports do Power BI do PCM)

Todos têm aba única `Export` e um **rodapé "Filtros aplicados: …"** (o app ignora as linhas sem data).

| Arquivo (exemplo) | Granularidade | Colunas usadas | Vira, no app |
|---|---|---|---|
| **Pesos** — `data (9).xlsx` | 1 linha por Depto × meta (todas as metas, inclusive sem plano) | `Departamento`, `GRUPO`, `Descrição Meta`, **`Peso Item Inicial`** (F), `Peso Item Redist` (G), `Plano Trimestral` | aba **Pesos** + catálogo |
| **Planejado** / **Planejamento PCM** — visão **congelada** | 1 linha por dia × meta × equipe × ativo | `Data`, `Centro de Trabalho` (Depto), `Descrição Meta`, `Qtd. Plano`, `Equipe`, `Local de Instalação/Equipamento`, `KM` | aba **Plano_PCM** (curva Meta PCM) |
| **Realizado** — ordens do SAP lançadas pelos programadores | 1 linha por ordem × operação × material | `Gerência`, **`Centro de trabalho Ativo`**, `Centro de trabalho responsável`, `Data Programada`, `Descrição Meta`, `Qtd. Programada`, **`Qtd. Real`**, **`Considera Plano?`**, **`Status atual da ordem`**, `Motivo de Perda`, `Nº ordem` | aba **Lancamentos** |

Pegadinhas dos exports:
- **`Tri/Ano` é uma data cujo MÊS é o número do trimestre**: `01/04/2026` = 4º tri/2026,
  `01/02/2026` = 2º tri. O trimestre confiável é o do **rodapé** (`Tri/Ano é Tri 4/26`) ou o da **data**.
- **Depto**: `V.SP.IPA` = Via Permanente (V), Gerência SP, coordenação IPA (Paranapiacaba).
  O PCM também tem `E.SP.*` e `I.SP.*` (outras disciplinas — seção 6).
- O Planejado pode trazer **vários trimestres**; o app separa pela data.

---

## 3. A regra, componente por componente

### 3.1 Peso de cada meta = Peso Item Inicial, redistribuído
- O **Peso Item Inicial (F)** é **fixo por meta** (catálogo do PCM). O **Peso Item Redist (G)** é F
  normalizado entre as metas **com plano no trimestre**, dentro do Depto (soma 1).
- O app grava F (ou G) e normaliza de novo em `core/dados.py::montar_canonico` — dá o mesmo G.
- **Evidência:** F do export do 4º tri, normalizado, reproduz **76 de 76** pesos das planilhas antigas
  do 1º e do 3º tri. Por isso **um único export de pesos serve para todos os trimestres**.

### 3.2 Grupos fora da aderência da Via
- Metas dos grupos **Saneamento Vegetal** e **Drenagem** (Limpeza de canaleta, Roçada, Capina) **não
  pesam**. Config `grupos_fora_aderencia` (Configurações → Parâmetros), aplicada antes da normalização.
- **Evidência:** no 2º tri/2026 o PCM pôs essas metas nos centros V.SP; com elas o 2º tri dá ~63–69%,
  sem elas 98,4/98,5/100% = Power BI. No 4º tri elas já vêm nos centros I.SP.

### 3.3 O que conta como realizado ("CONC")
- Conta para o plano a ordem com **`Considera Plano? = Sim` OU `Status atual da ordem = Encerrada`**.
  É o "CONC" (concluídas) dos nomes de coluna do PCM (`Real Ativo(CONC)`).
- No app: `No Plano = Sim` (feito em `core/importar_pcm.py::ler_realizado`).

### 3.4 De quem é a execução: do ATIVO
- A linha é atribuída ao Depto **onde fica o ativo**: `Gerência` + `Centro de trabalho Ativo`
  (`SP` + `IPA` → `V.SP.IPA`) — e **não** ao `Centro de trabalho responsável`.
- Entram responsáveis da própria Via (`V.SP.*`) e a **GOEV** (socaria mecanizada). Sem a GOEV, a
  Socaria de Linha/AMV (15–37% do peso em algumas coordenações) ficava zerada.

### 3.5 Teto por meta
- O realizado de cada Depto × meta conta **no máximo o Plano Trimestral** dela. Fazer 132 de 40 conta 40;
  excesso numa meta **não compensa** outra. Acumulado semana a semana em
  `core/fisico.py::_peso_realizado_limitado` (curva, KPIs, tabela por material).

### 3.6 Trimestre do realizado
- Pela **`Data Programada`** (= coluna `Trimestre` do PCM em 100% das linhas). Ordens programadas em
  2023–2025 e confirmadas em 2026 ficam de fora (todas "Considera Plano = Não").
- Linhas **sem Descrição Meta** (ordens fora do catálogo do plano, ~12,9 mil em 2026) ficam de fora por
  padrão — não pesam na curva (opção na tela de upload para incluí-las).

---

## 4. Visões e como cada uma é calculada

| Visão | Onde | Cálculo | Status |
|---|---|---|---|
| **Coordenação** | Dashboard → Resumo/Por Coordenação | Σ peso × aderência da meta (seção 1), metas do Depto | ✅ **validada** contra o Power BI |
| **Material / meta** | tabela "Atividades" | `Aderência PCM` = realizado com teto ÷ plano; `Peso na Visão`; `Contribuição` = peso × aderência. **Σ Contribuição = aderência da visão** | ✅ consistente com a coordenação |
| **Gerência** | Resumo/Gerencial | **média simples das coordenações** que "entram na Gerência" (Configurações → Coordenações) | ⚠️ **premissa não validada** (seção 6) |
| **Disciplina** (V / E / I) | — | o app hoje trata **só a Via (V.SP)** | ❌ **não coberta** (seção 6) |
| **Evolução** (trimestre / ano) | Evolução | trimestre = aderência no fim (ou acumulada até a última semana); ano = média dos trimestres | ⚠️ ano = premissa |

---

## 5. Como a regra foi descoberta (para não repetir o caminho)

1. **v3.2.0** importava o Realizado pelo `Centro de trabalho responsável`, só "Considera Plano = Sim",
   **sem teto** → 1º/2º/3º tri = 89/70/90% (Power BI: ~99/98/97%).
2. As colunas `Pontuação Meta` do export de pesos mostraram a fórmula: `Pontuação = G × Aderência_Ativo`
   e `Σ Pontuação = Adr_Ativo` (V.SP.PJU 4º tri = 6,52% exato).
3. `Real Ativo` ≤ `Real Volume` e ≤ plano → **teto por meta** (Correção de bitola PJU: volume 132, ativo 40).
4. Hipótese "casar realizado × plano pelo **local de instalação**" → **descartada** (quase nada casa).
5. Variantes testadas contra o print do Power BI (2026):

| Variante | Acertos (≤0,5 p.p.) | Resultado |
|---|---|---|
| A — ativo, só "Sim" | 8/12 | 1º e 3º tri IPA/IPG baixos (faltava ordem encerrada) |
| C — ativo, todas as ordens | 10/12 | 2º tri IPA alto (contava ordem que o PCM não conta) |
| D/E — todas exceto canceladas | 9–10/12 | pior que C |
| **F — "Sim" OU Encerrada** | **11/12** | **adotada** (a 12ª é o 4º tri em andamento) |
| G — exceto "datas divergentes" | 9/12 | descartada |

6. O 2º tri só bateu ao tirar **Saneamento/Drenagem**; 1º e 3º só bateram ao atribuir pelo **ativo** (GOEV).

---

## 6. Validação, premissas e pontos em aberto

**Números de referência (Power BI, Adr_Ativo, extraídos em 04/11/2026)** — também em
`dados/referencia_pcm_2026.csv` (fora do Git):

| Trimestre | IPA (PCM / app) | IPG (PCM / app) | PJU (PCM / app) |
|---|---|---|---|
| 1º/2026 | 99,27 / 99,17 | 98,15 / 98,05 | 100,00 / 100,00 |
| 2º/2026 | 98,43 / 98,85 | 98,45 / 98,45 | 100,00 / 100,00 |
| 3º/2026 | 96,46 / 96,54 | 99,52 / 99,52 | 99,96 / 99,96 |
| 4º/2026* | 25,26 / 26,29 | 5,37 / 5,37 | 6,52 / 6,52 |

\* trimestre em andamento: o Realizado foi exportado depois do print; diferença esperada.

**Premissas ainda NÃO validadas com o PCM:**
- **Gerência = média simples das coordenações.** O PCM pode ponderar (por volume, nº de metas…).
  Para validar: pegar o número de Gerência do Power BI e rodar a seção 7.
- **Ano = média dos trimestres.**
- **Disciplinas E (Eletro) e I** — o PCM mede outras disciplinas nas mesmas coordenações (E.SP.*, I.SP.*),
  com metas e `Tipo de medição = ATIVO`. Para incluir: cadastrar os Deptos em Configurações →
  Coordenações, ajustar `RESPONSAVEIS_EXTRA_VIA` (`core/importar_pcm.py`) e **definir com o PCM** como a
  coordenação/Gerência combina as disciplinas — depois validar pela seção 7.

---

## 7. Como reconferir (sempre que o PCM mudar algo ou a cada trimestre fechado)

1. Exportar do Power BI: pesos (`data (N).xlsx`), Planejado, Planejamento do trimestre atual e Realizado.
2. Anotar o **Adr_Ativo** de cada coordenação num CSV `ano;trimestre;depto;aderencia`.
3. Rodar:
   ```bash
   python scripts/conferir_pcm.py --pesos "data (9).xlsx" --planejado "Planejado 1 ao 3º Tri.xlsx" \
       --planejamento-atual "Planejamento PCM.xlsx" --realizado "Realizado 1 ao 4º Tri.xlsx" \
       --referencia dados/referencia_pcm_2026.csv
   ```
4. Saída "N de N dentro de 0,5 p.p." (código 0). Divergiu? Comparar meta a meta: o export de pesos traz
   `Real Volume`, `Real Ativo`, `Aderência_Trimestral_Ativo` e `Pontuação Meta` por meta — a meta que
   diverge mostra qual componente da seção 3 mudou.

---

## 8. Onde está no código

| Componente | Arquivo · função |
|---|---|
| Leitura dos exports, pesos (F), Realizado (3.3, 3.4, 3.6) | `core/importar_pcm.py` · `catalogo_peso_inicial`, `ler_planejamento`, `ler_realizado`, `montar_historico` |
| Normalização dos pesos, grupos fora (3.1, 3.2) | `core/dados.py` · `montar_canonico` |
| Teto por meta, curva, KPIs, tabela por material (3.5, 4) | `core/fisico.py` · `_peso_realizado_limitado`, `calcular`, `_tabela_itens` |
| Coordenação × Gerência, histórico | `core/motor.py` · `calcular_trimestre`, `historico`, `historico_anual` |
| Parâmetro dos grupos | `core/config.py` (`grupos_fora_aderencia`), tela Configurações → Parâmetros |
| Conferência contra o Power BI | `scripts/conferir_pcm.py` |
| Teste automático da regra (teto, grupos fora, fora do plano, Σ Contribuição) | `tests/test_regra_pcm.py` — `python -m pytest tests` |
