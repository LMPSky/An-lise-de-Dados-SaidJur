"""Rota de exportação: gera CSV ou XLSX em streaming sem carregar tudo na memória."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import MetaData, Table, select, and_
from sqlalchemy.engine import Engine

from src.db import tabelas_validas, colunas_validas
from src.api.routes_data import _get_table, _montar_where_exprs

router = APIRouter(tags=["Exportação"])
logger = logging.getLogger("saidjur.exportar")

_CHUNK_SIZE = 1000  # linhas por lote no streaming


async def _stream_csv(
    engine: Engine,
    tbl: Table,
    where_exprs: list[Any],
) -> AsyncGenerator[str, None]:
    """Gera o CSV linha a linha, lendo do banco em lotes (streaming sem estouro de memória)."""
    output = io.StringIO()
    writer: csv.DictWriter | None = None
    offset = 0

    while True:
        stmt = select(tbl)
        if where_exprs:
            stmt = stmt.where(and_(*where_exprs))
        stmt = stmt.limit(_CHUNK_SIZE).offset(offset)

        with engine.connect() as conn:
            resultado = conn.execute(stmt)
            colunas = list(resultado.keys())
            linhas = resultado.fetchall()

        if not linhas:
            break

        if writer is None:
            writer = csv.DictWriter(output, fieldnames=colunas)
            writer.writeheader()
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

        for row in linhas:
            writer.writerow(dict(zip(colunas, row)))

        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        if len(linhas) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE


async def _stream_xlsx(
    engine: Engine,
    tbl: Table,
    where_exprs: list[Any],
) -> AsyncGenerator[bytes, None]:
    """Gera XLSX em modo write_only (baixo uso de memória) e retorna em chunks."""
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="Exportação XLSX requer a biblioteca openpyxl. Execute: pip install openpyxl",
        ) from exc

    buf = io.BytesIO()
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Dados")

    cabecalho_escrito = False
    offset = 0

    while True:
        stmt = select(tbl)
        if where_exprs:
            stmt = stmt.where(and_(*where_exprs))
        stmt = stmt.limit(_CHUNK_SIZE).offset(offset)

        with engine.connect() as conn:
            resultado = conn.execute(stmt)
            colunas = list(resultado.keys())
            linhas = resultado.fetchall()

        if not linhas:
            break

        if not cabecalho_escrito:
            ws.append([str(c) for c in colunas])
            cabecalho_escrito = True

        for row in linhas:
            ws.append([str(v) if v is not None else "" for v in row])

        if len(linhas) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE

    wb.save(buf)
    buf.seek(0)
    yield buf.read()


@router.get(
    "/exportar/{nome}",
    summary="Exporta tabela para CSV ou XLSX em streaming",
)
async def exportar(
    nome: str,
    request: Request,
    formato: str = Query(default="csv", pattern="^(csv|xlsx)$", description="csv ou xlsx"),
    filtros: str | None = Query(
        default=None, description="JSON de filtros (mesmo formato de /linhas)"
    ),
) -> StreamingResponse:
    """
    Exporta os dados de uma tabela em formato CSV ou XLSX.

    - CSV: streaming linha a linha — nunca carrega tudo na memória.
    - XLSX: gerado em write_only mode com openpyxl (baixo uso de RAM).
    - Respeita os mesmos filtros de /tabelas/{nome}/linhas.
    - Queries 100% parametrizadas via SQLAlchemy expression language.
    """
    engine = request.app.state.engine

    tabelas_ok = tabelas_validas(engine)
    if nome not in tabelas_ok:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    cols_ok = colunas_validas(engine, nome)
    tbl = _get_table(engine, nome)
    where_exprs = _montar_where_exprs(tbl, filtros, cols_ok)

    logger.info("Exportar: tabela='%s' formato='%s' filtros=%s", nome, formato, filtros)

    if formato == "csv":
        return StreamingResponse(
            _stream_csv(engine, tbl, where_exprs),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nome}.csv"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # XLSX
    return StreamingResponse(
        _stream_xlsx(engine, tbl, where_exprs),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}.xlsx"',
            "X-Content-Type-Options": "nosniff",
        },
    )

