"""Testes do carregador de dicionários customizáveis."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import yaml

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


def test_dicionarios_runtime_versionado_contem_traducoes_de_alta_confianca() -> None:
    caminho = Path(__file__).resolve().parent.parent / "dicionarios.yaml"
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))

    assert dados["chatmessages"]["recipienttype"]["all"] == "Todos"
    assert dados["paymenttype"]["code"]["dda"] == "Débito Direto Autorizado (DDA)"
    assert dados["persons"]["persontype"]["n"] == "Pessoa Física"
    assert dados["usertasks"]["write_paytype"]["1"] == "Sim"


def test_dicionarios_runtime_contem_traducoes_da_rodada_9() -> None:
    """Verifica as traduções de domínio fechado aplicadas na Rodada 9."""
    caminho = Path(__file__).resolve().parent.parent / "dicionarios.yaml"
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))

    # Status binários com os dois lados confirmados no banco real.
    for tabela, coluna in (
        ("deniedprazo_reasons", "status"),
        ("paymentguarantee2lawsuit", "status"),
        ("projectactivityprazos", "status"),
        ("prazos_log", "status"),
        ("prazo2publication", "status"),
    ):
        assert dados[tabela][coluna] == {"0": "Inativo", "1": "Ativo"}

    # Flags booleanas com domínio fechado.
    assert dados["paymentguarantee2lawsuit"]["containstypefile"] == {"0": "Não", "1": "Sim"}
    assert dados["hearingcontrol"]["remote"] == {"0": "Não", "1": "Sim"}
    assert dados["hearingcontrol"]["confession"] == {"n": "Não", "y": "Sim"}
    assert dados["hearingcontrol"]["third_party_presence"] == {"n": "Não", "y": "Sim"}

    # Valor textual inequívoco.
    assert dados["automaticprazos_lawsuits"]["hearing_type"]["all"] == "Todos"

    # Propagação a partir da mesma tabela de referência (`prazotype`).
    assert dados["prazos_log"]["pzphase"] == dados["prazo2publication"]["pzphase"]
    assert dados["prazos_log"]["finishtype"]["p"] == "processo físico"

    # Normalização de capitalização declarada na Rodada 5.
    assert dados["accounts"]["code"]["pass"] == "Passivo"
    assert dados["accounts"]["code"]["ativo"] == "Ativo"


def test_dicionarios_runtime_sem_conteudo_de_registro_especifico() -> None:
    """Garante que as entradas removidas por higiene de dados não retornem."""
    caminho = Path(__file__).resolve().parent.parent / "dicionarios.yaml"
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))

    assert "hearingstatus" not in dados["hearingcontrol"]
    assert "finalpayment_type" not in dados["lawsuits"]
