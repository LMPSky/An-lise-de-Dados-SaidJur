"""Rotas para acesso ao dicionário customizável de ENUMs e códigos."""

from __future__ import annotations

from fastapi import APIRouter

from src.dicionarios import dicionario_de_coluna, obter_dicionarios

router = APIRouter(tags=["Dicionários"])


@router.get("/dicionarios", summary="Retorna o dicionário completo")
async def get_dicionarios() -> dict:
    """Retorna o dicionário inteiro recarregado do disco quando necessário."""
    return obter_dicionarios()


@router.get("/dicionarios/{tabela}/{coluna}", summary="Retorna o dicionário de uma coluna")
async def get_dicionario_coluna(tabela: str, coluna: str) -> dict[str, str]:
    """Retorna o mapa de tradução de uma coluna específica."""
    return dicionario_de_coluna(tabela, coluna)
