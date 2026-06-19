"""Carrega e expõe o dicionário customizável de ENUMs e códigos."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("saidjur.dicionarios")

_CAMINHO = Path(__file__).resolve().parent.parent / "dicionarios.yaml"
_CAMINHO_EXEMPLO = Path(__file__).resolve().parent.parent / "dicionarios.example.yaml"
_LOCK = threading.Lock()
# Estrutura do cache: {"mtime": float, "dados": dict[str, Any]}.
_CACHE: dict[str, Any] = {"mtime": 0.0, "dados": {}}


def _normalizar_dados(dados: Any) -> dict[str, Any]:
    """Garante que o conteúdo carregado tenha estrutura de dicionário."""
    return dados if isinstance(dados, dict) else {}


def _carregar_se_mudou() -> dict[str, Any]:
    """Carrega o dicionário do disco quando o arquivo muda."""
    caminho = _CAMINHO if _CAMINHO.exists() else _CAMINHO_EXEMPLO
    if not caminho.exists():
        return {}

    with _LOCK:
        try:
            mtime = caminho.stat().st_mtime
        except OSError:
            return _CACHE["dados"]

        if mtime == _CACHE["mtime"]:
            return _CACHE["dados"]

        try:
            with caminho.open("r", encoding="utf-8") as arquivo:
                dados = _normalizar_dados(yaml.safe_load(arquivo) or {})
        except Exception as exc:
            logger.warning("Falha ao carregar %s: %s", caminho.name, exc)
            return _CACHE["dados"]

        _CACHE["mtime"] = mtime
        _CACHE["dados"] = dados
        logger.info("Dicionário recarregado de %s (%d tabelas)", caminho.name, len(dados))
        return dados


def traduzir(tabela: str, coluna: str, valor: Any) -> str | None:
    """Retorna a tradução de um valor, quando existir."""
    if valor is None:
        return None
    dados = obter_dicionarios()
    return dados.get(tabela, {}).get(coluna, {}).get(str(valor))


def dicionario_de_coluna(tabela: str, coluna: str) -> dict[str, str]:
    """Retorna o mapa completo de tradução de uma coluna."""
    dados = obter_dicionarios()
    coluna_dict = dados.get(tabela, {}).get(coluna, {})
    return coluna_dict if isinstance(coluna_dict, dict) else {}


def obter_dicionarios() -> dict[str, Any]:
    """Retorna todos os dicionários carregados no momento."""
    return _carregar_se_mudou()
