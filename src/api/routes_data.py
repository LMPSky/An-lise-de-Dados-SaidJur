"""Rotas para consulta paginada de dados de uma tabela, com filtros e ordenação."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import MetaData, Table, func, select, and_, asc, desc, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from src.config import CONFIG
from src.db import tabelas_validas, colunas_validas, listar_tabelas

router = APIRouter(tags=["Dados"])
logger = logging.getLogger("saidjur.dados")

def _escapar_like(valor: str, escape: str = "!") -> str:
    """Escapa caracteres especiais de LIKE (%, _, e o próprio escape) no valor do usuário."""
    return valor.replace(escape, escape + escape).replace("%", escape + "%").replace("_", escape + "_")


# Operadores de filtro permitidos → função que constrói a expressão SQLAlchemy
# Valores com wildcards LIKE (%, _) são escapados para evitar correspondências inesperadas.
_OPERADORES: dict[str, Any] = {
    "contem":      lambda col, val: col.like("%" + _escapar_like(val) + "%", escape="!"),
    "nao_contem":  lambda col, val: ~col.like("%" + _escapar_like(val) + "%", escape="!"),
    "igual":       lambda col, val: col == val,
    "diferente":   lambda col, val: col != val,
    "maior":       lambda col, val: col > val,
    "menor":       lambda col, val: col < val,
    "maior_igual": lambda col, val: col >= val,
    "menor_igual": lambda col, val: col <= val,
    "comeca_com":  lambda col, val: col.like(_escapar_like(val) + "%", escape="!"),
}

_POR_PAGINA_MAX = 500


def _get_table(engine: Engine, nome: str) -> Table:
    """Retorna um objeto Table do SQLAlchemy via reflexão do banco."""
    meta = MetaData()
    return Table(nome, meta, autoload_with=engine)


def _montar_where_exprs(
    tbl: Table,
    filtros_json: str | None,
    colunas_ok: set[str],
) -> list[Any]:
    """
    Converte o JSON de filtros em expressões SQLAlchemy (sem interpolação de strings).

    Formato esperado:
        {"coluna": {"op": "contem|igual|...", "valor": "texto"}}

    Retorna lista de expressões para uso em .where(and_(*exprs)).
    """
    if not filtros_json:
        return []

    try:
        filtros: dict[str, dict[str, str]] = json.loads(filtros_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON de filtros inválido: {exc}") from exc

    exprs: list[Any] = []

    for coluna, opcoes in filtros.items():
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

        col = tbl.c[coluna]
        exprs.append(_OPERADORES[op_nome](col, valor))

    return exprs


def _contagem_total(
    engine: Engine,
    conn,
    nome_tabela: str,
    count_stmt,
    tem_filtros: bool,
) -> tuple[int, bool]:
    """Calcula o total de linhas para fins de paginação.

    Sem filtros, usa a contagem aproximada já disponível em
    ``information_schema`` (``TABLE_ROWS``) — muito mais rápida que um
    ``COUNT(*)`` completo e suficiente para paginar. Isso evita que abrir uma
    tabela colossal (milhões de linhas, ex: ``publicationxml``) trave
    "para sempre" esperando a contagem exata.

    Com filtros, mantém a contagem exata (necessária para o filtro fazer
    sentido), mas limitada por ``max_execution_time`` de sessão para nunca
    bloquear indefinidamente.
    """
    if not tem_filtros:
        for t in listar_tabelas(engine):
            if t["nome"] == nome_tabela:
                return int(t.get("linhas_aprox") or 0), True
        return 0, True

    cfg_banco = CONFIG.get("banco", {})
    timeout_segundos = int(cfg_banco.get("timeout_contagem_segundos", 15))
    try:
        conn.execute(text("SET SESSION max_execution_time=:ms"), {"ms": timeout_segundos * 1000})
    except Exception:
        pass
    return int(conn.execute(count_stmt).scalar_one()), False


def _consultar_linhas_sincrono(
    engine: Engine,
    nome: str,
    pagina: int,
    por_pagina: int,
    ordenar_por: str | None,
    direcao: str,
    filtros: str | None,
) -> dict[str, Any]:
    """Executa toda a consulta paginada de forma síncrona/bloqueante.

    Roda fora do event loop (via run_in_threadpool no handler) para que uma
    tabela lenta não congele o servidor para os demais usuários conectados.
    """
    # Valida nome da tabela contra whitelist do banco
    tabelas_ok = tabelas_validas(engine)
    if nome not in tabelas_ok:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    cols_ok = colunas_validas(engine, nome)

    # Obtém objeto Table via reflexão (usa metadados do banco, não input do usuário)
    tbl = _get_table(engine, nome)

    # Monta expressões de filtro (totalmente parametrizadas)
    where_exprs = _montar_where_exprs(tbl, filtros, cols_ok)

    # Monta expressão de ordenação (coluna validada contra whitelist)
    order_expr = None
    if ordenar_por:
        if ordenar_por not in cols_ok:
            raise HTTPException(
                status_code=400, detail=f"Coluna de ordenação desconhecida: '{ordenar_por}'"
            )
        col_ord = tbl.c[ordenar_por]
        order_expr = asc(col_ord) if direcao.lower() == "asc" else desc(col_ord)

    offset = (pagina - 1) * por_pagina

    with engine.connect() as conn:
        # Contagem total (exata ou aproximada, ver _contagem_total)
        count_stmt = select(func.count()).select_from(tbl)
        if where_exprs:
            count_stmt = count_stmt.where(and_(*where_exprs))

        try:
            total, aproximado = _contagem_total(engine, conn, nome, count_stmt, bool(where_exprs))
        except Exception as exc:
            logger.warning("COUNT(*) filtrado em '%s' excedeu o tempo limite: %s", nome, exc)
            raise HTTPException(
                status_code=503,
                detail="A contagem de registros filtrados demorou demais. Tente um filtro mais específico.",
            ) from exc

        # Dados paginados
        data_stmt = select(tbl)
        if where_exprs:
            data_stmt = data_stmt.where(and_(*where_exprs))
        if order_expr is not None:
            data_stmt = data_stmt.order_by(order_expr)
        data_stmt = data_stmt.limit(por_pagina).offset(offset)

        resultado = conn.execute(data_stmt)
        colunas = list(resultado.keys())
        linhas = [dict(zip(colunas, row)) for row in resultado]

    logger.info(
        "Tabela '%s' | página %d | filtros=%s | total=%d%s",
        nome,
        pagina,
        filtros,
        total,
        " (aproximado)" if aproximado else "",
    )

    return {
        "total": total,
        "total_aproximado": aproximado,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "linhas": linhas,
        "colunas": colunas,
    }


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
    filtros: str | None = Query(
        default=None,
        description='JSON de filtros: {"col":{"op":"contem","valor":"x"}}',
    ),
) -> dict[str, Any]:
    """
    Retorna registros paginados de uma tabela.

    - Suporta filtros por coluna (contem, igual, diferente, maior, menor, comeca_com)
    - Suporta ordenação segura via SQLAlchemy expression language
    - Nunca carrega mais de 500 linhas por requisição
    - Queries 100% parametrizadas via SQLAlchemy (sem interpolação de valores do usuário)
    """
    engine = request.app.state.engine
    return await run_in_threadpool(
        _consultar_linhas_sincrono,
        engine,
        nome,
        pagina,
        por_pagina,
        ordenar_por,
        direcao,
        filtros,
    )
