"""Testes para src/documentos.py (acesso a documentos externos de um processo)."""

from __future__ import annotations

import pytest

from src import documentos as docmod
from src.documentos import (
    DocumentosDesabilitadosError,
    NomeArquivoInvalidoError,
    NumeroProcessoInvalidoError,
    diretorio_base_configurado,
    listar_documentos_processo,
    resolver_caminho_arquivo,
)


@pytest.fixture
def pasta_base(tmp_path, monkeypatch):
    """Configura um diretório base de documentos com um processo de exemplo."""
    base = tmp_path / "documentos"
    base.mkdir()
    processo = base / "0000003-16.2025.5.07.0015"
    processo.mkdir()
    (processo / "Processo_0000003_202601011200.pdf").write_bytes(b"conteudo-pdf")
    (processo / "imagem_1202601011200.png").write_bytes(b"conteudo-png")

    monkeypatch.setitem(docmod.CONFIG, "documentos", {
        "diretorio_base": str(base),
        "habilitado": True,
    })
    return base


def test_diretorio_base_configurado_retorna_none_quando_desabilitado(monkeypatch):
    monkeypatch.setitem(docmod.CONFIG, "documentos", {"diretorio_base": "", "habilitado": False})
    assert diretorio_base_configurado() is None


def test_diretorio_base_configurado_retorna_path_quando_habilitado(pasta_base):
    assert diretorio_base_configurado() == pasta_base


def test_listar_documentos_processo_existente(pasta_base):
    arquivos = listar_documentos_processo("0000003-16.2025.5.07.0015")
    nomes = sorted(a.nome for a in arquivos)
    assert nomes == ["Processo_0000003_202601011200.pdf", "imagem_1202601011200.png"]
    assert all(a.tamanho_bytes > 0 for a in arquivos)


def test_listar_documentos_processo_sem_pasta_retorna_vazio(pasta_base):
    """Processo sem pasta local não é erro — apenas não tem documentos ainda."""
    assert listar_documentos_processo("9999999-99.2025.5.07.0015") == []


def test_listar_documentos_desabilitado_levanta_erro(monkeypatch):
    monkeypatch.setitem(docmod.CONFIG, "documentos", {"diretorio_base": "", "habilitado": False})
    with pytest.raises(DocumentosDesabilitadosError):
        listar_documentos_processo("0000003-16.2025.5.07.0015")


@pytest.mark.parametrize("numero_malicioso", [
    "../etc",
    "..",
    "..\\windows",
    "a/b",
    "a\\b",
    "",
    "   ",
])
def test_listar_documentos_numero_processo_invalido(pasta_base, numero_malicioso):
    with pytest.raises(NumeroProcessoInvalidoError):
        listar_documentos_processo(numero_malicioso)


def test_resolver_caminho_arquivo_existente(pasta_base):
    caminho = resolver_caminho_arquivo(
        "0000003-16.2025.5.07.0015", "Processo_0000003_202601011200.pdf"
    )
    assert caminho.is_file()
    assert caminho.read_bytes() == b"conteudo-pdf"


def test_resolver_caminho_arquivo_inexistente_levanta_file_not_found(pasta_base):
    with pytest.raises(FileNotFoundError):
        resolver_caminho_arquivo("0000003-16.2025.5.07.0015", "nao_existe.pdf")


@pytest.mark.parametrize("nome_malicioso", ["../config.yaml", "a/b.pdf", "a\\b.pdf", "", ".."])
def test_resolver_caminho_arquivo_nome_invalido(pasta_base, nome_malicioso):
    with pytest.raises(NomeArquivoInvalidoError):
        resolver_caminho_arquivo("0000003-16.2025.5.07.0015", nome_malicioso)


def test_resolver_caminho_arquivo_nao_escapa_diretorio_base(pasta_base, tmp_path):
    """Mesmo um número de processo validado não pode resultar em escape da base."""
    # Cria um arquivo secreto fora da base para garantir que não é acessível.
    segredo = tmp_path / "segredo.txt"
    segredo.write_text("nao deveria ser acessivel")

    with pytest.raises((NumeroProcessoInvalidoError, FileNotFoundError)):
        resolver_caminho_arquivo("..", "segredo.txt")
