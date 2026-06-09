"""Testes para as rotas de resolução de labels (POST /api/labels/resolver)."""

from __future__ import annotations

from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


# ── Setup do banco de testes ──────────────────────────────────────────────────

def _criar_engine_sqlite() -> Engine:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("""
            CREATE TABLE cities (
                id    INTEGER PRIMARY KEY,
                name  TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE lawsuit_types (
                id     INTEGER PRIMARY KEY,
                nome   TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE no_label_table (
                id  INTEGER PRIMARY KEY,
                val INTEGER
            )
        """))
        conn.execute(text("""
            INSERT INTO cities VALUES (1, 'São Paulo'), (2, 'Rio de Janeiro'), (3665, 'Belo Horizonte')
        """))
        conn.execute(text("""
            INSERT INTO lawsuit_types VALUES (6, 'Cível'), (7, 'Trabalhista')
        """))
        conn.execute(text("""
            INSERT INTO no_label_table VALUES (1, 100)
        """))
        conn.commit()
    return engine


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


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.api import main as main_module
    import src.api.routes_labels as rt_labels
    import src.db as db_module

    engine = _criar_engine_sqlite()

    # Clear caches between tests
    db_module._CACHE_COLUNA_LABEL.clear()
    db_module._CACHE_LABELS.clear()

    monkeypatch.setattr(db_module, "listar_tabelas", _listar_tabelas_sqlite)
    monkeypatch.setattr(db_module, "listar_colunas", _listar_colunas_sqlite)
    monkeypatch.setattr(db_module, "tabelas_validas", _tabelas_validas_sqlite)
    monkeypatch.setattr(db_module, "colunas_validas", _colunas_validas_sqlite)

    for modulo in [rt_labels]:
        if hasattr(modulo, "tabelas_validas"):
            monkeypatch.setattr(modulo, "tabelas_validas", _tabelas_validas_sqlite)
        if hasattr(modulo, "colunas_validas"):
            monkeypatch.setattr(modulo, "colunas_validas", _colunas_validas_sqlite)

    from src.api.main import app
    app.state.engine = engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Testes ────────────────────────────────────────────────────────────────────

class TestResolverLabels:
    def test_resolve_ids_existentes(self, client: TestClient) -> None:
        """IDs existentes devem retornar seus labels."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "cities", "coluna_chave": "id", "ids": [1, 2, 3665]},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "cities" in data
        assert data["cities"]["1"] == "São Paulo"
        assert data["cities"]["2"] == "Rio de Janeiro"
        assert data["cities"]["3665"] == "Belo Horizonte"

    def test_resolve_ids_inexistentes(self, client: TestClient) -> None:
        """IDs que não existem não devem aparecer no mapa retornado."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "cities", "coluna_chave": "id", "ids": [9999]},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        # tabela não aparece ou mapa está vazio para esse ID
        assert data.get("cities", {}).get("9999") is None

    def test_multiplas_tabelas(self, client: TestClient) -> None:
        """Múltiplas tabelas no mesmo request devem ser resolvidas."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "cities", "coluna_chave": "id", "ids": [1]},
                {"tabela": "lawsuit_types", "coluna_chave": "id", "ids": [6, 7]},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cities"]["1"] == "São Paulo"
        assert data["lawsuit_types"]["6"] == "Cível"
        assert data["lawsuit_types"]["7"] == "Trabalhista"

    def test_tabela_inexistente_retorna_404(self, client: TestClient) -> None:
        """Tabela não existente deve retornar 404."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "tabela_nao_existe", "coluna_chave": "id", "ids": [1]},
            ]
        })
        assert resp.status_code == 404

    def test_coluna_chave_inexistente_retorna_400(self, client: TestClient) -> None:
        """Coluna chave não existente deve retornar 400."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "cities", "coluna_chave": "coluna_que_nao_existe", "ids": [1]},
            ]
        })
        assert resp.status_code == 400

    def test_tabela_sem_coluna_label_retorna_vazio(self, client: TestClient) -> None:
        """Tabela sem coluna de label não deve quebrar — retorna mapa vazio."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "no_label_table", "coluna_chave": "id", "ids": [1]},
            ]
        })
        assert resp.status_code == 200
        # Sem label, a tabela não aparece no mapa (nenhum label resolvido)
        data = resp.json()
        assert data.get("no_label_table", {}) == {}

    def test_lista_vazia_de_ids(self, client: TestClient) -> None:
        """Lista vazia de IDs deve retornar resposta vazia sem erro."""
        resp = client.post("/api/labels/resolver", json={
            "resolucoes": [
                {"tabela": "cities", "coluna_chave": "id", "ids": []},
            ]
        })
        assert resp.status_code == 200

    def test_resolucoes_vazias(self, client: TestClient) -> None:
        """Lista vazia de resoluções deve retornar dict vazio."""
        resp = client.post("/api/labels/resolver", json={"resolucoes": []})
        assert resp.status_code == 200
        assert resp.json() == {}
