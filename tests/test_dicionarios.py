"""Testes do carregador de dicionários customizáveis."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.dicionarios as dicionarios_module


@pytest.fixture
def arquivos_dicionario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    caminho_principal = tmp_path / "dicionarios.yaml"
    caminho_exemplo = tmp_path / "dicionarios.example.yaml"

    monkeypatch.setattr(dicionarios_module, "_CAMINHO", caminho_principal)
    monkeypatch.setattr(dicionarios_module, "_CAMINHO_EXEMPLO", caminho_exemplo)
    dicionarios_module._CACHE["mtime"] = 0.0
    dicionarios_module._CACHE["dados"] = {}

    return caminho_principal, caminho_exemplo


def test_dicionario_ausente_retorna_vazio(arquivos_dicionario: tuple[Path, Path]) -> None:
    assert dicionarios_module._carregar_se_mudou() == {}
    assert dicionarios_module.traduzir("publicationxml", "nature", "p") is None
    assert dicionarios_module.dicionario_de_coluna("publicationxml", "nature") == {}


def test_dicionario_exemplo_funciona_como_fallback(arquivos_dicionario: tuple[Path, Path]) -> None:
    _, caminho_exemplo = arquivos_dicionario
    caminho_exemplo.write_text(
        "publicationxml:\n  nature:\n    p: 'Publicação'\n    m: 'Manifestação'\n",
        encoding="utf-8",
    )

    assert dicionarios_module.traduzir("publicationxml", "nature", "p") == "Publicação"
    assert dicionarios_module.dicionario_de_coluna("publicationxml", "nature") == {
        "p": "Publicação",
        "m": "Manifestação",
    }


def test_hot_reload_recarrega_arquivo_customizado(arquivos_dicionario: tuple[Path, Path]) -> None:
    caminho_principal, _ = arquivos_dicionario
    caminho_principal.write_text(
        "publicationxml:\n  nature:\n    p: 'Publicação antiga'\n",
        encoding="utf-8",
    )

    assert dicionarios_module.traduzir("publicationxml", "nature", "p") == "Publicação antiga"

    stat = caminho_principal.stat()
    caminho_principal.write_text(
        "publicationxml:\n  nature:\n    p: 'Publicação nova'\n",
        encoding="utf-8",
    )
    os.utime(caminho_principal, (stat.st_atime + 1, stat.st_mtime + 1))

    assert dicionarios_module.traduzir("publicationxml", "nature", "p") == "Publicação nova"


def test_rota_api_dicionarios_retorna_conteudo(arquivos_dicionario: tuple[Path, Path]) -> None:
    caminho_principal, _ = arquivos_dicionario
    caminho_principal.write_text(
        "publicationxml:\n  nature:\n    p: 'Publicação'\n",
        encoding="utf-8",
    )

    from src.api.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        resp_tudo = client.get("/api/dicionarios")
        resp_coluna = client.get("/api/dicionarios/publicationxml/nature")

    assert resp_tudo.status_code == 200
    assert resp_tudo.json()["publicationxml"]["nature"]["p"] == "Publicação"
    assert resp_coluna.status_code == 200
    assert resp_coluna.json() == {"p": "Publicação"}
