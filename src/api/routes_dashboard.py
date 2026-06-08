"""Rota da tela inicial (dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.db import dados_dashboard

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", summary="Dados agregados para a tela inicial")
async def get_dashboard(request: Request) -> dict:
    engine = request.app.state.engine
    try:
        return dados_dashboard(engine)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível montar o dashboard: {exc}",
        ) from exc
