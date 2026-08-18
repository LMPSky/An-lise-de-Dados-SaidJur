"""Testes direcionados da lógica de resumo em ``src/web/app.js``."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


APP_JS = Path(__file__).resolve().parents[1] / "src" / "web" / "app.js"


def _executar_js(snippet: str) -> object:
    """Executa um trecho pequeno de Node.js carregando ``app.js`` real."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js não disponível para validar a lógica do frontend.")

    script = f"""
const fs = require('fs');
const vm = require('vm');
global.localStorage = {{ getItem() {{ return null; }}, setItem() {{}} }};
global.window = {{ addEventListener() {{}}, requestAnimationFrame(cb) {{ cb(); }}, scrollY: 0 }};
global.document = {{ querySelector() {{ return null; }} }};
global.fetch = async () => ({{ ok: true, json: async () => ({{}}), text: async () => '' }});
vm.runInThisContext(fs.readFileSync({json.dumps(str(APP_JS))}, 'utf8'), {{ filename: {json.dumps(str(APP_JS))} }});
const instancia = app();
{snippet}
"""
    resultado = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(resultado.stdout)


def test_campos_card_resumido_usa_proximo_texto_quando_label_esta_vazio() -> None:
    """O card recolhido deve cair para outro texto quando o label principal vier nulo."""
    resultado = _executar_js(
        """
const resumo = instancia.camposCardResumido(
  { id: 10, summary: null, publication: 'Conteúdo alternativo', created_at: '2026-08-01' },
  [{ nome: 'id', chave: 'PRI' }, { nome: 'summary' }, { nome: 'publication' }, { nome: 'created_at' }]
);
console.log(JSON.stringify(resumo));
"""
    )

    assert resultado[0]["nome"] == "publication"
    assert resultado[0]["valor"] == "Conteúdo alternativo"


def test_campos_card_resumido_faz_fallback_para_registro_quando_nao_ha_texto() -> None:
    """Nenhum card deve ficar em branco mesmo sem colunas textuais úteis."""
    resultado = _executar_js(
        """
const resumo = instancia.camposCardResumido(
  { id: 30, left_id: 100, right_id: 200 },
  [{ nome: 'id', chave: 'PRI' }, { nome: 'left_id' }, { nome: 'right_id' }]
);
console.log(JSON.stringify(resumo));
"""
    )

    assert resultado == [{"nome": "id", "rotulo": "Registro", "valor": "#30"}]


def test_simplificar_resultados_busca_nunca_deixa_card_simples_vazio() -> None:
    """A busca simples deve produzir algum conteúdo visível mesmo sem resumo mapeado."""
    resultado = _executar_js(
        """
instancia.resultadosBusca = [
  {
    tabela: 'publicationxml_extra',
    coluna: 'summary',
    registros: [
      {
        id: 77,
        client_id: null,
        lawsuit_id: null,
        publication_date: null,
        status: null,
        summary: null,
        publication: null,
        content: null,
        texto: null,
        external_ref: 'Diário Oficial'
      }
    ]
  }
];
instancia.simplificarResultadosBusca();
console.log(JSON.stringify(instancia.resultadosBuscaSimplificados));
"""
    )

    assert "Publicações" in resultado
    assert resultado["Publicações"][0]
    assert any(str(valor).strip() for valor in resultado["Publicações"][0].values())
