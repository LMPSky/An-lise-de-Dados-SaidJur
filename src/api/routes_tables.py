"""Rotas para listagem de tabelas, colunas e chaves estrangeiras."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.db import (
    executar_com_retry_db,
    listar_tabelas,
    listar_colunas,
    listar_chaves_estrangeiras,
    tabelas_validas,
    fks_inferidas,
)

router = APIRouter(tags=["Tabelas"])
logger = logging.getLogger("saidjur.tabelas")


# Todas as rotas abaixo chamam funções síncronas de src.db (bloqueantes, I/O de
# rede com o MySQL). Como o Uvicorn roda um único processo/event loop por
# padrão, uma chamada bloqueante direta dentro de um handler "async def"
# congela o servidor inteiro para TODOS os clientes conectados até ela
# terminar — por isso cada handler delega o trabalho de banco para
# run_in_threadpool, liberando o event loop para atender outras requisições
# em paralelo.


@router.get("/tabelas", summary="Lista todas as tabelas do banco")
async def get_tabelas(request: Request) -> list[dict]:
    """Retorna todas as tabelas do banco com contagem aproximada e tamanho."""
    engine = request.app.state.engine
    try:
        return await run_in_threadpool(
            executar_com_retry_db,
            lambda: listar_tabelas(engine),
            logger_retry=logger,
            descricao="Listagem de tabelas",
        )
    except Exception as exc:
        logger.exception("Falha ao listar tabelas")
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível conectar ao banco de dados: {exc}",
        ) from exc


@router.get(
    "/tabelas/{nome}/colunas",
    summary="Lista as colunas de uma tabela",
)
async def get_colunas(nome: str, request: Request) -> list[dict]:
    """Retorna as colunas de uma tabela com tipo, nulidade e chave."""
    engine = request.app.state.engine

    validas = await run_in_threadpool(tabelas_validas, engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return await run_in_threadpool(listar_colunas, engine, nome)


@router.get(
    "/tabelas/{nome}/fks",
    summary="Lista as foreign keys de uma tabela",
)
async def get_fks(nome: str, request: Request) -> list[dict]:
    """Retorna lista de FKs da tabela."""
    engine = request.app.state.engine

    validas = await run_in_threadpool(tabelas_validas, engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return await run_in_threadpool(listar_chaves_estrangeiras, engine, nome)


@router.get(
    "/tabelas/{nome}/fks_inferidas",
    summary="Lista FKs implícitas (heurísticas) de uma tabela",
)
async def get_fks_inferidas(nome: str, request: Request) -> list[dict]:
    """Retorna FKs detectadas por heurística de nome/tipo de coluna."""
    engine = request.app.state.engine

    validas = await run_in_threadpool(tabelas_validas, engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return await run_in_threadpool(fks_inferidas, engine, nome)
