# Migrações de schema

Tabelas NOVAS são criadas sozinhas (`database/schema.py::criar_tabelas`).
Mudança em tabela EXISTENTE (coluna nova, tipo, índice) precisa de SQL manual:

1. crie aqui `AAAA-MM-DD_descricao.sql` com o `ALTER TABLE` (PostgreSQL);
2. rode no Neon (SQL Editor) e, se usar, no SQLite local;
3. atualize `database/schema.py` e suba MAJOR em `core/versao.py`.

Nenhuma migração até a v3.0.0.
