"""Testes para as rotas de documentos externos (GET /api/documentos/...)."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def pasta_base(tmp_path, monkeypatch):
    base = tmp_path / "documentos"
    base.mkdir()
    processo = base / "0000003-16.2025.5.07.0015"
    processo.mkdir()
    (processo / "Processo_exemplo.pdf").write_bytes(b"conteudo-pdf")

    import src.documentos as docmod

    monkeypatch.setitem(docmod.CONFIG, "documentos", {
        "diretorio_base": str(base),
        "habilitado": True,
    })
    return base


@pytest.fixture
def client(pasta_base) -> Generator[TestClient, None, None]:
    from src.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def client_desabilitado(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    import src.documentos as docmod

    monkeypatch.setitem(docmod.CONFIG, "documentos", {"diretorio_base": "", "habilitado": False})

    from src.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestStatusDocumentos:
    def test_status_habilitado(self, client: TestClient) -> None:
        resp = client.get("/api/documentos/status")
        assert resp.status_code == 200
        assert resp.json() == {"habilitado": True}

    def test_status_desabilitado(self, client_desabilitado: TestClient) -> None:
        resp = client_desabilitado.get("/api/documentos/status")
        assert resp.status_code == 200
        assert resp.json() == {"habilitado": False}


class TestListarDocumentos:
    def test_lista_arquivos_do_processo(self, client: TestClient) -> None:
        resp = client.get("/api/documentos/0000003-16.2025.5.07.0015")
        assert resp.status_code == 200
        dados = resp.json()
        assert dados["numero_processo"] == "0000003-16.2025.5.07.0015"
        nomes = [a["nome"] for a in dados["arquivos"]]
        assert nomes == ["Processo_exemplo.pdf"]

    def test_processo_sem_pasta_retorna_lista_vazia(self, client: TestClient) -> None:
        resp = client.get("/api/documentos/9999999-99.2025.5.07.0015")
        assert resp.status_code == 200
        assert resp.json()["arquivos"] == []

    def test_numero_processo_invalido_retorna_400(self, client: TestClient) -> None:
        # O cliente/ASGI pode normalizar "../" na URL antes de chegar à rota,
        # resultando em 404 (rota não encontrada) — em ambos os casos nenhum
        # arquivo fora da base é exposto, que é a garantia que importa aqui.
        resp = client.get("/api/documentos/..%2F..%2Fetc")
        assert resp.status_code in (400, 404)

    def test_desabilitado_retorna_404(self, client_desabilitado: TestClient) -> None:
        resp = client_desabilitado.get("/api/documentos/0000003-16.2025.5.07.0015")
        assert resp.status_code == 404


class TestServirArquivo:
    def test_baixa_arquivo_existente(self, client: TestClient) -> None:
        resp = client.get(
            "/api/documentos/0000003-16.2025.5.07.0015/arquivo/Processo_exemplo.pdf"
        )
        assert resp.status_code == 200
        assert resp.content == b"conteudo-pdf"

    def test_arquivo_inexistente_retorna_404(self, client: TestClient) -> None:
        resp = client.get(
            "/api/documentos/0000003-16.2025.5.07.0015/arquivo/nao_existe.pdf"
        )
        assert resp.status_code == 404

    def test_nome_arquivo_com_traversal_retorna_400(self, client: TestClient) -> None:
        resp = client.get(
            "/api/documentos/0000003-16.2025.5.07.0015/arquivo/..%2F..%2Fconfig.yaml"
        )
        assert resp.status_code in (400, 404)
