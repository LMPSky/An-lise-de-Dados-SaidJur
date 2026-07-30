"""Rota que expõe o dicionário de tradução de nomes de colunas para o frontend."""

from __future__ import annotations

from fastapi import APIRouter

from src.traducoes_colunas import TRADUCOES_COLUNAS

router = APIRouter(tags=["Traduções"])


@router.get(
    "/traducoes/colunas",
    summary="Retorna o dicionário de tradução de nomes de colunas",
    response_model=dict[str, str],
)
async def get_traducoes_colunas() -> dict[str, str]:
    """Retorna o mapa canônico coluna → nome em português.

    O frontend usa este endpoint para traduzir nomes técnicos de colunas,
    evitando que a tabela de traduções seja duplicada em vários arquivos.
    """
    return TRADUCOES_COLUNAS
