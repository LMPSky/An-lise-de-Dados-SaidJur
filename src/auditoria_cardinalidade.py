"""Auditoria de cobertura de tradução por cardinalidade (sem teto de 20 valores).

As duas ferramentas de descoberta já existentes (``auditar_traducoes.py`` e
``src.investigacao_pendencias.descobrir_pendencias_schema``, usada por
``investigar_pendencias.py``/``listar_traducoes_faltantes.py``) descartam por
completo qualquer coluna cujos valores distintos amostrados ultrapassem um
teto fixo pequeno (``MAX_VALORES_ENUM = 20`` na auditoria, ``limite = 20`` na
descoberta via schema). Isso é necessário para não tratar colunas de texto
livre genuíno como código/ENUM, mas tem um efeito colateral real: qualquer
coluna de código/ENUM legítima com **mais de 20 valores distintos** (ex: um
catálogo de ~40-100 tipos de documento) nunca aparece em nenhum dos dois
relatórios — fica permanentemente fora do radar, mesmo rodando ``--completo``.

Este módulo implementa uma terceira estratégia, complementar às anteriores:
em vez de buscar uma amostra de valores e descartá-la se ultrapassar o teto,
primeiro **estima a cardinalidade real da coluna** via
``COUNT(DISTINCT coluna)`` (ou uma subseleção limitada, para tabelas
colossais) e só então decide se a coluna é "categórica" (cardinalidade dentro
de uma faixa configurável, por padrão 2–500). Colunas aprovadas têm **todos**
os seus valores distintos (não apenas os primeiros 20) comparados ao
``dicionarios.yaml``, usando a mesma classificação de pendência de
``auditar_traducoes.avaliar_pendencias_enum`` (sem entrada no dicionário,
placeholder ``[valor]`` pendente, ou tradução que parece estar em inglês).

A elegibilidade de coluna reaproveita
``src.investigacao_pendencias._coluna_elegivel_para_descoberta_completa``
(mesma lista enxuta de exclusões: ``BLOB``, tipos temporais, ``id`` e colunas
sensíveis de credenciais) — ou seja, nenhum filtro adicional por nome de
coluna é aplicado aqui: a decisão de auditar ou não uma coluna depende
exclusivamente da cardinalidade observada no banco, não do nome dela.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from auditar_traducoes import avaliar_pendencias_enum
from src.db import conectar_com_timeout
from src.dicionarios import dicionario_de_coluna
from src.investigacao_pendencias import (
    ColunaTabela,
    _coluna_elegivel_para_descoberta_completa,
    _identificador,
    _linhas_estimadas_tabela,
    _pista_parece_texto_livre,
    listar_colunas_tabela,
)
from src.tabelas_grandes import (
    LIMITE_LINHAS_TABELA_COLOSSAL,
    LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
    LIMITE_SUBSELECAO_TABELA_COLOSSAL_MODO_COMPLETO,
)

ARQUIVO_AUDITORIA_CARDINALIDADE_PADRAO = "relatorio_auditoria_cardinalidade.yaml"

# Faixa padrão de cardinalidade considerada "categórica" (código/ENUM).
# O piso de 2 descarta colunas com um único valor constante (nunca precisam
# de tradução) e o teto de 500 é generoso o bastante para cobrir catálogos
# grandes (ex: tipos de documento, fases processuais) sem degenerar em texto
# livre de alta cardinalidade (nomes, descrições, timestamps formatados).
CARDINALIDADE_MINIMA_PADRAO = 2
CARDINALIDADE_MAXIMA_PADRAO = 500

# Tamanho máximo de valor individual ainda considerado rótulo curto (mesmo
# critério de `descobrir_pendencias_schema`): acima disso, mesmo com poucos
# valores distintos, provavelmente não é um código/ENUM de verdade.
_TAMANHO_MAXIMO_VALOR = 60


@dataclass
class PendenciaCardinalidade:
    """Pendência de tradução descoberta pela auditoria de cardinalidade."""

    tabela: str
    coluna: str
    cardinalidade: int
    valores_pendentes: list[dict[str, str]] = field(default_factory=list)


def _contar_valores_distintos(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    limite_subselecao: int | None = None,
    limite_minimo_subselecao: int = LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
) -> int:
    """Estima a cardinalidade de uma coluna via ``COUNT(DISTINCT ...)``.

    Para tabelas colossais, evita o ``COUNT(DISTINCT)`` na tabela inteira
    (mesmo risco de timeout já documentado em
    ``src.investigacao_pendencias._valores_distintos_coluna``) e conta sobre
    uma subseleção limitada por ``LIMIT``, com o mesmo retry decrescente até
    ``limite_minimo_subselecao`` em caso de falha.
    """
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)

    if limite_subselecao is None:
        sql = text(
            f"SELECT COUNT(DISTINCT {coluna_sql}) FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL"
        )
        with conectar_com_timeout(engine) as conn:
            resultado = conn.execute(sql).scalar()
        return int(resultado or 0)

    limite_atual = int(limite_subselecao)
    while True:
        sql = text(
            f"SELECT COUNT(DISTINCT valor) FROM ("
            f"SELECT {coluna_sql} AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"LIMIT {limite_atual}"
            f") AS amostra"
        )
        try:
            with conectar_com_timeout(engine) as conn:
                resultado = conn.execute(sql).scalar()
            return int(resultado or 0)
        except Exception:  # noqa: BLE001 - decide entre reduzir o LIMIT ou propagar
            if limite_atual <= limite_minimo_subselecao:
                raise
            limite_atual = max(limite_minimo_subselecao, limite_atual // 2)


def _coletar_valores_distintos(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    cardinalidade_maxima: int,
    limite_subselecao: int | None = None,
    limite_minimo_subselecao: int = LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
) -> list[str]:
    """Coleta todos os valores distintos de uma coluna já confirmada como categórica."""
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)
    # Pequena folga sobre a cardinalidade estimada: COUNT(DISTINCT) e a
    # consulta de valores podem divergir levemente se o banco mudar entre as
    # duas consultas (linhas inseridas/removidas concorrentemente).
    limite_valores = cardinalidade_maxima + 50

    if limite_subselecao is None:
        sql = text(
            f"SELECT DISTINCT CAST({coluna_sql} AS CHAR) AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"AND TRIM(CAST({coluna_sql} AS CHAR)) <> '' "
            f"LIMIT {limite_valores}"
        )
        with conectar_com_timeout(engine) as conn:
            return [str(row[0]).strip() for row in conn.execute(sql).fetchall()]

    limite_atual = int(limite_subselecao)
    while True:
        sql = text(
            f"SELECT DISTINCT valor FROM ("
            f"SELECT TRIM(CAST({coluna_sql} AS CHAR)) AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"LIMIT {limite_atual}"
            f") AS amostra "
            f"WHERE valor <> '' "
            f"LIMIT {limite_valores}"
        )
        try:
            with conectar_com_timeout(engine) as conn:
                return [str(row[0]).strip() for row in conn.execute(sql).fetchall()]
        except Exception:  # noqa: BLE001 - decide entre reduzir o LIMIT ou propagar
            if limite_atual <= limite_minimo_subselecao:
                raise
            limite_atual = max(limite_minimo_subselecao, limite_atual // 2)


def auditar_cobertura_por_cardinalidade(
    engine: Engine,
    *,
    cardinalidade_minima: int = CARDINALIDADE_MINIMA_PADRAO,
    cardinalidade_maxima: int = CARDINALIDADE_MAXIMA_PADRAO,
    limite_subselecao_colossal: int = LIMITE_SUBSELECAO_TABELA_COLOSSAL_MODO_COMPLETO,
) -> dict[str, Any]:
    """Audita todas as colunas elegíveis do banco por cardinalidade real.

    Retorna um relatório estruturado (pendências + resumo), no mesmo espírito
    de ``src.investigacao_pendencias.descobrir_pendencias_schema``, mas usando
    cardinalidade real (``COUNT(DISTINCT)``) em vez de nome de coluna ou teto
    fixo de amostra para decidir elegibilidade.
    """
    pendencias: list[PendenciaCardinalidade] = []
    colunas_auditadas = 0
    colunas_fora_do_intervalo = 0
    colunas_com_falha: list[dict[str, str]] = []
    tabelas_colossais: list[str] = []

    for tabela in inspect(engine).get_table_names():
        try:
            linhas_estimadas = _linhas_estimadas_tabela(engine, tabela)
        except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
            linhas_estimadas = 0
            print(f"⚠️  Falha ao estimar linhas de {tabela}, tratando como tabela normal: {exc}")

        tabela_colossal = linhas_estimadas > LIMITE_LINHAS_TABELA_COLOSSAL
        if tabela_colossal:
            tabelas_colossais.append(tabela)
            limite_subselecao = limite_subselecao_colossal
            print(
                f"ℹ️  Tabela colossal '{tabela}' (~{linhas_estimadas:,} linhas): "
                f"estimando cardinalidade sobre amostra de até {limite_subselecao:,} linhas."
            )
        else:
            limite_subselecao = None

        colunas: list[ColunaTabela] = listar_colunas_tabela(engine, tabela)
        for coluna in colunas:
            if not _coluna_elegivel_para_descoberta_completa(coluna):
                continue

            try:
                cardinalidade = _contar_valores_distintos(
                    engine, tabela, coluna.nome, limite_subselecao=limite_subselecao
                )
            except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
                colunas_com_falha.append(
                    {"tabela_coluna": f"{tabela}.{coluna.nome}", "etapa": "cardinalidade", "erro": str(exc)}
                )
                print(f"⚠️  Falha ao estimar cardinalidade de {tabela}.{coluna.nome}: {exc}")
                continue

            if cardinalidade < cardinalidade_minima or cardinalidade > cardinalidade_maxima:
                colunas_fora_do_intervalo += 1
                continue

            colunas_auditadas += 1
            try:
                valores = _coletar_valores_distintos(
                    engine,
                    tabela,
                    coluna.nome,
                    cardinalidade_maxima=cardinalidade,
                    limite_subselecao=limite_subselecao,
                )
            except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
                colunas_com_falha.append(
                    {"tabela_coluna": f"{tabela}.{coluna.nome}", "etapa": "valores", "erro": str(exc)}
                )
                print(f"⚠️  Falha ao coletar valores de {tabela}.{coluna.nome}: {exc}")
                continue

            valores_curtos = [
                valor
                for valor in dict.fromkeys(valores)
                if len(valor) <= _TAMANHO_MAXIMO_VALOR and not _pista_parece_texto_livre(valor)
            ]
            if not valores_curtos:
                continue

            dicionario_coluna = dicionario_de_coluna(tabela, coluna.nome)
            valores_pendentes = avaliar_pendencias_enum(valores_curtos, dicionario_coluna)
            if valores_pendentes:
                pendencias.append(
                    PendenciaCardinalidade(
                        tabela=tabela,
                        coluna=coluna.nome,
                        cardinalidade=cardinalidade,
                        valores_pendentes=valores_pendentes,
                    )
                )

    pendencias.sort(key=lambda p: (p.tabela, p.coluna))

    resumo = {
        "colunas_auditadas": colunas_auditadas,
        "colunas_fora_do_intervalo_cardinalidade": colunas_fora_do_intervalo,
        "colunas_com_falha": colunas_com_falha,
        "total_colunas_com_falha": len(colunas_com_falha),
        "tabelas_colossais_amostradas": tabelas_colossais,
        "total_tabelas_colossais_amostradas": len(tabelas_colossais),
        "total_colunas_com_pendencia": len(pendencias),
        "total_valores_pendentes": sum(len(p.valores_pendentes) for p in pendencias),
        "cardinalidade_minima": cardinalidade_minima,
        "cardinalidade_maxima": cardinalidade_maxima,
    }

    return {
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "resumo": resumo,
        "pendencias": [
            {
                "tabela": p.tabela,
                "coluna": p.coluna,
                "cardinalidade": p.cardinalidade,
                "valores_pendentes": p.valores_pendentes,
            }
            for p in pendencias
        ],
    }
