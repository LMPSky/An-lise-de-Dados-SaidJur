"""Módulo de configuração: lê config.yaml e expõe as configurações da aplicação."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Caminho padrão do arquivo de configuração (raiz do projeto)
_RAIZ = Path(__file__).resolve().parent.parent
_CAMINHO_PADRAO = _RAIZ / "config.yaml"


def _carregar_yaml(caminho: Path) -> dict[str, Any]:
    """Lê e retorna o conteúdo de um arquivo YAML."""
    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _config_padrao() -> dict[str, Any]:
    """Retorna configuração padrão quando config.yaml não existe."""
    return {
        "servidor": {"host": "127.0.0.1", "porta": 8000},
        "banco": {
            "host": "127.0.0.1",
            "porta": 3306,
            "usuario": "root",
            "senha": "",
            "nome": "saidjur",
        },
        "busca": {"timeout_segundos": 10, "limite_padrao": 100},
    }


def carregar_config(caminho: Path | None = None) -> dict[str, Any]:
    """
    Carrega a configuração da aplicação.

    Lê o arquivo config.yaml (ou o caminho informado). Se não existir,
    usa valores padrão. Variáveis de ambiente sobrescrevem o arquivo:
    - DB_HOST, DB_PORTA, DB_USUARIO, DB_SENHA, DB_NOME
    - APP_HOST, APP_PORTA
    """
    if caminho is None:
        caminho = _CAMINHO_PADRAO

    if caminho.exists():
        dados = _carregar_yaml(caminho)
    else:
        dados = _config_padrao()

    # Garante estrutura mínima
    dados.setdefault("servidor", {})
    dados.setdefault("banco", {})
    dados.setdefault("busca", {})

    # Sobrescreve com variáveis de ambiente (útil em testes e containers)
    if os.getenv("DB_HOST"):
        dados["banco"]["host"] = os.environ["DB_HOST"]
    if os.getenv("DB_PORTA"):
        dados["banco"]["porta"] = int(os.environ["DB_PORTA"])
    if os.getenv("DB_USUARIO"):
        dados["banco"]["usuario"] = os.environ["DB_USUARIO"]
    if os.getenv("DB_SENHA") is not None:
        dados["banco"]["senha"] = os.environ["DB_SENHA"]
    if os.getenv("DB_NOME"):
        dados["banco"]["nome"] = os.environ["DB_NOME"]
    if os.getenv("APP_HOST"):
        dados["servidor"]["host"] = os.environ["APP_HOST"]
    if os.getenv("APP_PORTA"):
        dados["servidor"]["porta"] = int(os.environ["APP_PORTA"])

    return dados


# Configuração global (carregada uma vez na importação do módulo)
CONFIG: dict[str, Any] = carregar_config()
