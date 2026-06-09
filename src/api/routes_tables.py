"""Rotas para listagem de tabelas, colunas e chaves estrangeiras."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.db import (
    listar_tabelas,
    listar_colunas,
    listar_chaves_estrangeiras,
    tabelas_validas,
    fks_inferidas,
)

router = APIRouter(tags=["Tabelas"])


@router.get("/tabelas", summary="Lista todas as tabelas do banco")
async def get_tabelas(request: Request) -> list[dict]:
    """Retorna todas as tabelas do banco com contagem aproximada e tamanho."""
    engine = request.app.state.engine
    try:
        return listar_tabelas(engine)
    except Exception as exc:
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

    validas = tabelas_validas(engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return listar_colunas(engine, nome)


@router.get(
    "/tabelas/{nome}/fks",
    summary="Lista as foreign keys de uma tabela",
)
async def get_fks(nome: str, request: Request) -> list[dict]:
    """Retorna lista de FKs da tabela."""
    engine = request.app.state.engine

    validas = tabelas_validas(engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return listar_chaves_estrangeiras(engine, nome)


@router.get(
    "/tabelas/{nome}/fks_inferidas",
    summary="Lista FKs implícitas (heurísticas) de uma tabela",
)
async def get_fks_inferidas(nome: str, request: Request) -> list[dict]:
    """Retorna FKs detectadas por heurística de nome/tipo de coluna."""
    engine = request.app.state.engine

    validas = tabelas_validas(engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return fks_inferidas(engine, nome)
