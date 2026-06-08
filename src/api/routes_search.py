"""Rotas de busca global (tradicional e streaming incremental)."""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config import CONFIG
from src.db import colunas_texto, listar_tabelas

router = APIRouter(tags=["Busca"])
logger = logging.getLogger("saidjur.busca")


def _buscar_em_tabela(
    engine: Engine,
    nome_tabela: str,
    colunas: list[str],
    termo: str,
    limite: int,
    timeout: int,
) -> list[dict[str, Any]]:
    """Executa busca LIKE em todas as colunas textuais de uma tabela."""
    resultados: list[dict[str, Any]] = []

    from sqlalchemy import MetaData, Table, select

    meta = MetaData()
    try:
        tbl = Table(nome_tabela, meta, autoload_with=engine)
    except Exception as exc:
        logger.warning("Erro ao refletir tabela '%s': %s", nome_tabela, exc)
        return resultados

    for coluna in colunas:
        try:
            col = tbl.c[coluna]
            from src.api.routes_data import _escapar_like

            padrao = "%" + _escapar_like(termo) + "%"
            stmt = select(tbl).where(col.like(padrao, escape="!")).limit(limite)

            with engine.connect() as conn:
                try:
                    conn.execute(
                        text("SET SESSION max_execution_time=:ms"),
                        {"ms": timeout * 1000},
                    )
                except Exception:
                    pass
                resultado = conn.execute(stmt)
                chaves = list(resultado.keys())
                linhas = [dict(zip(chaves, row)) for row in resultado]
                if linhas:
                    resultados.append(
                        {"tabela": nome_tabela, "coluna": coluna, "registros": linhas}
                    )
        except Exception as exc:
            logger.warning("Erro ao buscar em %s.%s: %s", nome_tabela, coluna, exc)

    return resultados


def _preparar_tabelas_busca(
    engine: Engine,
    incluir_colunas_grandes: bool,
) -> list[tuple[str, list[str], int]]:
    tabelas = listar_tabelas(engine)
    tabelas_ordenadas = sorted(tabelas, key=lambda t: int(t.get("linhas_aprox") or 0))

    tabelas_com_colunas: list[tuple[str, list[str], int]] = []
    for t in tabelas_ordenadas:
        nome = t["nome"]
        colunas = colunas_texto(engine, nome, incluir_colunas_grandes=incluir_colunas_grandes)
        if colunas:
            tabelas_com_colunas.append((nome, colunas, int(t.get("linhas_aprox") or 0)))
    return tabelas_com_colunas


def _iter_busca_global(
    engine: Engine,
    termo: str,
    limite: int,
    timeout: int,
    parallelism: int,
    incluir_colunas_grandes: bool,
) -> Generator[dict[str, Any], None, None]:
    """Itera eventos de progresso e resultados conforme tabelas finalizam."""
    tabelas = _preparar_tabelas_busca(engine, incluir_colunas_grandes)
    total = len(tabelas)
    if total == 0:
        yield {"tipo": "done", "processadas": 0, "total": 0, "encontrados": 0}
        return

    encontrados = 0
    processadas = 0

    with ThreadPoolExecutor(max_workers=max(1, parallelism)) as executor:
        futuros = {
            executor.submit(_buscar_em_tabela, engine, nome, colunas, termo, limite, timeout): nome
            for nome, colunas, _linhas in tabelas
        }

        for futuro in as_completed(futuros):
            nome_tabela = futuros[futuro]
            processadas += 1
            try:
                resultados = futuro.result()
            except Exception as exc:
                logger.warning("Falha na busca em tabela '%s': %s", nome_tabela, exc)
                resultados = []

            if resultados:
                encontrados += len(resultados)
                yield {"tipo": "result", "tabela": nome_tabela, "items": resultados}

            yield {
                "tipo": "progress",
                "processadas": processadas,
                "total": total,
                "encontrados": encontrados,
            }

    yield {
        "tipo": "done",
        "processadas": processadas,
        "total": total,
        "encontrados": encontrados,
    }


@router.get(
    "/busca",
    summary="Busca global por texto em todas as tabelas",
)
async def busca_global(
    request: Request,
    q: str = Query(min_length=1, description="Texto para pesquisar"),
    limite: int = Query(default=None, ge=1, le=500, description="Máximo de registros por coluna"),
    incluir_colunas_grandes: bool = Query(default=False, description="Inclui MEDIUMTEXT/LONGTEXT"),
) -> list[dict[str, Any]]:
    """Busca global em todas as tabelas, retornando resposta agregada."""
    engine = request.app.state.engine

    cfg_busca = CONFIG.get("busca", {})
    timeout = int(cfg_busca.get("timeout_segundos", 10))
    limite_efetivo = limite or int(cfg_busca.get("limite_padrao", 100))
    parallelism = int(cfg_busca.get("parallelism", 8))

    if len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="O termo de busca não pode ser vazio.")

    try:
        eventos = _iter_busca_global(
            engine,
            q,
            limite_efetivo,
            timeout,
            parallelism,
            incluir_colunas_grandes,
        )
        resultados: list[dict[str, Any]] = []
        for evento in eventos:
            if evento.get("tipo") == "result":
                resultados.extend(evento.get("items", []))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Não foi possível acessar o banco: {exc}") from exc

    logger.info("Busca '%s' retornou %d grupos de resultados", q, len(resultados))
    return resultados


@router.get(
    "/busca/stream",
    summary="Busca global incremental por streaming (SSE)",
)
async def busca_global_stream(
    request: Request,
    q: str = Query(min_length=1, description="Texto para pesquisar"),
    limite: int = Query(default=None, ge=1, le=500, description="Máximo de registros por coluna"),
    incluir_colunas_grandes: bool = Query(default=False, description="Inclui MEDIUMTEXT/LONGTEXT"),
) -> StreamingResponse:
    """Retorna eventos SSE com progresso e resultados incrementais."""
    engine = request.app.state.engine

    cfg_busca = CONFIG.get("busca", {})
    timeout = int(cfg_busca.get("timeout_segundos", 10))
    limite_efetivo = limite or int(cfg_busca.get("limite_padrao", 100))
    parallelism = int(cfg_busca.get("parallelism", 8))

    if len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="O termo de busca não pode ser vazio.")

    async def gerar_eventos() -> Any:
        try:
            for evento in _iter_busca_global(
                engine,
                q,
                limite_efetivo,
                timeout,
                parallelism,
                incluir_colunas_grandes,
            ):
                if await request.is_disconnected():
                    logger.info("Busca streaming cancelada pelo cliente")
                    break
                payload = json.dumps(evento, ensure_ascii=False, default=str)
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)
        except Exception as exc:
            erro = json.dumps({"tipo": "error", "mensagem": str(exc)}, ensure_ascii=False)
            yield f"data: {erro}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gerar_eventos(), media_type="text/event-stream", headers=headers)
