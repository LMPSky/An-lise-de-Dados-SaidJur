"""Testes da investigação assistida de pendências de tradução."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import yaml

from src.investigacao_pendencias import (
    PendenciaEnum,
    aplicar_decisoes_em_dicionario,
    carregar_pendencias_enum,
    gerar_template_decisoes,
    investigar_pendencias,
    selecionar_colunas_pista,
    listar_colunas_tabela,
)



def test_carregar_pendencias_enum_do_relatorio_yaml(tmp_path: Path) -> None:
    caminho = tmp_path / "relatorio.yaml"
    caminho.write_text(
        yaml.safe_dump(
            {
                "pendencias": {
                    "paymenttype": {
                        "enums": [
                            {
                                "coluna": "code",
                                "valores_pendentes": [
                                    {"valor": "Bol", "motivo": "sem_entrada_no_dicionario"},
                                    {"valor": "Bol", "motivo": "sem_entrada_no_dicionario"},
                                    {"valor": "chq", "motivo": "sem_entrada_no_dicionario"},
                                ],
                            }
                        ]
                    }
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    pendencias = carregar_pendencias_enum(caminho)

    assert pendencias == [
        PendenciaEnum("paymenttype", "code", "Bol", "sem_entrada_no_dicionario"),
        PendenciaEnum("paymenttype", "code", "chq", "sem_entrada_no_dicionario"),
    ]



def test_selecionar_colunas_pista_prioriza_nome_e_descricao() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                description TEXT,
                created_at TEXT
            )
        """))
        conn.commit()

    colunas = listar_colunas_tabela(engine, "paymenttype")
    candidatas = selecionar_colunas_pista(colunas, "code")

    assert "name" in candidatas
    assert "description" in candidatas



def _engine_pagamento() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                description TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO paymenttype (id, code, name, description) VALUES
            (1, 'Bol', 'Boleto', 'Pagamento por boleto bancário'),
            (2, 'Bol', 'Boleto', 'Pagamento por boleto bancário'),
            (3, 'chq', 'Cheque', 'Pagamento por cheque')
        """))
        conn.commit()
    return engine



def test_investigar_pendencias_gera_sugestao_de_alta_confianca() -> None:
    engine = _engine_pagamento()
    pendencias = [PendenciaEnum("paymenttype", "code", "Bol")]

    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=5)

    assert relatorio["resumo"]["total_pendencias"] == 1
    assert relatorio["resumo"]["alta_confianca"] == 1
    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["traducao_sugerida"] == "Boleto"
    assert item["linhas_exemplo"]



def test_investigar_pendencias_marca_sem_pista_quando_nao_ha_coluna_textual() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE config_status (
                id INTEGER PRIMARY KEY,
                code INTEGER,
                phase_id INTEGER,
                ordem INTEGER
            )
        """))
        conn.execute(text("INSERT INTO config_status (id, code, phase_id, ordem) VALUES (1, 2, 5, 10)"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("config_status", "code", "2")])

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "sem_pista_encontrada"


def test_investigar_pendencias_marca_pista_unica_quando_ha_apenas_uma_linha_util() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO paymenttype (id, code, name) VALUES (1, 'dda', 'Débito Direto')"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("paymenttype", "code", "dda")])

    assert relatorio["resumo"]["pista_unica"] == 1
    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "pista_unica"
    assert item["sugestao"]["traducao_sugerida"] == "Débito Direto"


def test_aplicar_decisoes_em_dicionario_aplica_somente_aprovadas() -> None:
    dicionarios = {"paymenttype": {"code": {"deb": "Débito"}}}
    decisoes = [
        {
            "tabela": "paymenttype",
            "coluna": "code",
            "valor": "Bol",
            "traducao_sugerida": "Boleto",
            "decisao": "aplicar",
        },
        {
            "tabela": "paymenttype",
            "coluna": "code",
            "valor": "chq",
            "traducao_sugerida": "Cheque",
            "decisao": "pular",
        },
    ]

    atualizados, aplicadas = aplicar_decisoes_em_dicionario(dicionarios, decisoes)

    assert atualizados["paymenttype"]["code"]["Bol"] == "Boleto"
    assert "chq" not in atualizados["paymenttype"]["code"]
    assert len(aplicadas) == 1



def test_gerar_template_decisoes() -> None:
    relatorio = {
        "investigacoes": [
            {
                "tabela": "paymenttype",
                "coluna": "code",
                "valor": "Bol",
                "sugestao": {
                    "status": "alta_confianca",
                    "traducao_sugerida": "Boleto",
                },
            }
        ]
    }

    template = gerar_template_decisoes(relatorio)

    assert template["decisoes"][0]["decisao"] == "pendente"
    assert template["decisoes"][0]["traducao_sugerida"] == "Boleto"
