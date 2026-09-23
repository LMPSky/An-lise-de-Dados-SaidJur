"""Testes para o script listar_traducoes_faltantes.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
import yaml

import listar_traducoes_faltantes as script
import src.investigacao_pendencias as mod


def _engine_com_tabela_simples() -> object:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE paymenttype (
                    id INTEGER PRIMARY KEY,
                    code TEXT,
                    name TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO paymenttype (id, code, name) VALUES
                (1, 'Bol', 'Boleto'),
                (2, 'Bol', 'Boleto')
                """
            )
        )
        conn.commit()
    return engine


def test_main_gera_relatorio_completo_e_lista_plana(tmp_path: Path, monkeypatch) -> None:
    engine = _engine_com_tabela_simples()

    caminho_markdown = tmp_path / "pendencias.md"
    caminho_markdown.write_text("# Sem pendências humanas neste teste\n", encoding="utf-8")

    caminho_dicionarios = tmp_path / "dicionarios.yaml"
    caminho_dicionarios.write_text("traducoes: {}\n", encoding="utf-8")

    saida_relatorio = tmp_path / "relatorio.yaml"
    saida_lista = tmp_path / "lista.yaml"

    monkeypatch.chdir(tmp_path)

    with (
        patch.object(mod, "criar_engine", return_value=engine),
        patch.object(script, "ARQUIVO_PENDENCIAS_MARKDOWN_PADRAO", str(caminho_markdown)),
        patch(
            "sys.argv",
            [
                "listar_traducoes_faltantes.py",
                "--limite-linhas",
                "3",
                "--saida-relatorio",
                str(saida_relatorio),
                "--saida-lista",
                str(saida_lista),
                "--intervalo-checkpoint",
                "0",
            ],
        ),
    ):
        script.main()

    assert saida_relatorio.exists()
    assert saida_lista.exists()

    dados_lista = yaml.safe_load(saida_lista.read_text(encoding="utf-8"))
    itens = dados_lista["decisoes"]
    assert len(itens) >= 1
    achou_paymenttype = any(
        item["tabela"] == "paymenttype" and item["coluna"] == "code" and item["valor"] == "Bol"
        for item in itens
    )
    assert achou_paymenttype, "Item paymenttype.code=Bol deveria estar na lista plana gerada"

    # Todos os itens vêm como 'pendente' -- ninguém foi decidido automaticamente.
    assert all(item["decisao"] == "pendente" for item in itens)

    # Lista deve estar ordenada por tabela/coluna/valor.
    chaves = [(item["tabela"], item["coluna"], item["valor"]) for item in itens]
    assert chaves == sorted(chaves)
