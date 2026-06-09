"""Rota para resolução de labels de chaves estrangeiras em lote."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.db import resolver_labels, tabelas_validas, colunas_validas

router = APIRouter(tags=["Labels"])


class ItemResolucao(BaseModel):
    tabela: str
    coluna_chave: str = "id"
    ids: list[int | str]


class BodyResolucao(BaseModel):
    resolucoes: list[ItemResolucao]


@router.post("/labels/resolver", summary="Resolve labels de IDs em lote")
async def post_resolver_labels(body: BodyResolucao, request: Request) -> dict[str, Any]:
    """Recebe pedidos de resolução e devolve mapa de id → label por tabela."""
    engine = request.app.state.engine
    validas = tabelas_validas(engine)

    for item in body.resolucoes:
        if item.tabela not in validas:
            raise HTTPException(
                status_code=404,
                detail=f"Tabela '{item.tabela}' não encontrada.",
            )
        cols = colunas_validas(engine, item.tabela)
        if item.coluna_chave not in cols:
            raise HTTPException(
                status_code=400,
                detail=f"Coluna '{item.coluna_chave}' não existe na tabela '{item.tabela}'.",
            )

    resolucoes_dict = [item.model_dump() for item in body.resolucoes]
    return resolver_labels(engine, resolucoes_dict)
