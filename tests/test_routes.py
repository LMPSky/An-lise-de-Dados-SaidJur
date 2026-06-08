"""Testes de integração para as rotas FastAPI usando SQLite em memória."""

from __future__ import annotations

import json
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


# ── Setup do banco de testes (SQLite) ─────────────────────────────────────────

def _criar_engine_sqlite() -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("""
            CREATE TABLE clientes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT NOT NULL,
                email     TEXT,
                cidade    TEXT,
                criado_em TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE processos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                numero    TEXT NOT NULL,
                status    TEXT,
                descricao TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE busunitaccess (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userid INTEGER NOT NULL,
                perfil TEXT,
                FOREIGN KEY(userid) REFERENCES users(id)
            )
        """))
        conn.execute(text("""
            INSERT INTO clientes (nome, email, cidade, criado_em) VALUES
            ('João Silva', 'joao@ex.com', 'São Paulo', '2023-01-01 10:00:00'),
            ('Maria Souza', 'maria@ex.com', 'Rio de Janeiro', '2023-02-01 11:00:00'),
            ('Carlos Andrade', 'carlos@ex.com', 'Belo Horizonte', '2023-03-01 12:00:00')
        """))
        conn.execute(text("""
            INSERT INTO processos (numero, status, descricao) VALUES
            ('0001234-00.2023.8', 'em andamento', 'Ação de cobrança'),
            ('0002345-00.2023.8', 'concluído', 'Divórcio consensual')
        """))
        conn.execute(text("INSERT INTO users (nome) VALUES ('Ana'), ('Bruno')"))
        conn.execute(text("INSERT INTO busunitaccess (userid, perfil) VALUES (1, 'admin'), (2, 'leitura')"))
        conn.commit()
    return engine


# ── Fixtures e mocks ──────────────────────────────────────────────────────────

def _listar_tabelas_sqlite(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        resultado = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tabelas = []
        for row in resultado:
            nome = row[0]
            if nome.startswith("sqlite_"):
                continue
            total = conn.execute(text(f"SELECT COUNT(*) FROM `{nome}`")).scalar_one()
            tabelas.append({"nome": nome, "linhas_aprox": total, "tamanho_mb": 0.0})
    return tabelas


def _listar_colunas_sqlite(engine: Engine, nome_tabela: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        resultado = conn.execute(text(f"PRAGMA table_info(`{nome_tabela}`)"))
        return [
            {
                "nome": row[1],
                "tipo": row[2],
                "nulo": row[3] == 0,
                "chave": "PRI" if row[5] == 1 else "",
            }
            for row in resultado
        ]


def _tabelas_validas_sqlite(engine: Engine) -> set[str]:
    return {t["nome"] for t in _listar_tabelas_sqlite(engine)}


def _colunas_validas_sqlite(engine: Engine, nome_tabela: str) -> set[str]:
    return {c["nome"] for c in _listar_colunas_sqlite(engine, nome_tabela)}


def _colunas_texto_sqlite(
    engine: Engine,
    nome_tabela: str,
    incluir_colunas_grandes: bool = False,
) -> list[str]:
    _ = incluir_colunas_grandes
    tipos_texto = {"text", "varchar", "char", "json"}
    colunas = _listar_colunas_sqlite(engine, nome_tabela)
    return [
        c["nome"]
        for c in colunas
        if c["tipo"].lower().split("(")[0] in tipos_texto
    ]


def _listar_fks_sqlite(engine: Engine, nome_tabela: str) -> list[dict[str, str]]:
    with engine.connect() as conn:
        resultado = conn.execute(text(f"PRAGMA foreign_key_list(`{nome_tabela}`)"))
        return [
            {
                "coluna": row[3],
                "tabela_referenciada": row[2],
                "coluna_referenciada": row[4],
            }
            for row in resultado
        ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.api import main as main_module
    import src.api.routes_tables as rt_tables
    import src.api.routes_data as rt_data
    import src.api.routes_search as rt_search
    import src.api.routes_export as rt_export
    import src.api.routes_stats as rt_stats
    import src.db as db_module

    engine = _criar_engine_sqlite()

    monkeypatch.setattr(db_module, "listar_tabelas", _listar_tabelas_sqlite)
    monkeypatch.setattr(db_module, "listar_colunas", _listar_colunas_sqlite)
    monkeypatch.setattr(db_module, "tabelas_validas", _tabelas_validas_sqlite)
    monkeypatch.setattr(db_module, "colunas_validas", _colunas_validas_sqlite)
    monkeypatch.setattr(db_module, "colunas_texto", _colunas_texto_sqlite)
    monkeypatch.setattr(db_module, "listar_chaves_estrangeiras", _listar_fks_sqlite)

    for modulo in [rt_tables, rt_data, rt_search, rt_export, rt_stats]:
        if hasattr(modulo, "listar_tabelas"):
            monkeypatch.setattr(modulo, "listar_tabelas", _listar_tabelas_sqlite)
        if hasattr(modulo, "listar_colunas"):
            monkeypatch.setattr(modulo, "listar_colunas", _listar_colunas_sqlite)
        if hasattr(modulo, "tabelas_validas"):
            monkeypatch.setattr(modulo, "tabelas_validas", _tabelas_validas_sqlite)
        if hasattr(modulo, "colunas_validas"):
            monkeypatch.setattr(modulo, "colunas_validas", _colunas_validas_sqlite)
        if hasattr(modulo, "colunas_texto"):
            monkeypatch.setattr(modulo, "colunas_texto", _colunas_texto_sqlite)
        if hasattr(modulo, "listar_chaves_estrangeiras"):
            monkeypatch.setattr(modulo, "listar_chaves_estrangeiras", _listar_fks_sqlite)

    from src.api.main import app
    app.state.engine = engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestRotaTabelas:
    def test_lista_tabelas_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas")
        assert resp.status_code == 200

    def test_colunas_tabela_existente(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/colunas")
        assert resp.status_code == 200
        nomes = [c["nome"] for c in resp.json()]
        assert "nome" in nomes

    def test_fks_tabela(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/busunitaccess/fks")
        assert resp.status_code == 200
        dados = resp.json()
        assert dados[0]["coluna"] == "userid"
        assert dados[0]["tabela_referenciada"] == "users"


class TestRotaDados:
    def test_linhas_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas")
        assert resp.status_code == 200

    def test_total_registros(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas")
        assert resp.json()["total"] == 3

    def test_filtro_contem(self, client: TestClient) -> None:
        filtros = json.dumps({"nome": {"op": "contem", "valor": "João"}})
        resp = client.get(f"/api/tabelas/clientes/linhas?filtros={filtros}")
        assert resp.json()["total"] == 1


class TestRotaBusca:
    def test_busca_retorna_lista(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=João")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_busca_streaming_retorna_eventos(self, client: TestClient) -> None:
        resp = client.get("/api/busca/stream?q=João")
        assert resp.status_code == 200
        assert "\"tipo\": \"progress\"" in resp.text
        assert "\"tipo\": \"done\"" in resp.text


class TestRotaExportar:
    def test_exportar_csv_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/clientes?formato=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


class TestRotasNovas:
    def test_dashboard(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        dados = resp.json()
        assert "estatisticas" in dados
        assert "maiores_tabelas" in dados

    def test_sql_select(self, client: TestClient) -> None:
        resp = client.post("/api/sql", json={"query": "SELECT id, nome FROM clientes ORDER BY id"})
        assert resp.status_code == 200
        dados = resp.json()
        assert "linhas" in dados
        assert dados["total"] >= 1

    def test_sql_rejeita_dml(self, client: TestClient) -> None:
        resp = client.post("/api/sql", json={"query": "DELETE FROM clientes"})
        assert resp.status_code == 400

    def test_stats_coluna(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/colunas/nome/stats")
        assert resp.status_code == 200
        dados = resp.json()
        assert "nao_nulos" in dados
        assert "top_5" in dados


class TestRotaRaiz:
    def test_raiz_serve_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code in (200, 404)
