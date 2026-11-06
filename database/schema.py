# database/schema.py — Tabelas do Plano de Manutenção VP (SQLAlchemy Core)
#
# O mesmo schema roda em SQLite (local, arquivo dados/plano.db) e em
# PostgreSQL (Neon, produção) — só muda a URL (ver database/client.py).
# Tabelas são criadas automaticamente na 1ª conexão (criar_tabelas), então
# não há script SQL para rodar à mão. Mudança de schema = bump MAJOR em
# core/versao.py + nota em docs/DOCUMENTACAO_TECNICA.md.
#
# Modelo de dados (1 trimestre = 1 linha em `trimestres`; tudo pendura nele):
#
#   trimestres ─┬─< pesos         (peso de cada meta por Depto — export do PCM)
#               ├─< plano         (visão congelada do PCM, 1 linha por dia/meta)
#               └─< lancamentos   (execução lançada pelos programadores)
#
#   lancamentos_copia  cópia automática dos lançamentos antes de cada substituição
#                      por upload, exclusão ou restauração (restaurável pelo admin)
#
#   metas_catalogo  Unidade + SLA (produção esperada da equipe/dia) por Depto×Meta
#   listas          opções dos menus (Equipe por Depto, Justificativa, Status...)
#   coordenacoes    de-para Depto → Coordenação → Centro de Custo
#   config          parâmetros chave/valor (faixas de risco, orçamento...)
#   usuarios        login próprio (senha PBKDF2) + perfil + Depto delegado
#   auditoria       quem fez o quê (lançamentos, uploads, configurações)

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer,
                        MetaData, String, Table, Text, UniqueConstraint, func)

metadata = MetaData()


# region ====================== SESSÃO 1: Trimestre e seus dados ======================

trimestres = Table(
    "trimestres", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ano", Integer, nullable=False),
    Column("trimestre", Integer, nullable=False),
    Column("semana_inicio", Integer, nullable=False),   # WEEKNUM do Excel
    Column("semana_fim", Integer, nullable=False),
    Column("status", String(10), nullable=False, default="aberto"),   # aberto | fechado
    Column("observacao", Text),
    Column("criado_em", DateTime, server_default=func.now()),
    Column("atualizado_em", DateTime, server_default=func.now()),
    UniqueConstraint("ano", "trimestre", name="uq_trimestre"),
)

pesos = Table(
    "pesos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trimestre_id", Integer, ForeignKey("trimestres.id", ondelete="CASCADE"), nullable=False),
    Column("depto", String(20), nullable=False),
    Column("grupo", String(80)),
    Column("meta", String(120), nullable=False),
    Column("peso", Float, nullable=False, default=0.0),
    UniqueConstraint("trimestre_id", "depto", "meta", name="uq_peso"),
)

plano = Table(
    "plano", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trimestre_id", Integer, ForeignKey("trimestres.id", ondelete="CASCADE"), nullable=False),
    Column("depto", String(20), nullable=False),
    Column("data", Date, nullable=False),
    Column("meta", String(120), nullable=False),
    Column("n_material", String(40)),
    Column("equipe", String(60)),
    Column("ativo", String(120)),
    Column("equipamento", String(120)),
    Column("tipo_material", String(20)),
    Column("qtd", Float, nullable=False, default=0.0),
    Column("observacao", Text),
)
Index("ix_plano_tri", plano.c.trimestre_id)

lancamentos = Table(
    "lancamentos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trimestre_id", Integer, ForeignKey("trimestres.id", ondelete="CASCADE"), nullable=False),
    Column("depto", String(20), nullable=False),
    Column("data", Date, nullable=False),
    Column("meta", String(120), nullable=False),
    Column("n_material", String(40)),
    Column("equipe", String(60)),
    Column("ativo", String(120)),
    Column("tipo_material", String(20)),
    Column("qtd_prog", Float, default=0.0),
    Column("qtd_real", Float, default=0.0),
    Column("no_plano", String(3)),          # Sim | Não
    Column("justificativa", Text),           # Motivo de Perda do PCM passa de 80 caracteres
    Column("observacao", Text),
    Column("plano_acao", Text),
    Column("responsavel", String(80)),
    Column("prazo", Date),
    Column("status", String(30)),
    Column("programador", String(80)),
    Column("origem", String(10)),            # upload | app (digitado na tela de Lançamentos)
    Column("criado_por", String(60)),
    Column("criado_em", DateTime, server_default=func.now()),
    Column("alterado_por", String(60)),
    Column("alterado_em", DateTime),
)
Index("ix_lanc_tri", lancamentos.c.trimestre_id)

# Sem FK para trimestres: a cópia sobrevive à exclusão do trimestre.
lancamentos_copia = Table(
    "lancamentos_copia", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ano", Integer, nullable=False),
    Column("trimestre", Integer, nullable=False),
    Column("quando", DateTime, nullable=False),
    Column("usuario", String(60)),
    Column("motivo", String(40)),             # upload | excluir trimestre | restaurar
    Column("linhas", Integer, nullable=False),
    Column("dados", Text, nullable=False),    # JSON com todas as linhas
)

# endregion


# region ====================== SESSÃO 2: Cadastros e configuração ======================

metas_catalogo = Table(
    "metas_catalogo", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("depto", String(20), nullable=False),
    Column("meta", String(120), nullable=False),
    Column("unidade", String(10)),
    Column("sla", Float),                    # produção esperada da equipe por dia
    UniqueConstraint("depto", "meta", name="uq_catalogo"),
)

listas = Table(
    "listas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tipo", String(30), nullable=False),     # Equipe | Ativo | Justificativa | Status | Tipo Material | Grupo
    Column("valor", String(120), nullable=False),
    Column("depto", String(20), nullable=False, default=""),   # "" = vale para todos
    Column("ativo", Boolean, nullable=False, default=True),
    UniqueConstraint("tipo", "valor", "depto", name="uq_lista"),
)

coordenacoes = Table(
    "coordenacoes", metadata,
    Column("depto", String(20), primary_key=True),
    Column("coordenacao", String(60), nullable=False),
    Column("centro_custo", String(20)),
    Column("entra_gerencia", Boolean, nullable=False, default=True),
)

config = Table(
    "config", metadata,
    Column("chave", String(60), primary_key=True),
    Column("valor", Text),
)

# endregion


# region ====================== SESSÃO 3: Acesso e auditoria ======================

usuarios = Table(
    "usuarios", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("login", String(60), nullable=False, unique=True),   # matrícula
    Column("nome", String(120), nullable=False),
    Column("email", String(120)),
    Column("senha_hash", String(255), nullable=False),
    Column("perfil", String(20), nullable=False, default="leitor"),  # admin | pcm | programador | leitor
    Column("depto", String(20)),             # NULL = todos os Deptos
    Column("ativo", Boolean, nullable=False, default=True),
    Column("deve_trocar_senha", Boolean, nullable=False, default=True),
    Column("criado_em", DateTime, server_default=func.now()),
    Column("ultimo_login", DateTime),
)

auditoria = Table(
    "auditoria", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("quando", DateTime, server_default=func.now()),
    Column("usuario", String(60)),
    Column("acao", String(40), nullable=False),
    Column("tabela", String(40)),
    Column("registro_id", Integer),
    Column("detalhe", Text),
)

# endregion


# region ====================== SESSÃO 4: De-para banco ↔ planilha (modelo v3) ======================
# Nomes das colunas do banco (snake_case) para os cabeçalhos do modelo de
# planilha (core/modelo.py). Usado na carga, no upload e na exportação.

MAPA_PESOS = {"depto": "Depto", "grupo": "Grupo", "meta": "Descrição Meta", "peso": "Peso"}

MAPA_PLANO = {
    "depto": "Depto", "data": "Data Planejada", "meta": "Descrição Meta", "n_material": "Nº Material",
    "equipe": "Equipe", "ativo": "Ativo", "equipamento": "Equipamento", "tipo_material": "Tipo Material",
    "qtd": "Quantidade Programada", "observacao": "Observação",
}

MAPA_LANC = {
    "depto": "Depto", "data": "Data", "meta": "Descrição Meta", "n_material": "Nº Material",
    "equipe": "Equipe", "ativo": "Ativo", "tipo_material": "Tipo Material",
    "qtd_prog": "Quantidade Programada", "qtd_real": "Quantidade Realizada", "no_plano": "No Plano",
    "justificativa": "Justificativa", "observacao": "Observação", "plano_acao": "Plano de Ação",
    "responsavel": "Responsável", "prazo": "Prazo", "status": "Status", "programador": "Programador",
}

# endregion


def criar_tabelas(engine) -> None:
    """Cria as tabelas que ainda não existem (idempotente)."""
    metadata.create_all(engine)
    _migrar(engine)


def _migrar(engine) -> None:
    """Ajustes em tabelas que já existiam (create_all não altera colunas). Idempotente."""
    from sqlalchemy import inspect, text
    cols = {c["name"]: c for c in inspect(engine).get_columns("lancamentos")}
    with engine.begin() as conn:
        if "origem" not in cols:
            conn.execute(text("ALTER TABLE lancamentos ADD COLUMN origem VARCHAR(10)"))
        if engine.dialect.name == "postgresql" and getattr(cols.get("justificativa", {}).get("type"), "length", None):
            conn.execute(text("ALTER TABLE lancamentos ALTER COLUMN justificativa TYPE TEXT"))
