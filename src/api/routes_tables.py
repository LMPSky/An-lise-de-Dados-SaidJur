"""Rotas para listagem de tabelas e colunas do banco de dados."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.db import listar_tabelas, listar_colunas, tabelas_validas

router = APIRouter(tags=["Tabelas"])


@router.get("/tabelas", summary="Lista todas as tabelas do banco")
async def get_tabelas(request: Request) -> list[dict]:
    """
    Retorna todas as tabelas do banco com contagem aproximada de registros e tamanho.

    Resposta: [{nome, linhas_aprox, tamanho_mb}]
    """
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
    """
    Retorna as colunas de uma tabela com tipo, nulidade e chave.

    Resposta: [{nome, tipo, nulo, chave}]
    """
    engine = request.app.state.engine

    # Valida nome da tabela contra whitelist do banco (evita SQL injection em ORDER BY)
    validas = tabelas_validas(engine)
    if nome not in validas:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    return listar_colunas(engine, nome)
