# Plano VP — Publicação

**Hospedagem atual: Hugging Face Spaces** (seção A). O Streamlit Community Cloud (seção B,
antiga) foi deixado de lado em 03/11/2026: os apps da conta perdiam ~15% das requisições
(erro "Failed to fetch dynamically imported module"), inclusive o Sentinel. O Render gratuito
foi descartado porque as 750 h/mês da conta já são consumidas pela API do Gestão_OS (com
keep-alive) — estourar suspende TODOS os serviços gratuitos, inclusive ela.

## A. Hugging Face Spaces (atual)

Como funciona: a cada push na `main`, o workflow `.github/workflows/sync-hf.yml` envia o
código para o Space (sem as planilhas .xlsx) e o Hugging Face reconstrói a imagem do
`Dockerfile`. O banco continua no Neon.

1. **Conta**: crie em https://huggingface.co/join (de preferência com o e-mail corporativo).
2. **Space**: *New Space* →
   - Owner: seu usuário · Space name: `plano-vp`
   - License: *other* · SDK: **Docker** → template **Blank**
   - Hardware: **CPU basic (free)** · Visibility: **Public** (Space privado só abre para quem
     tem conta no Hugging Face com acesso; o login do app protege os dados)
   - *Create Space*
3. **Secret do banco**: no Space → *Settings* → *Variables and secrets* → **New secret**
   - Name: `PLANO_DB_URL`
   - Value: a connection string do Neon (`postgresql://...?sslmode=require`), **sem aspas**
4. **Token**: https://huggingface.co/settings/tokens → *Create new token* → tipo **Write**
   (ou *Fine-grained* com escrita só no Space `plano-vp`) → copie o token (`hf_...`).
5. **GitHub** (`jcopaz/PlanoVPSP` → *Settings* → *Secrets and variables* → *Actions*):
   - aba **Secrets** → *New repository secret*: `HF_TOKEN` = o token do passo 4
   - aba **Variables** → *New repository variable*: `HF_SPACE` = `SEU_USUARIO/plano-vp`
6. **Primeiro envio**: GitHub → *Actions* → **Sync Hugging Face Space** → *Run workflow*.
   Depois disso, cada push na `main` atualiza o Space sozinho.
7. **Build**: no Space, aba *Logs*, aguarde *Running* (3–6 min na 1ª vez).
8. **Acesso**: `https://SEU_USUARIO-plano-vp.hf.space` (endereço direto, sem a moldura do site).
   Como o banco é o mesmo Neon, administrador, usuários e trimestres já gravados continuam lá.

Observações:
- **Dorme** após 48 h sem nenhum acesso; o 1º acesso depois disso leva ~1 min.
- **Financeiro (OPEX)**: o orçamento (.xlsx) não vai para o Space público; a aba mostra
  "orçamento não carregado" até o orçamento ser levado para o banco (roadmap).
- **Atualizar o app**: só `git push` na `main` (acompanhe em GitHub → Actions e na aba
  *Logs* do Space). Se o workflow avisar "HF_TOKEN/HF_SPACE não configurados", revise o passo 5.

---

## B. Streamlit Community Cloud (alternativa anterior)

Passo a passo para colocar o app na web. Tempo estimado: 20–30 min.
Arquitetura: **GitHub** (código) → **Streamlit Community Cloud** (roda o app) → **Neon** (banco PostgreSQL).

---

## 0. Antes de começar — repositório

O repositório `jcopaz/PlanoVPSP` ainda tem dois arquivos com dados reais da MRS
(`Orçamento Ger. SP.xlsx` e `Plano de Manutenção 2º Trimestre - SP.xlsx`).

- **Recomendado:** deixar o repositório **privado** (GitHub → Settings → General →
  Danger Zone → *Change visibility* → Private). O Streamlit Cloud publica de repositório
  privado normalmente (ele pede permissão ao GitHub no passo 2).
- O `Orçamento Ger. SP.xlsx` é o que alimenta a aba **Financeiro** na web. Se for removido
  do repositório, o app funciona, só a aba Financeiro mostra "orçamento não carregado".

## 1. Neon — criar o banco

1. Acesse **https://console.neon.tech** e entre (GitHub ou e-mail corporativo).
2. **New Project**
   - Project name: `plano-vp`
   - Postgres version: a padrão
   - Region: **AWS South America East 1 (São Paulo)** — `sa-east-1`
   - **Create project**
3. No painel do projeto → botão **Connect**:
   - Branch `main` · Database `neondb` · Role `neondb_owner`
   - **Connection pooling: desligado** (conexão direta)
   - Copie a *connection string*. Ela vem assim:
     ```
     postgresql://neondb_owner:SENHA@ep-xxxx-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
     ```
4. Monte a URL do app trocando o começo para `postgresql+psycopg2://` e deixando só `sslmode=require`:
   ```
   postgresql+psycopg2://neondb_owner:SENHA@ep-xxxx-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require
   ```
5. (Recomendado, para não estourar a cota) **Settings → Compute**: autoscaling máximo **0,25–1 CU**
   e *scale to zero* ligado (padrão do plano Free).

> Não precisa criar tabelas: o app cria tudo sozinho na primeira conexão.
> A senha do Neon fica **só** nos Secrets do Streamlit — nunca no código nem no chat.

## 2. Streamlit Community Cloud — publicar o app

1. Acesse **https://share.streamlit.io** → *Continue with GitHub* (conta `jcopaz`).
   Se o repositório for privado, autorize o acesso quando o GitHub pedir.
2. **Create app** → *Deploy a public app from GitHub* (o "public" é a hospedagem; o acesso
   continua protegido pelo login do próprio app).
   - Repository: `jcopaz/PlanoVPSP`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: ex. `plano-vp` → `https://plano-vp.streamlit.app`
3. **Advanced settings**
   - Python version: **3.12**
   - **Secrets** — cole (com a URL do passo 1.4):
     ```toml
     [database]
     url = "postgresql+psycopg2://neondb_owner:SENHA@ep-xxxx-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require"
     ```
4. **Deploy**. A primeira instalação leva 2–5 min.
5. Abriu a tela **"Primeiro acesso — criar o administrador"**? O banco está conectado.
   Erro "Não foi possível conectar ao banco": revise a URL nos Secrets
   (App → ⋮ → Settings → Secrets) e clique em *Reboot app*.

## 3. Primeiro uso na web

1. **Criar o administrador** (sua matrícula e senha).
2. **Dados → Upload → Plano do trimestre (exports do PCM)**: `data (9).xlsx` + `Planejamento PCM.xlsx`
   → Importar (cria o 4º tri/2026).
3. **Dados → Upload → Planilha de trimestre**: `Plano de Manutenção 2º Trimestre - SP.xlsx`
   (e outros trimestres passados que tiver) → histórico.
4. **Configurações → SLA e Unidades**: preencher as metas sem SLA.
5. **Configurações → Usuários**: cadastrar cada programador (perfil *Programador* + Depto)
   e o PCM. O app mostra a **senha provisória** — envie à pessoa; ela troca no 1º acesso.
6. Mande o link `https://plano-vp.streamlit.app` e o [manual](MANUAL_USUARIO.md).

## 4. Operação

| Situação | O que fazer |
|---|---|
| Atualizar o código | `git push` na `main` → o Streamlit Cloud reinstala sozinho |
| App "dormindo" (sem uso por dias) | abrir o link e clicar em *Yes, get this app back up* |
| Esqueci a senha de admin | outro admin reseta em Configurações → Usuários; sem nenhum admin: rodar `scripts/criar_usuario.py` apontando para o Neon (abaixo) |
| Backup | Dados → Exportação → **Backup completo (.zip)** ao fechar cada trimestre |
| Trocar a senha do Neon | Neon → Roles → reset password → atualizar a URL nos Secrets → *Reboot app* |
| Ver consumo | Neon → Usage (storage e network transfer; o app usa cache por versão de dados) |

### Rodar scripts contra o Neon a partir da rede MRS

A rede da MRS só deixa passar o PostgreSQL com SSL "direto". No PowerShell:

```powershell
$env:PLANO_DB_URL = "postgresql+psycopg2://neondb_owner:SENHA@ep-xxxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&sslnegotiation=direct"
.venv\Scripts\python scripts\criar_usuario.py MATRICULA --resetar
.venv\Scripts\python scripts\carregar_no_banco.py "Plano de Manutenção 2º Trimestre - SP.xlsx"
Remove-Item Env:PLANO_DB_URL
```

> `sslnegotiation=direct` é **só para a rede MRS**. Nos Secrets do Streamlit Cloud use a URL
> sem ele (o servidor do Streamlit não está atrás do firewall da MRS).
