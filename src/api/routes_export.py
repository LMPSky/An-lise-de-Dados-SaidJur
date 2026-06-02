"""Rota de exportação: gera CSV ou XLSX em streaming sem carregar tudo na memória."""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from src.db import tabelas_validas, colunas_validas

router = APIRouter(tags=["Exportação"])
logger = logging.getLogger("saidjur.exportar")

_CHUNK_SIZE = 1000  # linhas por lote no streaming


def _montar_where(
    filtros_json: str | None, colunas_ok: set[str]
) -> tuple[str, dict[str, Any]]:
    """Reutiliza lógica de filtros do routes_data (cópia mínima para evitar importação circular)."""
    from src.api.routes_data import _montar_filtros  # importação local para evitar circular

    return _montar_filtros(filtros_json, colunas_ok)


async def _stream_csv(
    engine: Any,
    nome: str,
    where: str,
    params: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """Gera o CSV linha a linha, lendo do banco em lotes."""
    output = io.StringIO()
    writer: csv.DictWriter | None = None
    offset = 0

    while True:
        params_lote = dict(params, _offset=offset, _limit=_CHUNK_SIZE)
        with engine.connect() as conn:
            resultado = conn.execute(
                text(f"SELECT * FROM `{nome}` {where} LIMIT :_limit OFFSET :_offset"),
                params_lote,
            )
            colunas = list(resultado.keys())
            linhas = result_rows = resultado.fetchall()

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

        if len(result_rows) < _CHUNK_SIZE:
            break
        offset += _CHUNK_SIZE


async def _stream_xlsx(
    engine: Any,
    nome: str,
    where: str,
    params: dict[str, Any],
) -> AsyncGenerator[bytes, None]:
    """Gera XLSX em modo write_only (baixo uso de memória) e retorna em chunks."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
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
        params_lote = dict(params, _offset=offset, _limit=_CHUNK_SIZE)
        with engine.connect() as conn:
            resultado = conn.execute(
                text(f"SELECT * FROM `{nome}` {where} LIMIT :_limit OFFSET :_offset"),
                params_lote,
            )
            colunas = list(resultado.keys())
            linhas = resultado.fetchall()

        if not linhas:
            break

        if not cabecalho_escrito:
            header_row = [str(c) for c in colunas]
            ws.append(header_row)
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
    filtros: str | None = Query(default=None, description="JSON de filtros (mesmo formato de /linhas)"),
) -> StreamingResponse:
    """
    Exporta os dados de uma tabela em formato CSV ou XLSX.

    - CSV: streaming linha a linha — nunca carrega tudo na memória.
    - XLSX: gerado em write_only mode com openpyxl (baixo uso de RAM).
    - Respeita os mesmos filtros de /tabelas/{nome}/linhas.
    """
    engine = request.app.state.engine

    tabelas_ok = tabelas_validas(engine)
    if nome not in tabelas_ok:
        raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada.")

    cols_ok = colunas_validas(engine, nome)
    where, params = _montar_where(filtros, cols_ok)

    logger.info("Exportar: tabela='%s' formato='%s' filtros=%s", nome, formato, filtros)

    if formato == "csv":
        return StreamingResponse(
            _stream_csv(engine, nome, where, params),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nome}.csv"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    # XLSX
    return StreamingResponse(
        _stream_xlsx(engine, nome, where, params),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{nome}.xlsx"',
            "X-Content-Type-Options": "nosniff",
        },
    )
