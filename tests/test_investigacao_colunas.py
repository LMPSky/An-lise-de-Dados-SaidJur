"""Testes do fluxo de investigação de nomes de coluna."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
import yaml

from aplicar_sugestoes_colunas import _revisar_interativo, aplicar_traducoes_no_arquivo
from src.investigacao_colunas import (
    classificar_estado_traducao,
    coletar_pistas_coluna,
    executar_investigacao_colunas,
    investigar_coluna,
    listar_colunas_schema,
)



def test_classificar_estado_traduzida_manual() -> None:
    assert classificar_estado_traducao("created_at") == "traduzida_manual"



def test_classificar_estado_traduzida_heuristica(monkeypatch) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "processo", "Processo")
    assert classificar_estado_traducao("processo_id") == "traduzida_heuristica"



def test_classificar_estado_nao_traduzida() -> None:
    assert classificar_estado_traducao("xyzabc123") == "nao_traduzida"



def test_listar_colunas_schema_tabela() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, nome TEXT, xyzabc123 TEXT)"))
        conn.commit()

    colunas = listar_colunas_schema(engine, "teste")

    assert [item["coluna"] for item in colunas] == ["id", "nome", "xyzabc123"]
    assert colunas[1]["tabela"] == "teste"



def test_column_comment_alta_confianca(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, pzphase TEXT)"))
        conn.commit()

    class ResultadoFake:
        def fetchone(self):
            return ("Fase do prazo",)

    conexao_real = engine.connect

    class ConexaoFake:
        def __init__(self):
            self._conn = conexao_real()

        def __enter__(self):
            self._conn.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._conn.__exit__(exc_type, exc, tb)

        def execute(self, statement, *args, **kwargs):
            if "information_schema.COLUMNS" in str(statement):
                return ResultadoFake()
            return self._conn.execute(statement, *args, **kwargs)

        def close(self):
            return self._conn.close()

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(engine, "connect", lambda: ConexaoFake())

    pistas = coletar_pistas_coluna(engine, "teste", "pzphase", "TEXT")["pistas"]

    assert any(
        pista["fonte"] == "column_comment" and pista["confianca"] == "alta_confianca"
        for pista in pistas
    )



def test_tipo_dado_booleano() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (ativo INTEGER)"))
        conn.commit()

    pistas = coletar_pistas_coluna(engine, "teste", "ativo", "TINYINT(1)")["pistas"]

    assert any("booleano" in pista["valor"].lower() for pista in pistas if pista["fonte"] == "tipo_dado")



def test_colunas_irmas_sugestao() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE documentos (prazo_status TEXT, prazo_id INTEGER, nome TEXT)"))
        conn.commit()

    pistas = coletar_pistas_coluna(engine, "documentos", "prazo_status", "TEXT")["pistas"]

    assert any(
        pista["fonte"] == "colunas_irmas" and pista.get("coluna_relacionada") == "prazo_id"
        for pista in pistas
    )



def test_investigar_coluna_individual(monkeypatch) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "processo", "Processo")
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE documentos (processo_id INTEGER, observacao TEXT)"))
        conn.commit()

    resultado = investigar_coluna(engine, "documentos", "processo_id")

    assert resultado["estado"] == "traduzida_heuristica"
    assert resultado["sugestao_candidata"] == "ID do Processo"
    assert resultado["nivel_confianca"] == "alta_confianca"



def test_aplicar_sugestoes_nao_sobrescreve_manual(monkeypatch, tmp_path: Path) -> None:
    relatorio = {
        "investigacoes": [
            {
                "tabela": "teste",
                "coluna": "created_at",
                "estado": "traduzida_manual",
                "traducao_atual": "Data de Criação",
                "nivel_confianca": "traduzida_manual",
                "sugestao_candidata": "Outra Tradução",
                "pistas": [],
            }
        ]
    }

    respostas = iter(["s", "n"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(respostas))
    decisoes = _revisar_interativo(relatorio)

    assert decisoes[0]["decisao"] == "pular"
    assert decisoes[0]["traducao_final"] is None

    arquivo = tmp_path / "traducoes_colunas.py"
    arquivo.write_text(
        "TRADUCOES_COLUNAS = {\n    'created_at': 'Data de Criação',\n}\n",
        encoding="utf-8",
    )

    aplicadas = aplicar_traducoes_no_arquivo(arquivo, decisoes)
    assert aplicadas == []
    assert "Outra Tradução" not in arquivo.read_text(encoding="utf-8")



def test_executar_investigacao_colunas_gera_relatorio(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, xyzabc123 TEXT)"))
        conn.commit()

    saida = tmp_path / "relatorio.yaml"
    relatorio = executar_investigacao_colunas(engine=engine, tabela="teste", caminho_saida=str(saida))

    assert relatorio["resumo"]["total_investigadas"] == 2
    dados = yaml.safe_load(saida.read_text(encoding="utf-8"))
    assert dados["investigacoes"][1]["coluna"] == "xyzabc123"
