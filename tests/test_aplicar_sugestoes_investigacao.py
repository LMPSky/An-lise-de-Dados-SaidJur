"""Testes do CLI aplicar_sugestoes_investigacao.py (aprovação em lote)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aplicar_sugestoes_investigacao import (
    _detectar_colunas_referencia_inconsistente,
    main,
)


def _item(
    tabela: str,
    coluna: str,
    valor: str,
    traducao: str,
    tabela_referencia: str,
    fonte: str = "tabela_referencia",
) -> dict[str, Any]:
    return {
        "tabela": tabela,
        "coluna": coluna,
        "valor": valor,
        "tabela_referencia": tabela_referencia,
        "sugestao": {
            "status": "alta_confianca",
            "traducao_sugerida": traducao,
            "fonte": fonte,
        },
    }


def test_detectar_colunas_referencia_inconsistente_identifica_divergencia() -> None:
    """Regressão: 'lawsuitdocs.doctype' resolvendo ora para
    'correspondent_document_types', ora para 'otherdocs' deve ser detectado."""
    itens = [
        _item("lawsuitdocs", "doctype", "7", "Outro", "correspondent_document_types"),
        _item("lawsuitdocs", "doctype", "10", "TRCT", "otherdocs"),
        _item("hearingcontrol", "hearingtype", "7", "Inicial", "hearingtype"),
        _item("hearingcontrol", "hearingtype", "8", "Nova Inicial", "hearingtype"),
    ]

    inconsistentes = _detectar_colunas_referencia_inconsistente(itens)

    assert inconsistentes == {
        "lawsuitdocs.doctype": {"correspondent_document_types", "otherdocs"}
    }


def test_aprovar_fonte_exclui_coluna_inconsistente_por_padrao(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import yaml

    relatorio = {
        "investigacoes": [
            _item("lawsuitdocs", "doctype", "7", "Outro", "correspondent_document_types"),
            _item("lawsuitdocs", "doctype", "10", "TRCT", "otherdocs"),
            _item("hearingcontrol", "hearingtype", "7", "Inicial", "hearingtype"),
        ]
    }
    caminho_relatorio = tmp_path / "relatorio.yaml"
    caminho_relatorio.write_text(yaml.safe_dump(relatorio), encoding="utf-8")
    caminho_dicionarios = tmp_path / "dicionarios.yaml"

    import sys
    argv_original = sys.argv
    try:
        sys.argv = [
            "aplicar_sugestoes_investigacao.py",
            "--relatorio-investigacao", str(caminho_relatorio),
            "--dicionarios", str(caminho_dicionarios),
            "--aprovar-fonte", "tabela_referencia",
            "--dry-run",
        ]
        main()
    finally:
        sys.argv = argv_original

    saida = capsys.readouterr().out
    assert "1 sugestão(ões)" in saida
    assert "lawsuitdocs.doctype" in saida
    assert "hearingcontrol.hearingtype[7]" in saida
    assert "Traduções aplicadas: 1" in saida


def test_aprovar_fonte_incluir_colunas_inconsistentes_forca_inclusao(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import yaml

    relatorio = {
        "investigacoes": [
            _item("lawsuitdocs", "doctype", "7", "Outro", "correspondent_document_types"),
            _item("lawsuitdocs", "doctype", "10", "TRCT", "otherdocs"),
        ]
    }
    caminho_relatorio = tmp_path / "relatorio.yaml"
    caminho_relatorio.write_text(yaml.safe_dump(relatorio), encoding="utf-8")
    caminho_dicionarios = tmp_path / "dicionarios.yaml"

    import sys
    argv_original = sys.argv
    try:
        sys.argv = [
            "aplicar_sugestoes_investigacao.py",
            "--relatorio-investigacao", str(caminho_relatorio),
            "--dicionarios", str(caminho_dicionarios),
            "--aprovar-fonte", "tabela_referencia",
            "--incluir-colunas-inconsistentes",
            "--dry-run",
        ]
        main()
    finally:
        sys.argv = argv_original

    saida = capsys.readouterr().out
    assert "Traduções aplicadas: 2" in saida


def test_aprovar_fonte_excluir_coluna_manualmente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import yaml

    relatorio = {
        "investigacoes": [
            _item("hearingcontrol", "hearingtype", "7", "Inicial", "hearingtype"),
            _item("hearings_log", "hearingtype", "7", "Inicial", "hearingtype"),
        ]
    }
    caminho_relatorio = tmp_path / "relatorio.yaml"
    caminho_relatorio.write_text(yaml.safe_dump(relatorio), encoding="utf-8")
    caminho_dicionarios = tmp_path / "dicionarios.yaml"

    import sys
    argv_original = sys.argv
    try:
        sys.argv = [
            "aplicar_sugestoes_investigacao.py",
            "--relatorio-investigacao", str(caminho_relatorio),
            "--dicionarios", str(caminho_dicionarios),
            "--aprovar-fonte", "tabela_referencia",
            "--excluir-coluna", "hearingcontrol.hearingtype",
            "--dry-run",
        ]
        main()
    finally:
        sys.argv = argv_original

    saida = capsys.readouterr().out
    assert "Colunas excluídas manualmente" in saida
    assert "hearingcontrol.hearingtype" in saida
    assert "Traduções aplicadas: 1" in saida
