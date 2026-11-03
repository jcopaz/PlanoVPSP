# -*- coding: utf-8 -*-
"""Layout do modelo de planilha do trimestre (formato v3, sem fórmulas).

Fonte única das abas/colunas usadas por:
    scripts/gerar_modelo.py              -> gera o modelo em branco e o exemplo
    scripts/converter_planilha_antiga.py -> migra o workbook antigo (Diário)
    core/dados.py                        -> lê o modelo e calcula pesos/semana

Quem preenche o quê:
    Pesos        -> PCM, 1x por trimestre (peso relativo de cada meta por Depto)
    Plano_PCM    -> 1 pessoa, no início do trimestre (cópia da planilha do PCM)
    Lancamentos  -> programadores, ao longo do trimestre (execução + extra plano)
    Listas       -> opções dos menus suspensos (equipes, justificativas...)

Tudo que antes era fórmula (Semana, Coordenação, Chave Peso, Peso Unitário,
Peso Planejado/Realizado/Extra Linha, Plano Trimestral) é calculado no Python.
"""
from __future__ import annotations

ABA_LEIAME = "LEIA-ME"
ABA_PESOS = "Pesos"
ABA_PLANO = "Plano_PCM"
ABA_LANC = "Lancamentos"
ABA_LISTAS = "Listas"

COLS_PESOS = ["Depto", "Grupo", "Descrição Meta", "Peso", "Unidade", "SLA"]

COLS_PLANO = ["Depto", "Data Planejada", "Descrição Meta", "Nº Material", "Equipe",
              "Ativo", "Equipamento", "Tipo Material", "Quantidade Programada", "Observação"]

COLS_LANC = ["Depto", "Data", "Descrição Meta", "Nº Material", "Equipe", "Ativo",
             "Tipo Material", "Quantidade Programada", "Quantidade Realizada", "No Plano",
             "Justificativa", "Observação", "Plano de Ação", "Responsável", "Prazo",
             "Status", "Programador"]

# Listas (aba Listas): coluna -> valores padrão
LISTAS_PADRAO = {
    "Depto": ["V.SP.IPA", "V.SP.IPG", "V.SP.PJU"],
    "Equipe": [],
    "Justificativa": [
        "Erro de programação", "Baixa produtividade", "Mau tempo", "Intervalo não concedido",
        "Quebra de equipamento", "Falta de equipamento", "Baixo efetivo da equipe",
        "Intervalo concedido fora de faixa", "Problemas no deslocamento",
        "Problemas com material", "Falha de comunicação CCO", "Avaria EGP",
        "Paralisação da equipe", "Adiantado", "Outros",
    ],
    "Tipo Material": ["Novo", "Usado"],
    "Sim/Não": ["Sim", "Não"],
    "Status": ["Aberto", "Em andamento", "Concluído"],
    "Grupo": ["AMV/Travessão", "Correção Geométrica", "Drenagem", "Manutenção Preventiva",
              "Manutenção Corretiva", "Recolhimento / Descarga", "Saneamento Vegetal",
              "Serviços Extras"],
}

# Menus suspensos: (aba, coluna) -> coluna da aba Listas (ou "Pesos:Descrição Meta")
VALIDACOES = {
    (ABA_PESOS, "Depto"): "Depto",
    (ABA_PESOS, "Grupo"): "Grupo",
    (ABA_PLANO, "Depto"): "Depto",
    (ABA_PLANO, "Descrição Meta"): "Pesos:Descrição Meta",
    (ABA_PLANO, "Equipe"): "Equipe",
    (ABA_PLANO, "Tipo Material"): "Tipo Material",
    (ABA_LANC, "Depto"): "Depto",
    (ABA_LANC, "Descrição Meta"): "Pesos:Descrição Meta",
    (ABA_LANC, "Equipe"): "Equipe",
    (ABA_LANC, "Tipo Material"): "Tipo Material",
    (ABA_LANC, "No Plano"): "Sim/Não",
    (ABA_LANC, "Justificativa"): "Justificativa",
    (ABA_LANC, "Status"): "Status",
}

ABAS_OBRIGATORIAS = (ABA_PESOS, ABA_PLANO, ABA_LANC)


def eh_modelo(nomes_abas) -> bool:
    """True se o workbook está no formato v3 (Pesos + Plano_PCM + Lancamentos)."""
    nomes = {str(n).strip().lower() for n in nomes_abas}
    return all(a.lower() in nomes for a in ABAS_OBRIGATORIAS)
