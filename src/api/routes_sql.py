"""Rota SQL customizada (somente leitura)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.db import executar_sql_somente_leitura

router = APIRouter(tags=["SQL"])
logger = logging.getLogger("saidjur.sql")


class SQLPayload(BaseModel):
    query: str = Field(min_length=1)


@router.post("/sql", summary="Executa query SQL somente leitura")
async def executar_sql(payload: SQLPayload, request: Request) -> dict[str, Any]:
    engine = request.app.state.engine
    try:
        return executar_sql_somente_leitura(
            engine,
            query=payload.query,
            limite=5000,
            timeout_segundos=30,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao executar SQL")
        raise HTTPException(status_code=500, detail=f"Falha ao executar SQL: {exc}") from exc
