"""Rotas para acesso ao dicionário customizável de ENUMs e códigos."""

from __future__ import annotations

from fastapi import APIRouter

from src.dicionarios import dicionario_de_coluna, obter_dicionarios
from src.investigacao_colunas import carregar_decisoes_booleanos

router = APIRouter(tags=["Dicionários"])


@router.get("/dicionarios", summary="Retorna o dicionário completo")
async def get_dicionarios() -> dict:
    """Retorna o dicionário inteiro recarregado do disco quando necessário."""
    return obter_dicionarios()


@router.get("/dicionarios/{tabela}/{coluna}", summary="Retorna o dicionário de uma coluna")
async def get_dicionario_coluna(tabela: str, coluna: str) -> dict[str, str]:
    """Retorna o mapa de tradução de uma coluna específica."""
    return dicionario_de_coluna(tabela, coluna)


@router.get("/booleanas", summary="Retorna lista de colunas confirmadas como booleanas")
async def get_colunas_booleanas() -> list[str]:
    """Retorna as chaves ``tabela.coluna`` confirmadas manualmente como booleanas.

    O frontend usa essa lista para traduzir automaticamente ``0`` → "Não" e
    ``1`` → "Sim" nas colunas confirmadas, quando não houver tradução de ENUM
    mais específica já definida em ``dicionarios.yaml``.
    """
    decisoes = carregar_decisoes_booleanos()
    return sorted(decisoes.get("confirmadas", {}).keys())
