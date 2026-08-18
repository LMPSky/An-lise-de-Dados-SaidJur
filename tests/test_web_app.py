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
instancia.termoBuscaAtiva = 'Sila do Brasil';
instancia.resultadosBusca = [
  {
    tabela: 'publicationxml_extra',
    coluna: 'search_term',
    colunas: [
      { nome: 'id', chave: 'PRI' },
      { nome: 'search_term' },
      { nome: 'external_ref' }
    ],
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
        search_term: 'Sila do Brasil',
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
    assert resultado["Publicações"][0]["resumo"]
    assert "Diário Oficial" in resultado["Publicações"][0]["resumo"].values()
    assert resultado["Publicações"][0]["correspondencia"]["valor"] == "Sila do Brasil"


def test_campos_card_busca_global_ignora_search_term_como_resumo_principal() -> None:
    """Busca global não deve promover o termo correspondido como resumo principal do card."""
    resultado = _executar_js(
        """
instancia.termoBuscaAtiva = 'Sila do Brasil';
const resumo = instancia.camposCardBuscaGlobalResumido(
  {
    tabela: 'publicationxml_extra',
    coluna: 'search_term',
    colunas: [
      { nome: 'id', chave: 'PRI' },
      { nome: 'search_term' },
      { nome: 'content' },
      { nome: 'publication_date' }
    ]
  },
  {
    id: 91,
    search_term: 'Sila do Brasil',
    content: 'Publicação com dados reais do processo',
    publication_date: '2026-08-01'
  }
);
console.log(JSON.stringify(resumo));
"""
    )

    assert resultado[0]["nome"] == "content"
    assert resultado[0]["valor"] == "Publicação com dados reais do processo"


def test_campos_card_busca_global_nao_descarta_coluna_term_legitima() -> None:
    """Colunas chamadas ``term`` só devem ser ignoradas quando coincidirem com o termo buscado."""
    resultado = _executar_js(
        """
instancia.termoBuscaAtiva = 'Sila do Brasil';
const resumo = instancia.camposCardBuscaGlobalResumido(
  {
    tabela: 'publicationxml_extra',
    coluna: 'content',
    colunas: [
      { nome: 'id', chave: 'PRI' },
      { nome: 'term' },
      { nome: 'publication_date' }
    ]
  },
  {
    id: 12,
    term: 'Prazo recursal',
    publication_date: '2026-08-01',
    content: 'Sila do Brasil'
  }
);
console.log(JSON.stringify(resumo));
"""
    )

    assert resultado[0]["nome"] == "term"
    assert resultado[0]["valor"] == "Prazo recursal"


def test_index_html_da_busca_global_tem_botao_explicito_de_expansao() -> None:
    """A UI da busca global deve renderizar um botão textual de expansão dos cards."""
    html = (Path(__file__).resolve().parents[1] / "src" / "web" / "index.html").read_text(encoding="utf-8")

    assert "Expandir detalhes" in html
    assert "chaveCardBuscaSimples" in html
