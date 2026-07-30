"""Testes unitários para classificação da auditoria de traduções."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pymysql

from auditar_traducoes import (
    _eh_erro_de_conexao,
    _garantir_conexao_viva,
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


# ── Testes da lógica de reconexão automática ───────────────────────────────


def test_eh_erro_de_conexao_para_codigos_conhecidos() -> None:
    """_eh_erro_de_conexao deve retornar True para os códigos MySQL de perda de conexão."""
    for codigo in (2006, 2013, 2003, 2055, 0):
        exc = pymysql.err.OperationalError(codigo, "connection lost")
        assert _eh_erro_de_conexao(exc), f"Código {codigo} deveria ser erro de conexão"

    exc_interface = pymysql.err.InterfaceError(2006, "socket closed")
    assert _eh_erro_de_conexao(exc_interface)


def test_eh_erro_de_conexao_retorna_false_para_erros_de_dados() -> None:
    """Erros de dados (ex: SQL inválido) não devem ser classificados como conexão perdida."""
    exc_dados = pymysql.err.OperationalError(1064, "syntax error")
    assert not _eh_erro_de_conexao(exc_dados)

    exc_generico = ValueError("não é erro do pymysql")
    assert not _eh_erro_de_conexao(exc_generico)


def test_garantir_conexao_viva_retorna_mesma_conexao_quando_ping_ok() -> None:
    """Se conn.ping(reconnect=True) não levanta exceção, a conexão original é retornada."""
    conn_mock = MagicMock()
    conn_mock.ping.return_value = None  # ping bem-sucedido

    resultado = _garantir_conexao_viva(conn_mock)

    conn_mock.ping.assert_called_once_with(reconnect=True)
    assert resultado is conn_mock


def test_garantir_conexao_viva_reabre_conexao_quando_ping_falha() -> None:
    """Se conn.ping levanta exceção, _garantir_conexao_viva deve criar nova conexão."""
    conn_mock = MagicMock()
    conn_mock.ping.side_effect = pymysql.err.OperationalError(2006, "server gone")

    nova_conn = MagicMock()

    with patch("auditar_traducoes._conectar_mysql", return_value=nova_conn) as mock_conectar:
        resultado = _garantir_conexao_viva(conn_mock)

    mock_conectar.assert_called_once()
    assert resultado is nova_conn
    # Deve ter tentado fechar a conexão antiga
    conn_mock.close.assert_called_once()


def test_garantir_conexao_viva_fecha_conn_mesmo_se_close_falhar() -> None:
    """_garantir_conexao_viva não deve propagar exceção de conn.close()."""
    conn_mock = MagicMock()
    conn_mock.ping.side_effect = Exception("ping timeout")
    conn_mock.close.side_effect = Exception("já fechada")

    nova_conn = MagicMock()

    with patch("auditar_traducoes._conectar_mysql", return_value=nova_conn):
        resultado = _garantir_conexao_viva(conn_mock)

    assert resultado is nova_conn


def test_classificar_coluna_com_novas_traducoes() -> None:
    """Colunas adicionadas pelo relatório de auditoria devem ser classificadas como traduzidas."""
    assert classificar_traducao_coluna("approved") == "traduzido_corretamente"
    assert classificar_traducao_coluna("viewed") == "traduzido_corretamente"
    assert classificar_traducao_coluna("task") == "traduzido_corretamente"
    assert classificar_traducao_coluna("activity") == "traduzido_corretamente"
    assert classificar_traducao_coluna("hearingtype") == "traduzido_corretamente"
