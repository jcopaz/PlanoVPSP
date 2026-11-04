# Histórico do projeto — decisões, investigações e lições

Linha do tempo do Plano VP para quem chegar depois (pessoa ou agente de IA): **o que foi decidido,
por quê, o que foi testado e descartado**. Detalhes de versão em [`core/versao.py`](../core/versao.py);
regra de cálculo em [REGRA_ADERENCIA_PCM.md](REGRA_ADERENCIA_PCM.md).

---

## Linha do tempo

| Data | Versão | O que aconteceu |
|---|---|---|
| jun/2026 | 1.0 | Dashboard único lendo a planilha do 2º tri (Diário + Planilha de Peso, com fórmulas). |
| 11/09/2026 | 2.0 | Modular (`core/`), parametrizado por `parametros.xlsx`, curva OPEX top-down. |
| 03/11/2026 | 2.1–2.2 | Modelo de planilha **sem fórmulas** (Python calcula semana/pesos); importador do PCM (pesos + Planejamento congelado). |
| 03/11/2026 | 3.0 | App completo no padrão do **MRS Sentinel**: login, banco, Lançamentos, Dados, Configurações, histórico. |
| 03/11/2026 | 3.0.1–3.0.3 | Deploy no Streamlit Cloud: driver psycopg, versões fixas, Streamlit 1.56 (Tornado). |
| 03/11/2026 | 3.1.x | Tentativa de Hugging Face (bloqueada por cota); volta ao Streamlit Cloud; **cache** (navegação sem consultas). |
| 04/11/2026 | 3.2.0 | Histórico direto dos exports **Planejado/Realizado** do PCM. |
| 04/11/2026 | 4.0.0 | Aderência pela **regra oficial do PCM** (Adr_Ativo), validada contra o Power BI. |
| 04/11/2026 | 4.1.x | Regra documentada (REGRA_ADERENCIA_PCM.md), visão por material, `scripts/conferir_pcm.py`, testes. |
| 04/11/2026 | 4.2.0 | **Gerência pela regra do PCM** (export consolidado `data (10)`): Σ pesos, DEPTO soma volume, ATIVO soma realizado limitado. |

---

## Decisões e o porquê

### Dados e cálculo
- **Planilha sem fórmulas, Python calcula tudo.** A planilha antiga tinha fórmula quebrada (uma linha de
  JIC de 23/05 do 2º tri sem semana/peso) e cada trimestre exigia remontar fórmulas.
- **Semana = WEEKNUM do Excel** (domingo inicia; 1º/jan = semana 1). Existe **semana 53** (28–31/12/2026).
  Janela do trimestre calculada pelo calendário (4º tri/2026 = 40–53), editável.
- **Curva planejada = Planejamento PCM congelado** (o "norte" do trimestre); os programadores lançam a
  execução pela própria programação.
- **Peso = Peso Item Inicial** (fixo por meta; o PCM só redistribui) — um export de pesos serve para todos
  os trimestres (76/76 pesos reproduzidos).
- **Aderência = regra do PCM** (teto por meta; "Sim" ou Encerrada; pelo ativo, com GOEV; sem
  Saneamento/Drenagem) — ver REGRA_ADERENCIA_PCM.md, inclusive as variantes descartadas.
- **SLA = produção esperada da equipe por dia**, por Depto × meta → "Dias de equipe p/ concluir".
- Datas em texto ISO (`2026-10-05`) eram lidas como dia/mês — `core/dados.py::para_data` resolve.

### Aplicação
- **Padrão do MRS Sentinel**: `app.py` roteador, `auth/`, `database/`, `core/` (sem Streamlit), `modules/`.
- **Login próprio PBKDF2** (não Supabase Auth): a org Supabase Free foi bloqueada em out/2026; funciona igual
  em SQLite e Neon. Perfis admin/pcm/programador/leitor; programador preso ao Depto (tela **e** banco).
- **Banco**: SQLite local ou PostgreSQL (Neon) pela mesma camada SQLAlchemy — só muda a URL.

### Hospedagem (investigação de 03/11/2026)
- **Streamlit Community Cloud — em uso.** Os apps da conta perdem **~15% das requisições** ("Failed to fetch
  dynamically imported module … .js"). Provado que **não é o código**: um app mínimo de 1 linha e o Sentinel
  têm o mesmo sintoma; um app público de referência fica em 0%. Contorno: **F5** (o navegador guarda os
  componentes já baixados — **não** usar Ctrl+Shift+R, que apaga esse cache).
- Streamlit fixado em **1.56.0** (último com servidor Tornado; o uvicorn das versões novas foi suspeito no
  início — não era a causa, mas a versão fixa evita trocas de arquivos .js a cada deploy).
- **Render gratuito — descartado**: 750 h/mês são **por conta** e a API do Gestão_OS (keep-alive 24 h) já
  consome ~744 h; estourar suspende **todos** os serviços gratuitos. Render Starter (~US$ 7) é a opção paga.
- **Hugging Face Spaces — bloqueado**: conta nova com cota *cpu-basic* = 0 (exige PRO ~US$ 9). Tudo pronto
  (`Dockerfile`, workflow `sync-hf.yml` com Trusted Publisher/OIDC) — basta assinar e criar a variável
  `HF_SPACE` no GitHub.
- **Neon** (São Paulo) é só o banco; não resolve o problema do servidor do app.

### Desempenho
- App (EUA) ↔ Neon (SP) ≈ 0,15 s por consulta. Antes: 8–26 consultas por clique (1–7 s).
  Agora: **versão dos dados em cache 10 s, usuário em cache 60 s** → navegação com 0 consultas.
  Quem grava limpa o cache e vê na hora; os demais em até 10 s.
- Mesma análise no **Sentinel** (branch `perf/cache-dados`): cache das bases de 5 min → 6 h (o upload já
  limpa), páginas em paralelo e ordenadas, Gerência Geral no cache compartilhado.

---

## Lições (vale para os outros apps)

1. **Medir antes de mudar**: contar consultas/bytes por tela com latência simulada achou o gargalo real.
2. **Comparar com um controle**: app mínimo × app real × app de referência separou "nosso código" de
   "plataforma".
3. **Peça o export no nível certo**: a Gerência não fechou com 13 fórmulas sobre números de coordenação;
   fechou na hora com o export consolidado (uma linha por meta).
4. **Número oficial é a fonte da verdade**: a regra do PCM só fechou testando variantes contra o print do
   Power BI — e o teste virou script (`scripts/conferir_pcm.py`) para não se perder.
4. **Cotas gratuitas são por conta**, não por serviço (Render, Supabase): somar o uso de todos os apps.
5. **Dados reais fora do GitHub público** (`dados/`, exports do PCM, `secrets.toml`).

---

## Pendências conhecidas

- Confirmar a Gerência do 2º e 3º tri com o export consolidado de cada trimestre (como o `data (10)`).
- Validar com o PCM a regra do **ano** (hoje média dos trimestres).
- **Disciplinas E/I** (Eletro/Infra) — cadastrar Deptos e definir com o PCM como se combinam.
- **Orçamento (curva OPEX) na web**: hoje depende do Excel na pasta.
- Hospedagem estável: Render Starter ou HF PRO, se o erro de .js incomodar.
- Integração com o **HubSP** (SSO por ticket; identidade pelo e-mail do usuário).
