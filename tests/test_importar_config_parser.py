"""Testes unitários para o parser Ler-Config do script de importação."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_IMPORTAR = REPO_ROOT / "scripts" / "importar.ps1"


def test_ler_config_trata_comentarios_e_senha_com_caracteres_especiais(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """# linha de comentário pura
banco:
  host: 127.0.0.1
  usuario: root # comentário inline
  senha: "Acd9854#@yui\\\"!$"
  senha_sem_aspas: senhaSegura123
  nome: saidjur
""",
        encoding="utf-8",
    )

    resultado = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(SCRIPT_IMPORTAR),
            "-SomenteLerConfig",
            "-ConfigPath",
            str(config_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    config = json.loads(resultado.stdout)
    banco = config["banco"]

    assert banco["senha"] == 'Acd9854#@yui"!$'
    assert banco["senha_sem_aspas"] == "senhaSegura123"
    assert banco["usuario"] == "root"
