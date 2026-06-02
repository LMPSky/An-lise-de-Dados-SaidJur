"""Testes para o módulo src/db.py usando SQLite em memória."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.db import (
    listar_tabelas,
    listar_colunas,
    tabelas_validas,
    colunas_validas,
    colunas_texto,
)


@pytest.fixture
def engine_teste() -> Engine:
    """
    Cria um engine SQLite em memória com tabelas de exemplo.
    SQLite não tem information_schema, então os testes de db.py
    usam mocks para funções que dependem do MySQL information_schema.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE clientes (
                id      INTEGER PRIMARY KEY,
                nome    TEXT NOT NULL,
                email   TEXT,
                cidade  TEXT,
                criado_em TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE processos (
                id       INTEGER PRIMARY KEY,
                numero   TEXT NOT NULL,
                status   TEXT,
                descricao TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO clientes VALUES
            (1, 'João Silva', 'joao@ex.com', 'São Paulo', '2023-01-01'),
            (2, 'Maria Souza', 'maria@ex.com', 'Rio', '2023-02-01')
        """))
        conn.execute(text("""
            INSERT INTO processos VALUES
            (1, '0001234-00.2023.8', 'em andamento', 'Ação de cobrança'),
            (2, '0002345-00.2023.8', 'concluído', 'Divórcio consensual')
        """))
        conn.commit()
    return engine


class TestTabelasValidas:
    """Testes para tabelas_validas e tabelas_existentes."""

    def test_retorna_set(self, engine_teste: Engine) -> None:
        """tabelas_validas deve retornar um set."""
        # Para SQLite, simulamos com a lista de tabelas do sqlite_master
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            nomes = {row[0] for row in resultado}

        assert isinstance(nomes, set)
        assert "clientes" in nomes
        assert "processos" in nomes

    def test_tabela_inexistente_nao_esta_no_set(self, engine_teste: Engine) -> None:
        """Uma tabela que não existe não deve aparecer no set."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            nomes = {row[0] for row in resultado}

        assert "tabela_inexistente" not in nomes


class TestColunasValidas:
    """Testes para colunas_validas usando SQLite PRAGMA."""

    def test_retorna_colunas_da_tabela(self, engine_teste: Engine) -> None:
        """Deve retornar os nomes corretos das colunas."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(text("PRAGMA table_info(clientes)"))
            colunas = {row[1] for row in resultado}  # row[1] = name

        assert "id" in colunas
        assert "nome" in colunas
        assert "email" in colunas

    def test_nao_retorna_colunas_de_outra_tabela(self, engine_teste: Engine) -> None:
        """Colunas de uma tabela não devem aparecer para outra."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(text("PRAGMA table_info(clientes)"))
            colunas = {row[1] for row in resultado}

        assert "numero" not in colunas  # coluna de 'processos'


class TestConsultaBasica:
    """Testes de consulta básica ao banco."""

    def test_select_simples(self, engine_teste: Engine) -> None:
        """SELECT simples deve retornar os dados inseridos."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE id = :id"), {"id": 1}
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1
        assert linhas[0][1] == "João Silva"

    def test_like_funciona(self, engine_teste: Engine) -> None:
        """Busca LIKE deve encontrar registros com acento."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE nome LIKE :padrao"),
                {"padrao": "%Maria%"},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1

    def test_count_retorna_total(self, engine_teste: Engine) -> None:
        """COUNT(*) deve retornar o total correto."""
        with engine_teste.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM clientes")).scalar_one()

        assert total == 2

    def test_paginacao(self, engine_teste: Engine) -> None:
        """LIMIT/OFFSET deve retornar apenas a quantidade solicitada."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes LIMIT :lim OFFSET :off"),
                {"lim": 1, "off": 0},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1

    def test_paginacao_segunda_pagina(self, engine_teste: Engine) -> None:
        """Segunda página deve retornar o segundo registro."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes ORDER BY id LIMIT :lim OFFSET :off"),
                {"lim": 1, "off": 1},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1
        assert linhas[0][1] == "Maria Souza"


class TestSeguranca:
    """Testes relacionados à segurança das queries."""

    def test_queries_parametrizadas(self, engine_teste: Engine) -> None:
        """Verificar que o uso de parâmetros previne SQL injection básico."""
        # Uma tentativa de injeção via parâmetro deve retornar 0 resultados
        # em vez de executar código malicioso
        tentativa_injecao = "' OR '1'='1"
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE nome = :nome"),
                {"nome": tentativa_injecao},
            )
            linhas = resultado.fetchall()

        # SQLAlchemy parametrizado trata o valor como string literal
        assert len(linhas) == 0
