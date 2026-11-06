"""Rotas para acesso a documentos externos de um processo (fora do banco)."""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from src.documentos import (
    DocumentosDesabilitadosError,
    NomeArquivoInvalidoError,
    NumeroProcessoInvalidoError,
    diretorio_base_configurado,
    listar_documentos_processo,
    resolver_caminho_arquivo,
)

router = APIRouter(tags=["Documentos"])
logger = logging.getLogger("saidjur.documentos")


@router.get(
    "/documentos/status",
    summary="Verifica se a funcionalidade de documentos externos está habilitada",
)
async def get_status_documentos() -> dict:
    """Retorna se o acesso a documentos externos está habilitado nesta instância."""
    return {"habilitado": diretorio_base_configurado() is not None}


@router.get(
    "/documentos/{numero_processo}",
    summary="Lista os documentos disponíveis para um número de processo",
)
async def get_documentos_processo(numero_processo: str) -> dict:
    """Lista metadados dos arquivos de um processo (nome, tamanho, tipo, data).

    Retorna lista vazia (não erro) quando o processo não tem pasta de
    documentos — situação esperada enquanto o acervo completo não estiver
    disponível.
    """
    try:
        arquivos = await run_in_threadpool(listar_documentos_processo, numero_processo)
    except DocumentosDesabilitadosError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NumeroProcessoInvalidoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao listar documentos do processo '%s'", numero_processo)
        raise HTTPException(status_code=500, detail=f"Falha ao listar documentos: {exc}") from exc

    return {"numero_processo": numero_processo, "arquivos": [asdict(a) for a in arquivos]}


@router.get(
    "/documentos/{numero_processo}/arquivo/{nome_arquivo}",
    summary="Baixa/visualiza um documento específico de um processo",
)
async def get_arquivo_documento(numero_processo: str, nome_arquivo: str) -> FileResponse:
    """Serve um arquivo específico da pasta de documentos de um processo."""
    try:
        caminho = await run_in_threadpool(resolver_caminho_arquivo, numero_processo, nome_arquivo)
    except DocumentosDesabilitadosError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (NumeroProcessoInvalidoError, NomeArquivoInvalidoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Falha ao servir arquivo '%s' do processo '%s'", nome_arquivo, numero_processo
        )
        raise HTTPException(status_code=500, detail=f"Falha ao abrir arquivo: {exc}") from exc

    return FileResponse(str(caminho), filename=caminho.name)
