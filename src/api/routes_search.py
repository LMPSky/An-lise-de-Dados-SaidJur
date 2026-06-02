"""Rota de busca global: pesquisa texto em todas as colunas textuais do banco."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config import CONFIG
from src.db import listar_tabelas, colunas_texto

router = APIRouter(tags=["Busca"])
logger = logging.getLogger("saidjur.busca")


def _buscar_em_tabela(
    engine: Engine,
    nome_tabela: str,
    colunas: list[str],
    termo: str,
    limite: int,
    timeout: int,
) -> list[dict[str, Any]]:
    """
    Executa busca LIKE em todas as colunas textuais de uma tabela.

    Retorna lista de resultados agrupados por coluna.
    """
    resultados: list[dict[str, Any]] = []

    from sqlalchemy import MetaData, Table, select
    meta = MetaData()
    try:
        tbl = Table(nome_tabela, meta, autoload_with=engine)
    except Exception as exc:
        logger.warning("Erro ao refletir tabela '%s': %s", nome_tabela, exc)
        return resultados

    for coluna in colunas:
        try:
            col = tbl.c[coluna]
            stmt = select(tbl).where(col.like(f"%{termo}%")).limit(limite)

            with engine.connect() as conn:
                # SET SESSION max_execution_time define timeout em ms (MySQL 5.7.4+).
                # Silencia o erro em bancos que não suportam esse comando (ex: SQLite em testes).
                try:
                    conn.execute(text(f"SET SESSION max_execution_time={timeout * 1000}"))
                except Exception:
                    pass
                resultado = conn.execute(stmt)
                chaves = list(resultado.keys())
                linhas = [dict(zip(chaves, row)) for row in resultado]
                if linhas:
                    resultados.append(
                        {"tabela": nome_tabela, "coluna": coluna, "registros": linhas}
                    )
        except Exception as exc:
            logger.warning(
                "Erro ao buscar em %s.%s: %s", nome_tabela, coluna, exc
            )

    return resultados


@router.get(
    "/busca",
    summary="Busca global por texto em todas as tabelas",
)
async def busca_global(
    request: Request,
    q: str = Query(min_length=1, description="Texto para pesquisar"),
    limite: int = Query(default=None, ge=1, le=500, description="Máximo de registros por coluna"),
) -> list[dict[str, Any]]:
    """
    Pesquisa o texto em todas as colunas textuais de todas as tabelas.

    - Busca com LIKE %texto% em colunas do tipo CHAR, VARCHAR, TEXT, JSON etc.
    - Execução paralela por tabela (até 4 threads simultâneas)
    - Timeout configurável por query (padrão: 10 segundos por coluna)

    Resposta: [{tabela, coluna, registros: [...]}]
    """
    engine = request.app.state.engine

    cfg_busca = CONFIG.get("busca", {})
    timeout = int(cfg_busca.get("timeout_segundos", 10))
    limite_efetivo = limite or int(cfg_busca.get("limite_padrao", 100))

    if len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="O termo de busca não pode ser vazio.")

    # Descobre tabelas e suas colunas textuais
    try:
        tabelas = listar_tabelas(engine)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Não foi possível acessar o banco: {exc}"
        ) from exc

    tabelas_com_colunas = [
        (t["nome"], colunas_texto(engine, t["nome"]))
        for t in tabelas
        if colunas_texto(engine, t["nome"])
    ]

    if not tabelas_com_colunas:
        return []

    logger.info("Busca global: '%s' em %d tabelas", q, len(tabelas_com_colunas))

    # Executa buscas em paralelo (thread pool — operações bloqueantes de banco)
    todos_resultados: list[dict[str, Any]] = []

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futuros = {
            executor.submit(
                _buscar_em_tabela, engine, nome, colunas, q, limite_efetivo, timeout
            ): nome
            for nome, colunas in tabelas_com_colunas
        }
        for futuro in as_completed(futuros):
            try:
                todos_resultados.extend(futuro.result())
            except Exception as exc:
                tabela = futuros[futuro]
                logger.warning("Falha na busca em tabela '%s': %s", tabela, exc)

    logger.info("Busca '%s' retornou %d grupos de resultados", q, len(todos_resultados))
    return todos_resultados
