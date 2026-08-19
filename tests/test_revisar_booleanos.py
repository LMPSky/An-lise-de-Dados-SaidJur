"""Testes do fluxo interativo de revisão de colunas booleanas."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
import yaml

from revisar_booleanos import revisar_booleanos_interativamente
from src.investigacao_colunas import executar_investigacao_colunas


def _escrever_relatorio(caminho: Path, investigacoes: list[dict[str, object]]) -> None:
    relatorio = {
        "gerado_em": "2026-08-19T00:00:00+00:00",
        "resumo": {
            "total_investigadas": len(investigacoes),
            "provavel_booleano": sum(1 for item in investigacoes if item.get("provavel_booleano")),
            "classificacao_nomes": {
                "traduzidas_manual": 0,
                "alta_confianca": 0,
                "pista_parcial": len(investigacoes),
                "sem_pista": 0,
            },
            "traduzidas_manual": 0,
            "alta_confianca": 0,
            "pista_parcial": len(investigacoes),
            "sem_pista": 0,
        },
        "colunas_booleanas_provaveis": {},
        "investigacoes": investigacoes,
    }
    caminho.write_text(yaml.safe_dump(relatorio, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _investigacao_booleana(
    tabela: str,
    coluna: str,
    *,
    tipo: str = "INTEGER",
    nulos_observados: bool = True,
) -> dict[str, object]:
    return {
        "tabela": tabela,
        "coluna": coluna,
        "tipo": tipo,
        "estado": "nao_traduzida",
        "traducao_atual": coluna.capitalize(),
        "pistas": [
            {
                "fonte": "provavel_booleano",
                "valor": "Domínio restrito a 0/1.",
                "confianca": "media",
                "categoria": "provavel_booleano",
                "valores_observados": ["0", "1"],
                "nulos_observados": nulos_observados,
                "amostra_distintos": ["0", "1"],
            },
            {
                "fonte": "tipo_dado",
                "valor": "Campo numérico/código",
                "confianca": "baixa",
            },
        ],
        "sugestao_candidata": None,
        "nivel_confianca": "pista_parcial",
        "nivel_confianca_nome": "pista_parcial",
        "classificacao_valores": "provavel_booleano",
        "provavel_booleano": True,
    }


def test_revisar_booleanos_confirma_coluna(tmp_path: Path, monkeypatch) -> None:
    relatorio = tmp_path / "relatorio.yaml"
    decisoes = tmp_path / "decisoes.yaml"
    _escrever_relatorio(relatorio, [_investigacao_booleana("users", "active")])

    respostas = iter(["s"])
    resumo = revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        input_fn=lambda _prompt: next(respostas),
        output_fn=lambda _msg: None,
    )

    assert resumo == {"confirmadas": 1, "rejeitadas": 0, "pendentes": 0}
    dados_decisoes = yaml.safe_load(decisoes.read_text(encoding="utf-8"))
    assert "users.active" in dados_decisoes["confirmadas"]

    dados_relatorio = yaml.safe_load(relatorio.read_text(encoding="utf-8"))
    item = dados_relatorio["investigacoes"][0]
    assert item["confirmado_manualmente"] is True
    assert item["revisao_booleano_manual"] == "confirmado"


def test_revisar_booleanos_rejeita_coluna_e_investigacao_futura_respeita_exclusao(
    tmp_path: Path,
) -> None:
    relatorio = tmp_path / "relatorio.yaml"
    decisoes = tmp_path / "decisoes.yaml"
    _escrever_relatorio(relatorio, [_investigacao_booleana("users", "active")])

    respostas = iter(["n"])
    revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        input_fn=lambda _prompt: next(respostas),
        output_fn=lambda _msg: None,
    )

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, active INTEGER)"))
        conn.execute(text("INSERT INTO users (active) VALUES (0), (1), (NULL)"))
        conn.commit()

    relatorio_futuro = executar_investigacao_colunas(
        engine=engine,
        tabela="users",
        caminho_saida=str(tmp_path / "relatorio_futuro.yaml"),
        caminho_decisoes_booleanos=str(decisoes),
    )
    item_active = next(item for item in relatorio_futuro["investigacoes"] if item["coluna"] == "active")

    assert item_active["provavel_booleano"] is False
    assert item_active["rejeitado_manualmente"] is True
    assert relatorio_futuro["resumo"]["provavel_booleano"] == 0


def test_revisar_booleanos_pular_mantem_coluna_pendente_na_proxima_execucao(tmp_path: Path) -> None:
    relatorio = tmp_path / "relatorio.yaml"
    decisoes = tmp_path / "decisoes.yaml"
    _escrever_relatorio(relatorio, [_investigacao_booleana("users", "active")])

    respostas_primeira = iter(["p"])
    resumo_primeira = revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        input_fn=lambda _prompt: next(respostas_primeira),
        output_fn=lambda _msg: None,
    )

    respostas_segunda = iter(["s"])
    resumo_segunda = revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        input_fn=lambda _prompt: next(respostas_segunda),
        output_fn=lambda _msg: None,
    )

    assert resumo_primeira == {"confirmadas": 0, "rejeitadas": 0, "pendentes": 1}
    assert resumo_segunda == {"confirmadas": 1, "rejeitadas": 0, "pendentes": 0}


def test_revisar_booleanos_q_preserva_progresso_parcial(tmp_path: Path) -> None:
    relatorio = tmp_path / "relatorio.yaml"
    decisoes = tmp_path / "decisoes.yaml"
    _escrever_relatorio(
        relatorio,
        [
            _investigacao_booleana("users", "active"),
            _investigacao_booleana("users", "remote"),
        ],
    )

    respostas = iter(["s", "q"])
    resumo = revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        input_fn=lambda _prompt: next(respostas),
        output_fn=lambda _msg: None,
    )

    dados_decisoes = yaml.safe_load(decisoes.read_text(encoding="utf-8"))
    assert "users.active" in dados_decisoes["confirmadas"]
    assert "users.remote" not in dados_decisoes["confirmadas"]
    assert resumo == {"confirmadas": 1, "rejeitadas": 0, "pendentes": 1}


def test_revisar_booleanos_filtra_por_tabela(tmp_path: Path) -> None:
    relatorio = tmp_path / "relatorio.yaml"
    decisoes = tmp_path / "decisoes.yaml"
    _escrever_relatorio(
        relatorio,
        [
            _investigacao_booleana("prazos_log", "ativo"),
            _investigacao_booleana("users", "active"),
        ],
    )

    respostas = iter(["s"])
    resumo = revisar_booleanos_interativamente(
        relatorio,
        caminho_decisoes=decisoes,
        tabela="prazos_log",
        input_fn=lambda _prompt: next(respostas),
        output_fn=lambda _msg: None,
    )

    dados_decisoes = yaml.safe_load(decisoes.read_text(encoding="utf-8"))
    assert "prazos_log.ativo" in dados_decisoes["confirmadas"]
    assert "users.active" not in dados_decisoes["confirmadas"]
    assert resumo == {"confirmadas": 1, "rejeitadas": 0, "pendentes": 0}
