"""Aplicação principal FastAPI: configura rotas, CORS, logging e arquivos estáticos."""

from __future__ import annotations

import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import CONFIG
from src.db import criar_engine
from src.api.routes_tables import router as router_tabelas
from src.api.routes_data import router as router_dados
from src.api.routes_search import router as router_busca
from src.api.routes_export import router as router_exportar
from src.api.routes_dashboard import router as router_dashboard
from src.api.routes_sql import router as router_sql
from src.api.routes_stats import router as router_stats
from src.api.routes_labels import router as router_labels
from src.api.routes_dicionarios import router as router_dicionarios

# ── Logging ─────────────────────────────────────────────────────────────────

_RAIZ = Path(__file__).resolve().parent.parent.parent
_LOGS_DIR = _RAIZ / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_handler_arquivo = logging.handlers.TimedRotatingFileHandler(
    filename=_LOGS_DIR / "app.log",
    when="midnight",
    backupCount=30,
    encoding="utf-8",
)
_handler_arquivo.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
_handler_console = logging.StreamHandler()
_handler_console.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)

logging.basicConfig(level=logging.INFO, handlers=[_handler_arquivo, _handler_console])
logger = logging.getLogger("saidjur")

# ── Engine global ────────────────────────────────────────────────────────────

engine = criar_engine()

# ── Ciclo de vida da aplicação ────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida do servidor (inicialização e encerramento)."""
    cfg_servidor = CONFIG.get("servidor", {})
    cfg_banco = CONFIG.get("banco", {})
    
    host = cfg_servidor.get("host", "0.0.0.0")
    porta = cfg_servidor.get("porta", 8000)
    nome_banco = cfg_banco.get("nome", "saidjur")
    
    logger.info(
        "Servidor iniciado em http://%s:%s — banco: %s",
        host,
        porta,
        nome_banco,
    )
    yield
    engine.dispose()
    logger.info("Servidor encerrado.")

# ── Aplicação FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="Visualizador de Dados SaidJur",
    description="API para visualização e pesquisa de dados do banco SaidJur.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Por padrão, permite acesso remoto da rede. Para restringir apenas localhost:
# origins_permitidas = ["http://localhost:8000", "http://127.0.0.1:8000"]

_origens_permitidas = ["*"]  # Permite de qualquer origem (útil para redes internas)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_permitidas,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_excecoes_nao_tratadas(request: Request, call_next):
    """Registra exceções não tratadas para facilitar diagnóstico em produção."""
    try:
        return await call_next(request)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Exceção não tratada em %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor. Veja logs/app.log."},
        )

# ── Injeção do engine nas rotas ───────────────────────────────────────────────

app.state.engine = engine

# ── Rotas da API ──────────────────────────────────────────────────────────────

app.include_router(router_tabelas, prefix="/api")
app.include_router(router_dados, prefix="/api")
app.include_router(router_busca, prefix="/api")
app.include_router(router_exportar, prefix="/api")
app.include_router(router_dashboard, prefix="/api")
app.include_router(router_sql, prefix="/api")
app.include_router(router_stats, prefix="/api")
app.include_router(router_labels, prefix="/api")
app.include_router(router_dicionarios, prefix="/api")

# ── Arquivos estáticos (frontend) ─────────────────────────────────────────────

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def raiz() -> FileResponse:
        """Serve a interface web principal."""
        return FileResponse(str(_WEB_DIR / "index.html"))


# ── Inicialização do servidor (para execução direta) ────────────────────────

if __name__ == "__main__":
    import uvicorn
    
    cfg_servidor = CONFIG.get("servidor", {})
    host = cfg_servidor.get("host", "0.0.0.0")
    porta = cfg_servidor.get("porta", 8000)
    
    uvicorn.run(
        app,
        host=host,
        port=porta,
        log_level="info",
    )