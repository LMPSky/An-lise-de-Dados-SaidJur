"""Rota para resolução de labels de chaves estrangeiras em lote."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.db import resolver_labels, tabelas_validas, colunas_validas

router = APIRouter(tags=["Labels"])


class ItemResolucao(BaseModel):
    tabela: str
    coluna_chave: str = "id"
    ids: list[int | str]


class BodyResolucao(BaseModel):
    resolucoes: list[ItemResolucao]


def _resolver_labels_sincrono(engine, resolucoes: list[ItemResolucao]) -> dict[str, Any]:
    """Valida tabelas/colunas e resolve os labels — tudo síncrono/bloqueante,
    por isso deve rodar fora do event loop (ver run_in_threadpool abaixo)."""
    validas = tabelas_validas(engine)

    for item in resolucoes:
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

    resolucoes_dict = [item.model_dump() for item in resolucoes]
    return resolver_labels(engine, resolucoes_dict)


@router.post("/labels/resolver", summary="Resolve labels de IDs em lote")
async def post_resolver_labels(body: BodyResolucao, request: Request) -> dict[str, Any]:
    """Recebe pedidos de resolução e devolve mapa de id → label por tabela."""
    engine = request.app.state.engine
    return await run_in_threadpool(_resolver_labels_sincrono, engine, body.resolucoes)
