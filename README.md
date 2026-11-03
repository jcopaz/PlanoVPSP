# 🚂 Plano VP — Plano de Manutenção da Via Permanente

Aplicação web (Streamlit) para acompanhar o **plano de manutenção trimestral** da
Via Permanente: a curva planejada pelo PCM (visão congelada) contra o que as
equipes executaram (lançado pelos programadores), por **Gerência** e por
**Coordenação**, com **histórico** de trimestres e anos.

| Tela | Para quê | Quem |
|---|---|---|
| **Login** | acesso por matrícula e senha (perfis admin, PCM, programador, leitura) | todos |
| **Dashboard** | Resumo · Gerencial · Por Coordenação · Financeiro (OPEX) · Evolução | todos |
| **Lançamentos** | lançar e corrigir atividades linha a linha (mesmas colunas do Excel) | programador, PCM, admin |
| **Dados** | upload do plano do PCM e de trimestres passados; exportação em Excel (backup) | upload: PCM/admin · exportar: todos |
| **Configurações** | SLA por Depto, equipes, listas, coordenações, trimestres, parâmetros, usuários | conforme perfil |

📘 **Documentação:** [docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md) (como usar) ·
[docs/PUBLICACAO.md](docs/PUBLICACAO.md) (Neon + Streamlit Cloud, passo a passo) ·
[docs/DOCUMENTACAO_TECNICA.md](docs/DOCUMENTACAO_TECNICA.md) (como funciona e como manter).
Versão e histórico de mudanças: [core/versao.py](core/versao.py).

---

## Rodar no computador (Windows)

Duplo clique em **`Abrir_Dashboard.bat`** — ou:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Sem configurar nada, o banco é um arquivo **SQLite** em `dados/plano.db`
(pasta fora do Git). No **primeiro acesso** a tela pede para criar o
administrador. Perdeu o acesso? `python scripts/criar_usuario.py LOGIN --resetar`.

## Início de cada trimestre (1 pessoa do PCM)

**Dados → Upload → Plano do trimestre (exports do PCM)**, enviando:

1. o export de pesos (ex.: `data (9).xlsx`) → coluna **Peso Item Redist**;
2. o **Planejamento PCM** (visão congelada, plano por dia) → curva planejada.

O trimestre é lido do rodapé do export (`Tri/Ano é Tri 4/26`). Reimportar troca o
plano e **mantém os lançamentos**. Depois, os programadores lançam em **Lançamentos**.

## Histórico

**Dados → Upload → Planilha de trimestre** aceita a planilha antiga (Diário + Planilha
de Peso), o modelo v3 e os backups exportados pelo próprio app. Para vários arquivos
de uma vez: `python scripts/carregar_no_banco.py arquivo1.xlsx arquivo2.xlsx`.

## Publicar na web (Hugging Face Spaces + Neon)

Passo a passo completo: [docs/PUBLICACAO.md](docs/PUBLICACAO.md) — hoje o app roda no
**Hugging Face Spaces** (Dockerfile + envio automático pelo GitHub Actions). Resumo da
alternativa Streamlit Cloud:

1. Crie um projeto no **Neon** (região São Paulo) e copie a connection string.
2. Em share.streamlit.io → *New app* → repositório `jcopaz/PlanoVPSP`, arquivo `app.py`.
3. Em *Settings → Secrets* cole (modelo em [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example)):
   ```toml
   [database]
   url = "postgresql+psycopg2://USUARIO:SENHA@HOST/neondb?sslmode=require&sslnegotiation=direct"
   ```
4. Abra o app, crie o administrador e carregue os trimestres (Dados → Upload).

As tabelas são criadas sozinhas na primeira conexão. **Dados reais nunca vão para o
GitHub** (`dados/`, exports do PCM e `secrets.toml` estão no `.gitignore`).

## Estrutura

```
app.py              roteador: login → troca de senha → menu → tela
auth/               login, sessão, senha (PBKDF2), permissões por perfil
database/           conexão (SQLite/Postgres), tabelas, consultas
core/               regras de negócio — cálculo das curvas, pesos, OPEX, Excel, PCM
modules/            telas: home (menu), dashboard, lancamentos, dados, configuracoes
scripts/            criar_usuario, carregar_no_banco, importar_plano_pcm, gerar_modelo, ...
modelos/            planilha modelo (em branco) e exemplo com dados fictícios
docs/               manual do usuário e documentação técnica
```
