"""Rota da tela inicial (dashboard)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.db import dados_dashboard, executar_com_retry_db

router = APIRouter(tags=["Dashboard"])
logger = logging.getLogger("saidjur.dashboard")


@router.get("/dashboard", summary="Dados agregados para a tela inicial")
async def get_dashboard(request: Request) -> dict:
    engine = request.app.state.engine
    try:
        return executar_com_retry_db(
            lambda: dados_dashboard(engine),
            logger_retry=logger,
            descricao="Montagem do dashboard",
        )
    except Exception as exc:
        logger.exception("Falha ao montar o dashboard")
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível montar o dashboard: {exc}",
        ) from exc
