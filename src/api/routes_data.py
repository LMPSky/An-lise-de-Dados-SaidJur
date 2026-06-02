"""Rotas para consulta paginada de dados de uma tabela, com filtros e ordenação."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text

from src.db import tabelas_validas, colunas_validas

router = APIRouter(tags=["Dados"])
logger = logging.getLogger("saidjur.dados")

# Operadores de filtro permitidos → fragmento SQL
_OPERADORES: dict[str, str] = {
    "contem": "LIKE",
    "nao_contem": "NOT LIKE",
    "igual": "=",
    "diferente": "!=",
    "maior": ">",
    "menor": "<",
    "maior_igual": ">=",
    "menor_igual": "<=",
    "comeca_com": "LIKE",
}

_POR_PAGINA_MAX = 500


def _montar_filtros(
    filtros_json: str | None,
    colunas_ok: set[str],
) -> tuple[str, dict[str, Any]]:
    """
    Converte o JSON de filtros em cláusula WHERE SQL parametrizada.

    Formato esperado:
        {"coluna": {"op": "contem|igual|...", "valor": "texto"}}

    Retorna: (cláusula_where, params)
    """
    if not filtros_json:
        return "", {}

    try:
        filtros: dict[str, dict[str, str]] = json.loads(filtros_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON de filtros inválido: {exc}") from exc

    clausulas: list[str] = []
    params: dict[str, Any] = {}

    for idx, (coluna, opcoes) in enumerate(filtros.items()):
        if coluna not in colunas_ok:
            raise HTTPException(
                status_code=400, detail=f"Coluna desconhecida no filtro: '{coluna}'"
            )
        op_nome = opcoes.get("op", "contem")
        valor = opcoes.get("valor", "")

        if op_nome not in _OPERADORES:
            raise HTTPException(
                status_code=400,
                detail=f"Operador inválido '{op_nome}'. Use: {list(_OPERADORES)}",
            )

        op_sql = _OPERADORES[op_nome]
        param_name = f"filtro_{idx}"

        # Ajusta valor para LIKE
        if op_nome == "contem":
            valor = f"%{valor}%"
        elif op_nome == "nao_contem":
            valor = f"%{valor}%"
        elif op_nome == "comeca_com":
            valor = f"{valor}%"

        # Nome da coluna é validado contra whitelist — seguro interpolá-lo
        clausulas.append(f"`{coluna}` {op_sql} :{param_name}")
        params[param_name] = valor

    where = "WHERE " + " AND ".join(clausulas) if clausulas else ""
    return where, params


@router.get(
    "/tabelas/{nome}/linhas",
    summary="Consulta registros de uma tabela com paginação e filtros",
)
async def get_linhas(
    nome: str,
    request: Request,
    pagina: int = Query(default=1, ge=1, description="Número da página"),
    por_pagina: int = Query(
        default=50, ge=1, le=_POR_PAGINA_MAX, description="Registros por página (máx 500)"
    ),
    ordenar_por: str | None = Query(default=None, description="Nome da coluna para ordenar"),
    direcao: str = Query(default="asc", pattern="^(asc|desc)$", description="asc ou desc"),
    filtros: str | None = Query(default=None, description='JSON de filtros: {"col":{"op":"contem","valor":"x"}}'),
) -> dict[str, Any]:
    """
    Retorna registros paginados de uma tabela.

    - Suporta filtros por coluna (contem, igual, diferente, maior, menor, comeca_com)
    - Suporta ordenação segura (valida nome da coluna)
    - Nunca carrega mais de 500 linhas por requisição
    """
    engine = request.app.state.engine

    # Valida nome da tabela
    tabelas_ok = tabelas_validas(engine)
    if nome not in tabelas_ok:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    cols_ok = colunas_validas(engine, nome)

    # Monta filtros
    where, params = _montar_filtros(filtros, cols_ok)

    # Valida ordenação
    order_clause = ""
    if ordenar_por:
        if ordenar_por not in cols_ok:
            raise HTTPException(
                status_code=400, detail=f"Coluna de ordenação desconhecida: '{ordenar_por}'"
            )
        dir_sql = "ASC" if direcao.lower() == "asc" else "DESC"
        order_clause = f"ORDER BY `{ordenar_por}` {dir_sql}"

    offset = (pagina - 1) * por_pagina

    with engine.connect() as conn:
        # Contagem total
        sql_count = text(f"SELECT COUNT(*) FROM `{nome}` {where}")
        total: int = conn.execute(sql_count, params).scalar_one()

        # Dados
        params_pag = dict(params, _offset=offset, _limit=por_pagina)
        sql_dados = text(
            f"SELECT * FROM `{nome}` {where} {order_clause} LIMIT :_limit OFFSET :_offset"
        )
        resultado = conn.execute(sql_dados, params_pag)
        colunas = list(resultado.keys())
        linhas = [dict(zip(colunas, row)) for row in resultado]

    logger.info("Tabela '%s' | página %d | filtros=%s | total=%d", nome, pagina, filtros, total)

    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "linhas": linhas,
    }
