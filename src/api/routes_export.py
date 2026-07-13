"""Rotas para consulta paginada de dados de uma tabela, com filtros e ordenação."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import MetaData, Table, func, select, and_, asc, desc
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.db import tabelas_validas, colunas_validas

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


def _colunas_vazias(session: Session, engine: Engine, tabela_nome: str, colunas_nomes: list[str]) -> set[str]:
    """
    Identifica quais colunas têm APENAS valores NULL ou string vazia em toda a tabela.
    Retorna um set com os nomes das colunas vazias.
    """
    try:
        tbl = _get_table(engine, tabela_nome)
        colunas_vazias = set()
        
        for col_nome in colunas_nomes:
            col = tbl.c.get(col_nome)
            if col is None:
                continue
            
            # Conta quantos valores NÃO são NULL e NÃO são string vazia
            stmt = select(func.count()).select_from(tbl).where(
                and_(
                    col.isnot(None),
                    col != '',
                    col != '—',
                    col != '-',
                )
            )
            
            count_nao_vazios = session.execute(stmt).scalar() or 0
            
            # Se NÃO há valores não-vazios, coluna é considerada vazia
            if count_nao_vazios == 0:
                colunas_vazias.add(col_nome)
        
        return colunas_vazias
    
    except Exception as exc:
        logger.warning("Erro ao detectar colunas vazias em %s: %s", tabela_nome, exc)
        return set()


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
    sem_colunas_vazias: bool = Query(
        default=False,
        description="Se true, remove colunas que só têm valores NULL/vazios",
    ),
) -> dict[str, Any]:
    """
    Retorna registros paginados de uma tabela.

    - Suporta filtros por coluna (contem, igual, diferente, maior, menor, comeca_com)
    - Suporta ordenação segura via SQLAlchemy expression language
    - Nunca carrega mais de 500 linhas por requisição
    - Queries 100% parametrizadas via SQLAlchemy (sem interpolação de valores do usuário)
    - Opção de remover colunas vazias automaticamente
    """
    engine = request.app.state.engine

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
        # Contagem total
        count_stmt = select(func.count()).select_from(tbl)
        if where_exprs:
            count_stmt = count_stmt.where(and_(*where_exprs))
        total: int = conn.execute(count_stmt).scalar_one()

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

    # ── Filtrar colunas vazias (se solicitado) ──
    colunas_ocultar = set()
    if sem_colunas_vazias:
        with Session(engine) as session:
            colunas_ocultar = _colunas_vazias(session, engine, nome, colunas)
            colunas = [c for c in colunas if c not in colunas_ocultar]
            linhas = [{c: row.get(c) for c in colunas} for row in linhas]

    logger.info(
        "Tabela '%s' | página %d | filtros=%s | total=%d | ocultas=%d", 
        nome, pagina, filtros, total, len(colunas_ocultar)
    )

    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "linhas": linhas,
        "colunas": colunas,
        "colunas_ocultadas": list(colunas_ocultar),
    }