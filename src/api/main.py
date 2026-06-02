"""Aplicação principal FastAPI: configura rotas, CORS, logging e arquivos estáticos."""

from __future__ import annotations

import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config import CONFIG
from src.db import criar_engine
from src.api.routes_tables import router as router_tabelas
from src.api.routes_data import router as router_dados
from src.api.routes_search import router as router_busca
from src.api.routes_export import router as router_exportar

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
    cfg = CONFIG["servidor"]
    logger.info(
        "Servidor iniciado em http://%s:%s — banco: %s",
        cfg.get("host", "127.0.0.1"),
        cfg.get("porta", 8000),
        CONFIG["banco"].get("nome", "saidjur"),
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
# Por padrão, permite apenas localhost. Para liberar na rede, configure
# origins_extras em config.yaml ou altere allow_origins abaixo.

_origens_permitidas = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_permitidas,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Middleware de autenticação (desabilitado — preparado para uso futuro) ────
# Para habilitar autenticação básica no futuro, descomente e implemente:
#
# from fastapi import Request, HTTPException
# from fastapi.responses import Response
# import secrets
#
# @app.middleware("http")
# async def autenticar(request: Request, call_next):
#     # Implemente sua lógica de autenticação aqui
#     # Exemplo: Basic Auth, JWT, API Key etc.
#     response = await call_next(request)
#     return response

# ── Injeção do engine nas rotas ───────────────────────────────────────────────

app.state.engine = engine

# ── Rotas da API ──────────────────────────────────────────────────────────────

app.include_router(router_tabelas, prefix="/api")
app.include_router(router_dados, prefix="/api")
app.include_router(router_busca, prefix="/api")
app.include_router(router_exportar, prefix="/api")

# ── Arquivos estáticos (frontend) ─────────────────────────────────────────────

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def raiz() -> FileResponse:
        """Serve a interface web principal."""
        return FileResponse(str(_WEB_DIR / "index.html"))

