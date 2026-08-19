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


# ── Testes de regressão — hearingcontrol (PR #39 / correcoes) ──────────────────

def test_hearingcontrol_processo_usa_numero_cnj_antes_de_lawsuit_id() -> None:
    """Resumo de audiência deve exibir o CNJ (numero/lawsuitnumber) e não o lawsuit_id cru."""
    resultado = _executar_js(
        """
instancia.resultadosBusca = [
  {
    tabela: 'hearingcontrol',
    coluna: 'hearingtype_id',
    colunas: [
      { nome: 'id', chave: 'PRI' },
      { nome: 'lawsuit_id' },
      { nome: 'numero' },
      { nome: 'hearing_date' }
    ],
    registros: [
      {
        id: 1,
        lawsuit_id: 2332,
        numero: '0010441-54.2017.5.03.0028',
        hearing_date: '0000-00-00',
        updated_at: '2019-09-09 13:04:57'
      }
    ]
  }
];
instancia.simplificarResultadosBusca();
console.log(JSON.stringify(instancia.resultadosBuscaSimplificados));
"""
    )

    audiencias = resultado.get("Audiências", [])
    assert len(audiencias) == 1
    resumo = audiencias[0]["resumo"]
    assert resumo.get("Processo") == "0010441-54.2017.5.03.0028", (
        "O campo Processo deve ser o CNJ, não o lawsuit_id cru"
    )


def test_hearingcontrol_data_pula_valor_sentinela_zerado() -> None:
    """Resumo de audiência deve pular '0000-00-00' e usar o próximo campo de data disponível."""
    resultado = _executar_js(
        """
instancia.resultadosBusca = [
  {
    tabela: 'hearingcontrol',
    coluna: 'hearingtype_id',
    colunas: [
      { nome: 'id', chave: 'PRI' },
      { nome: 'hearing_date' },
      { nome: 'updated_at' }
    ],
    registros: [
      {
        id: 1,
        lawsuit_id: 2332,
        numero: '0010441-54.2017.5.03.0028',
        hearing_date: '0000-00-00',
        updated_at: '2019-09-09 13:04:57'
      }
    ]
  }
];
instancia.simplificarResultadosBusca();
console.log(JSON.stringify(instancia.resultadosBuscaSimplificados));
"""
    )

    audiencias = resultado.get("Audiências", [])
    assert len(audiencias) == 1
    resumo = audiencias[0]["resumo"]
    assert resumo.get("Data") != "0000-00-00", (
        "O resumo não deve mostrar a data sentinela '0000-00-00'"
    )
    assert resumo.get("Data") == "2019-09-09 13:04:57", (
        "O resumo deve usar updated_at como fallback quando hearing_date é sentinela zerado"
    )


def test_hearingcontrol_data_zero_hora_pula_sentinela() -> None:
    """Sentinela '0000-00-00 00:00:00' também deve ser ignorado em primeiraLinha."""
    resultado = _executar_js(
        """
instancia.resultadosBusca = [
  {
    tabela: 'hearingcontrol',
    coluna: 'hearingtype_id',
    colunas: [{ nome: 'id', chave: 'PRI' }, { nome: 'hearing_date' }, { nome: 'updated_at' }],
    registros: [
      {
        id: 2,
        lawsuit_id: 100,
        numero: '9999999-00.2020.8.00.0000',
        hearing_date: '0000-00-00 00:00:00',
        updated_at: '2022-03-15 08:30:00'
      }
    ]
  }
];
instancia.simplificarResultadosBusca();
console.log(JSON.stringify(instancia.resultadosBuscaSimplificados));
"""
    )

    audiencias = resultado.get("Audiências", [])
    assert audiencias[0]["resumo"].get("Data") == "2022-03-15 08:30:00"


def test_traduzir_valor_usa_colunas_booleanas_para_sim_nao() -> None:
    """traduzirValor deve retornar 'Sim'/'Não' para colunas confirmadas como booleanas."""
    resultado = _executar_js(
        """
instancia.mostrarLabels = true;
instancia.colunasBooleanas = new Set(['hearingcontrol.dispensed', 'hearingcontrol.canceled']);
const sim = instancia.traduzirValor('hearingcontrol', 'dispensed', 1);
const nao = instancia.traduzirValor('hearingcontrol', 'canceled', 0);
const nao_str = instancia.traduzirValor('hearingcontrol', 'dispensed', '0');
console.log(JSON.stringify({ sim, nao, nao_str }));
"""
    )

    assert resultado["sim"] == "Sim"
    assert resultado["nao"] == "Não"
    assert resultado["nao_str"] == "Não"


def test_traduzir_valor_colunas_nao_booleanas_nao_afetadas() -> None:
    """Colunas não listadas em colunasBooleanas não devem ser tratadas como booleanas."""
    resultado = _executar_js(
        """
instancia.mostrarLabels = true;
instancia.dicionarios = { hearingcontrol: { hearingstatus: { '0': 'Pendente', '1': 'Realizado' } } };
instancia.colunasBooleanas = new Set(['hearingcontrol.dispensed']);
const status = instancia.traduzirValor('hearingcontrol', 'hearingstatus', '1');
console.log(JSON.stringify(status));
"""
    )

    assert resultado == "Realizado"
