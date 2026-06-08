"""Rota de estatísticas rápidas de coluna."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.db import colunas_validas, estatisticas_coluna, tabelas_validas

router = APIRouter(tags=["Estatísticas"])


@router.get(
    "/tabelas/{nome}/colunas/{coluna}/stats",
    summary="Estatísticas rápidas de uma coluna",
)
async def get_stats_coluna(nome: str, coluna: str, request: Request) -> dict:
    engine = request.app.state.engine

    if nome not in tabelas_validas(engine):
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    if coluna not in colunas_validas(engine, nome):
        raise HTTPException(
            status_code=404,
            detail=f"Coluna '{coluna}' não encontrada na tabela '{nome}'.",
        )

    try:
        return estatisticas_coluna(engine, nome, coluna)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao calcular estatísticas: {exc}") from exc
