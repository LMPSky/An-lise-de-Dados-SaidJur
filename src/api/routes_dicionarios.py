"""Rotas para acesso ao dicionário customizável de ENUMs e códigos."""

from __future__ import annotations

from fastapi import APIRouter

from src.dicionarios import dicionario_de_coluna, obter_dicionarios
from src.investigacao_colunas import lista_colunas_booleanas_confirmadas

router = APIRouter(tags=["Dicionários"])


@router.get("/dicionarios", summary="Retorna o dicionário completo")
async def get_dicionarios() -> dict:
    """Retorna o dicionário inteiro recarregado do disco quando necessário."""
    return obter_dicionarios()


@router.get("/dicionarios/booleanas", summary="Retorna colunas confirmadas como booleanas")
async def get_colunas_booleanas() -> list[dict]:
    """Retorna a lista de colunas confirmadas como booleanas pelo revisor.

    Cada item contém ``tabela`` e ``coluna``.  Quando o arquivo de decisões
    ainda não foi gerado, retorna lista vazia (sem erro).
    """
    return lista_colunas_booleanas_confirmadas()


@router.get("/dicionarios/{tabela}/{coluna}", summary="Retorna o dicionário de uma coluna")
async def get_dicionario_coluna(tabela: str, coluna: str) -> dict[str, str]:
    """Retorna o mapa de tradução de uma coluna específica."""
    return dicionario_de_coluna(tabela, coluna)
