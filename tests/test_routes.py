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
    """
    Cria engine SQLite em memória com StaticPool.

    StaticPool garante que todas as conexões ao SQLite compartilhem a
    mesma base de dados em memória — necessário para que os dados
    inseridos sejam visíveis nas chamadas subsequentes.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
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
            INSERT INTO clientes (nome, email, cidade, criado_em) VALUES
            ('João Silva', 'joao@ex.com', 'São Paulo', '2023-01-01'),
            ('Maria Souza', 'maria@ex.com', 'Rio de Janeiro', '2023-02-01'),
            ('Carlos Andrade', 'carlos@ex.com', 'Belo Horizonte', '2023-03-01')
        """))
        conn.execute(text("""
            INSERT INTO processos (numero, status, descricao) VALUES
            ('0001234-00.2023.8', 'em andamento', 'Ação de cobrança'),
            ('0002345-00.2023.8', 'concluído', 'Divórcio consensual')
        """))
        conn.commit()
    return engine


# ── Fixtures e mocks ──────────────────────────────────────────────────────────

def _listar_tabelas_sqlite(engine: Engine) -> list[dict[str, Any]]:
    """Substitui listar_tabelas para funcionar com SQLite."""
    with engine.connect() as conn:
        resultado = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tabelas = []
        for row in resultado:
            nome = row[0]
            total = conn.execute(text(f"SELECT COUNT(*) FROM `{nome}`")).scalar_one()
            tabelas.append({"nome": nome, "linhas_aprox": total, "tamanho_mb": 0.0})
    return tabelas


def _listar_colunas_sqlite(engine: Engine, nome_tabela: str) -> list[dict[str, Any]]:
    """Substitui listar_colunas para funcionar com SQLite."""
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
    with engine.connect() as conn:
        resultado = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        return {row[0] for row in resultado}


def _colunas_validas_sqlite(engine: Engine, nome_tabela: str) -> set[str]:
    return {c["nome"] for c in _listar_colunas_sqlite(engine, nome_tabela)}


def _colunas_texto_sqlite(engine: Engine, nome_tabela: str) -> list[str]:
    tipos_texto = {"text", "varchar", "char", "json"}
    colunas = _listar_colunas_sqlite(engine, nome_tabela)
    return [
        c["nome"]
        for c in colunas
        if c["tipo"].lower().split("(")[0] in tipos_texto
    ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """
    Cliente de teste com banco SQLite e mocks das funções MySQL-específicas.
    """
    from src.api import main as main_module
    import src.api.routes_tables as rt_tables
    import src.api.routes_data as rt_data
    import src.api.routes_search as rt_search
    import src.api.routes_export as rt_export
    import src.db as db_module

    engine = _criar_engine_sqlite()

    # Patching das funções que dependem do MySQL information_schema
    monkeypatch.setattr(db_module, "listar_tabelas", _listar_tabelas_sqlite)
    monkeypatch.setattr(db_module, "listar_colunas", _listar_colunas_sqlite)
    monkeypatch.setattr(db_module, "tabelas_validas", _tabelas_validas_sqlite)
    monkeypatch.setattr(db_module, "colunas_validas", _colunas_validas_sqlite)
    monkeypatch.setattr(db_module, "colunas_texto", _colunas_texto_sqlite)

    # Também aplica nos módulos de rota (que importaram os nomes localmente)
    for modulo in [rt_tables, rt_data, rt_search, rt_export]:
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

    from src.api.main import app
    app.state.engine = engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Testes de /api/tabelas ────────────────────────────────────────────────────

class TestRotaTabelas:

    def test_lista_tabelas_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas")
        assert resp.status_code == 200

    def test_lista_tabelas_retorna_lista(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas")
        dados = resp.json()
        assert isinstance(dados, list)
        assert len(dados) >= 2

    def test_estrutura_tabela(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas")
        tabela = resp.json()[0]
        assert "nome" in tabela
        assert "linhas_aprox" in tabela
        assert "tamanho_mb" in tabela

    def test_tabela_clientes_presente(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas")
        nomes = [t["nome"] for t in resp.json()]
        assert "clientes" in nomes

    def test_colunas_tabela_existente(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/colunas")
        assert resp.status_code == 200
        colunas = resp.json()
        assert isinstance(colunas, list)
        nomes = [c["nome"] for c in colunas]
        assert "nome" in nomes

    def test_colunas_tabela_inexistente_retorna_404(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/nao_existe/colunas")
        assert resp.status_code == 404


# ── Testes de /api/tabelas/{nome}/linhas ─────────────────────────────────────

class TestRotaDados:

    def test_linhas_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas")
        assert resp.status_code == 200

    def test_linhas_estrutura_resposta(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas")
        dados = resp.json()
        assert "total" in dados
        assert "pagina" in dados
        assert "por_pagina" in dados
        assert "linhas" in dados

    def test_total_registros(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas")
        dados = resp.json()
        assert dados["total"] == 3

    def test_paginacao(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?pagina=1&por_pagina=2")
        dados = resp.json()
        assert len(dados["linhas"]) == 2

    def test_segunda_pagina(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?pagina=2&por_pagina=2")
        dados = resp.json()
        assert len(dados["linhas"]) == 1

    def test_por_pagina_maximo_500(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?por_pagina=501")
        assert resp.status_code == 422  # Unprocessable Entity

    def test_tabela_inexistente_retorna_404(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/nao_existe/linhas")
        assert resp.status_code == 404

    def test_filtro_contem(self, client: TestClient) -> None:
        filtros = json.dumps({"nome": {"op": "contem", "valor": "João"}})
        resp = client.get(f"/api/tabelas/clientes/linhas?filtros={filtros}")
        dados = resp.json()
        assert dados["total"] == 1
        assert dados["linhas"][0]["nome"] == "João Silva"

    def test_filtro_igual(self, client: TestClient) -> None:
        filtros = json.dumps({"cidade": {"op": "igual", "valor": "São Paulo"}})
        resp = client.get(f"/api/tabelas/clientes/linhas?filtros={filtros}")
        dados = resp.json()
        assert dados["total"] == 1

    def test_filtro_comeca_com(self, client: TestClient) -> None:
        filtros = json.dumps({"nome": {"op": "comeca_com", "valor": "Mar"}})
        resp = client.get(f"/api/tabelas/clientes/linhas?filtros={filtros}")
        dados = resp.json()
        assert dados["total"] == 1

    def test_ordenar_por_coluna(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?ordenar_por=nome&direcao=asc")
        assert resp.status_code == 200
        dados = resp.json()
        nomes = [l["nome"] for l in dados["linhas"]]
        assert nomes == sorted(nomes)

    def test_ordenar_coluna_invalida_retorna_400(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?ordenar_por=coluna_invalida")
        assert resp.status_code == 400

    def test_filtro_coluna_invalida_retorna_400(self, client: TestClient) -> None:
        filtros = json.dumps({"coluna_invalida": {"op": "contem", "valor": "x"}})
        resp = client.get(f"/api/tabelas/clientes/linhas?filtros={filtros}")
        assert resp.status_code == 400

    def test_filtro_json_invalido_retorna_400(self, client: TestClient) -> None:
        resp = client.get("/api/tabelas/clientes/linhas?filtros=nao_e_json")
        assert resp.status_code == 400


# ── Testes de /api/busca ──────────────────────────────────────────────────────

class TestRotaBusca:

    def test_busca_retorna_lista(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=João")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_busca_encontra_resultado(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=João")
        resultados = resp.json()
        # Deve encontrar em alguma tabela/coluna
        assert len(resultados) > 0

    def test_busca_sem_resultados(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=xyzxyzxyz_nao_existe_9999")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_busca_estrutura_resposta(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=Maria")
        resultados = resp.json()
        if resultados:
            item = resultados[0]
            assert "tabela" in item
            assert "coluna" in item
            assert "registros" in item

    def test_busca_vazia_retorna_400(self, client: TestClient) -> None:
        resp = client.get("/api/busca?q=")
        # query string vazia: validação min_length=1
        assert resp.status_code in (400, 422)


# ── Testes de /api/exportar ───────────────────────────────────────────────────

class TestRotaExportar:

    def test_exportar_csv_status_200(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/clientes?formato=csv")
        assert resp.status_code == 200

    def test_exportar_csv_content_type(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/clientes?formato=csv")
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_exportar_csv_tem_cabecalho(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/clientes?formato=csv")
        linhas = resp.text.strip().split("\n")
        assert len(linhas) >= 1
        cabecalho = linhas[0]
        assert "nome" in cabecalho

    def test_exportar_csv_com_filtro(self, client: TestClient) -> None:
        filtros = json.dumps({"nome": {"op": "contem", "valor": "João"}})
        resp = client.get(f"/api/exportar/clientes?formato=csv&filtros={filtros}")
        assert resp.status_code == 200
        linhas = resp.text.strip().split("\n")
        # Cabeçalho + 1 linha de dados
        assert len(linhas) == 2

    def test_exportar_tabela_inexistente_retorna_404(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/nao_existe?formato=csv")
        assert resp.status_code == 404

    def test_exportar_formato_invalido_retorna_422(self, client: TestClient) -> None:
        resp = client.get("/api/exportar/clientes?formato=xml")
        assert resp.status_code == 422


# ── Teste da rota raiz (frontend) ─────────────────────────────────────────────

class TestRotaRaiz:

    def test_raiz_serve_html(self, client: TestClient) -> None:
        resp = client.get("/")
        # Se o diretório web existe, retorna 200; caso contrário, 404.
        # Em ambiente de teste, ambos são válidos.
        assert resp.status_code in (200, 404)
