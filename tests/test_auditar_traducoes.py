"""Testes unitários para classificação da auditoria de traduções."""

from __future__ import annotations

from auditar_traducoes import (
    avaliar_pendencias_enum,
    classificar_traducao_coluna,
    traducao_parece_ingles,
    traducao_pendente_placeholder,
)


def test_classifica_traducao_completa() -> None:
    assert classificar_traducao_coluna("publication_id", "ID da Publicação") == "traduzido_corretamente"


def test_classifica_traducao_parcial() -> None:
    assert classificar_traducao_coluna("search_custom_id", "Busca Custom ID") == "parcialmente_traduzido"


def test_classifica_sem_traducao_real() -> None:
    assert classificar_traducao_coluna("unknown_id", "Unknown ID") == "nao_traduzido"


def test_detecta_placeholder_pendente() -> None:
    assert traducao_pendente_placeholder("refuse_request", "[refuse_request]")
    assert not traducao_pendente_placeholder("refuse_request", "Recusar solicitação")


def test_detecta_traducao_possivelmente_ingles() -> None:
    assert traducao_parece_ingles("Pending")
    assert not traducao_parece_ingles("Pendente")


def test_avalia_pendencias_enum() -> None:
    pendencias = avaliar_pendencias_enum(
        valores_amostra=["p", "m", "pending", "x"],
        dicionario_coluna={
            "p": "Publicação",
            "m": "[m]",
            "pending": "Pending",
        },
    )

    assert pendencias == [
        {"valor": "m", "traducao_atual": "[m]", "motivo": "placeholder_pendente"},
        {
            "valor": "pending",
            "traducao_atual": "Pending",
            "motivo": "traducao_possivelmente_em_ingles",
        },
        {"valor": "x", "traducao_atual": "", "motivo": "sem_entrada_no_dicionario"},
    ]
