"""Rotas de busca global (tradicional e streaming incremental)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, AsyncGenerator, Generator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from src.config import CONFIG
from src.db import colunas_texto, listar_colunas, listar_tabelas

router = APIRouter(tags=["Busca"])
logger = logging.getLogger("saidjur.busca")


async def _stream_generator_sincrono(
    fabrica_generator,
) -> AsyncGenerator[Any, None]:
    """Converte um generator síncrono/bloqueante em um generator assíncrono.

    ``_iter_busca_global`` é síncrono (reflexão de schema + ThreadPoolExecutor
    + ``as_completed``) e, se consumido diretamente dentro de um ``async
    def``, bloqueia o único event loop do Uvicorn até a busca inteira
    terminar — congelando o servidor para TODOS os clientes conectados
    (inclusive requisições sem nenhuma relação com a busca, como clicar em
    uma tabela na barra lateral). Aqui o generator roda em uma thread
    separada e seus itens são repassados ao event loop por uma fila
    assíncrona, deixando o loop livre para atender outras requisições
    enquanto a busca está em andamento.
    """
    loop = asyncio.get_event_loop()
    fila: asyncio.Queue = asyncio.Queue()
    _FIM = object()

    def _worker() -> None:
        try:
            for item in fabrica_generator():
                loop.call_soon_threadsafe(fila.put_nowait, ("item", item))
        except Exception as exc:  # pragma: no cover - defensivo
            loop.call_soon_threadsafe(fila.put_nowait, ("erro", exc))
        finally:
            loop.call_soon_threadsafe(fila.put_nowait, ("fim", None))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    while True:
        tipo, payload = await fila.get()
        if tipo == "item":
            yield payload
        elif tipo == "erro":
            raise payload
        else:
            break


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

    try:
        colunas_detalhadas = listar_colunas(engine, nome_tabela)
    except Exception as exc:
        logger.warning("Erro ao listar colunas de '%s': %s", nome_tabela, exc)
        colunas_detalhadas = [{"nome": nome} for nome in colunas]

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
                        {
                            "tabela": nome_tabela,
                            "coluna": coluna,
                            "colunas": colunas_detalhadas,
                            "registros": linhas,
                        }
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

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
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
    parallelism = max(1, int(cfg_busca.get("parallelism", 8)))

    if len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="O termo de busca não pode ser vazio.")

    def _executar_busca_sincrona() -> list[dict[str, Any]]:
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
        return resultados

    try:
        # Delegado para uma thread: a busca percorre todas as tabelas do
        # banco de forma síncrona/bloqueante e, se rodasse direto aqui,
        # travaria o event loop único do Uvicorn para todos os clientes
        # conectados até terminar.
        resultados = await run_in_threadpool(_executar_busca_sincrona)
    except Exception as exc:
        logger.exception("Falha ao executar busca global")
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
    parallelism = max(1, int(cfg_busca.get("parallelism", 8)))

    if len(q.strip()) == 0:
        raise HTTPException(status_code=400, detail="O termo de busca não pode ser vazio.")

    async def gerar_eventos() -> Any:
        fabrica = lambda: _iter_busca_global(
            engine,
            q,
            limite_efetivo,
            timeout,
            parallelism,
            incluir_colunas_grandes,
        )
        try:
            # _stream_generator_sincrono roda a busca em uma thread separada,
            # para a busca não bloquear o event loop (e assim não travar as
            # requisições de outros usuários) enquanto os eventos são
            # repassados ao cliente incrementalmente.
            async for evento in _stream_generator_sincrono(fabrica):
                if await request.is_disconnected():
                    logger.info("Busca streaming cancelada pelo cliente")
                    break
                payload = json.dumps(evento, ensure_ascii=False, default=str)
                yield f"data: {payload}\n\n"
        except Exception as exc:
            logger.exception("Falha na busca streaming")
            erro = json.dumps({"tipo": "error", "mensagem": "Falha interna durante a busca."}, ensure_ascii=False)
            yield f"data: {erro}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gerar_eventos(), media_type="text/event-stream", headers=headers)
