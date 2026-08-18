/**
 * Lógica principal do Visualizador de Dados SaidJur
 * Usa Alpine.js para reatividade sem build step.
 * 
 * ✅ COM TRADUÇÕES DE COLUNAS (carregadas do backend via /api/traducoes/colunas)
 * ✅ COM SCROLL/PAGINAÇÃO FIXOS NO TOPO
 * ✅ COM EXPORTAÇÃO DE RESULTADOS DE BUSCA
 * ✅ COM FORMATAÇÃO MELHORADA
 */

// ──────────────────────────────────────────────────────────────────────────
// TRADUÇÃO DE NOMES DE COLUNAS
// As traduções são carregadas do endpoint GET /api/traducoes/colunas durante
// a inicialização do app. Este módulo NÃO mantém uma cópia local do dicionário
// — a fonte canônica é src/traducoes_colunas.py no backend.
// ──────────────────────────────────────────────────────────────────────────

let _traducoesColunas = {};

const SUBSTANTIVOS_MASCULINOS_EM_A = new Set([
  'mapa',
  'prazo',
  'problema',
  'programa',
  'sistema',
  'tema',
]);

const CANDIDATAS_LABEL_RESUMO = [
  'name', 'nome', 'descricao', 'description', 'title',
  'titulo', 'label', 'display_name', 'displayname',
  'razao_social', 'fantasia', 'numero', 'number',
  'lawsuitnumber', 'summary', 'publication', 'content',
  'texto', 'search_term', 'term', 'termo',
];

const REGEX_COLUNA_TECNICA_RESUMO = /(^id$|_id$|^fk_|^id_|created_at$|updated_at$|deleted_at$|inserted_at$|created_by$|updated_by$|userid$|user_id$|log_|config|setting|token|hash|password|checksum|uuid|guid|version|sort_order$|ordem$)/i;

function normalizarPalavra(texto) {
  return texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function artigoParaId(traducaoBase) {
  const primeiraPalavra = traducaoBase.split(' ')[0];
  const palavraNormalizada = normalizarPalavra(primeiraPalavra);

  if (
    palavraNormalizada.endsWith('agem') ||
    palavraNormalizada.endsWith('cao') ||
    palavraNormalizada.endsWith('dade') ||
    palavraNormalizada.endsWith('gem') ||
    palavraNormalizada.endsWith('ice') ||
    palavraNormalizada.endsWith('sao')
  ) {
    return 'da';
  }

  if (
    palavraNormalizada.endsWith('a') &&
    !SUBSTANTIVOS_MASCULINOS_EM_A.has(palavraNormalizada)
  ) {
    return 'da';
  }

  return 'do';
}

function traduzirColunaRelacional(nomeColuna) {
  if (!nomeColuna.endsWith('_id')) {
    return null;
  }

  const entidade = nomeColuna.slice(0, -3);
  const traducaoEntidade = _traducoesColunas[entidade];
  if (!traducaoEntidade) {
    return null;
  }

  return `ID ${artigoParaId(traducaoEntidade)} ${traducaoEntidade}`;
}

/**
 * Traduz nome da coluna para português
 */
function traduzirNomeColuna(nomeColuna) {
  if (!nomeColuna) return nomeColuna;
  const nomeNormalizado = nomeColuna.toLowerCase();
  
  // Tradução direta
  if (_traducoesColunas[nomeNormalizado]) {
    return _traducoesColunas[nomeNormalizado];
  }

  const traducaoRelacional = traduzirColunaRelacional(nomeNormalizado);
  if (traducaoRelacional) {
    return traducaoRelacional;
  }
  
  // Tentar traduzir partes (para nomes compostos)
  const partes = nomeNormalizado.split('_');
  const partesTraduzidas = [];
  
  for (const parte of partes) {
    if (_traducoesColunas[parte]) {
      partesTraduzidas.push(_traducoesColunas[parte]);
    } else if (parte === 'id') {
      partesTraduzidas.push('ID');
    } else {
      partesTraduzidas.push(parte.charAt(0).toUpperCase() + parte.slice(1).toLowerCase());
    }
  }
  
  return partesTraduzidas.join(' ');
}

/**
 * Formata nome removendo underscores e capitalizando
 */
function formatarNome(nome) {
  return nome
    .replace(/_/g, ' ')
    .split(' ')
    .map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
    .join(' ');
}

// ──────────────────────────────────────────────────────────────────────────
// APP PRINCIPAL
// ──────────────────────────────────────────────────────────────────────────

function app() {
  return {
    // ── Estado global ─────────────────────────────────────────────
    nomeBanco: '',
    mensagemErro: null,
    abaAtiva: 'dados', // dados | sql

    // ── Tabelas (sidebar) ─────────────────────────────────────────
    tabelas: [],
    carregandoTabelas: true,
    filtroTabela: '',
    tabelaSelecionada: null,
    favoritos: [],
    recentes: [],

    // ── Dashboard ──────────────────────────────────────────────────
    dashboard: null,
    carregandoDashboard: false,

    // ── Dados da tabela ───────────────────────────────────────────
    colunas: [],
    colunasOriginais: [], // ✅ NOVO: guardar nomes originais
    linhas: [],
    totalRegistros: 0,
    pagina: 1,
    porPagina: 50,
    ordenarColuna: null,
    direcaoOrdem: 'asc',
    carregandoDados: false,
    filtrosAtivos: {},
    filtroAberto: null,
    filtroTemp: { op: 'contem', valor: '' },
    fksPorTabela: {},
    fksMapAtual: {},
    fksInferidas: {},

    // ── Labels ───────────────────────────────────────────────────
    labels: {},
    dicionarios: {},
    mostrarLabels: true,
    modoAvancado: false,
    mostrarNomesTecnicos: false,

    // ── Modo de visualização: 'cards' | 'tabela' ─────────────────
    // Persiste em localStorage; padrão = 'cards'
    modoVisualizacao: 'cards',

    // ── Cards expansíveis: conjunto de índices expandidos ────────
    cardsExpandidos: new Set(),

    // ── Colunas visíveis ─────────────────────────────────────────
    colunasVisiveis: {},
    popoverColunasAberto: false,

    // ── Estatísticas de coluna ───────────────────────────────────
    statsAbertoColuna: null,
    statsColuna: null,
    carregandoStats: false,

    // ── Busca global ──────────────────────────────────────────────
    termoBusca: '',
    termoBuscaAtiva: '',
    resultadosBusca: [],
    resultadosBuscaSimplificados: {},
    buscandoGlobal: false,
    mostrarBusca: false,
    buscaCancelada: false,
    buscaProgresso: { processadas: 0, total: 0, encontrados: 0 },
    buscaController: null,
    exportandoBusca: false,

    // ── Modal de detalhe ─────────────────────────────────────────
    detalheAberto: false,
    detalheTabela: null,
    detalheRegistro: null,
    detalheLinhasContexto: [],
    detalheIndiceContexto: -1,
    detalheColunas: [],

    // ── Console SQL ──────────────────────────────────────────────
    sqlQuery: 'SELECT * FROM clientes LIMIT 50',
    sqlCarregando: false,
    sqlResultado: null,
    sqlHistorico: [],
    sqlPagina: 1,
    sqlPorPagina: 50,
    sqlTabelaContexto: null,

    // ── Getters computados ────────────────────────────────────────

    get tabelasFiltradas() {
      const termo = this.filtroTabela.toLowerCase();
      if (!termo) return this.tabelas;
      return this.tabelas.filter(t => t.nome.toLowerCase().includes(termo));
    },

    get totalPaginas() {
      if (!this.porPagina) return 1;
      return Math.max(1, Math.ceil(this.totalRegistros / this.porPagina));
    },

    get colunasExibidas() {
      return this.colunas.filter(c => this.colunasVisiveis[c.nome] !== false);
    },

    get tabelasFavoritas() {
      const favoritas = new Set(this.favoritos);
      return this.tabelas.filter(t => favoritas.has(t.nome));
    },

    get tabelasRecentes() {
      const mapa = new Map(this.tabelas.map(t => [t.nome, t]));
      return this.recentes.map(nome => mapa.get(nome)).filter(Boolean);
    },

    get detalheCampos() {
      if (!this.detalheRegistro) return [];
      const ordem = this.detalheColunas.length > 0 ? this.detalheColunas.map(c => c.nome) : Object.keys(this.detalheRegistro);
      return ordem
        .filter(nome => Object.prototype.hasOwnProperty.call(this.detalheRegistro, nome))
        .map(nome => ({ nome, valor: this.detalheRegistro[nome] }));
    },

    get sqlLinhasPaginadas() {
      const linhas = this.sqlResultado?.linhas || [];
      const ini = (this.sqlPagina - 1) * this.sqlPorPagina;
      return linhas.slice(ini, ini + this.sqlPorPagina);
    },

    get sqlTotalPaginas() {
      const total = this.sqlResultado?.linhas?.length || 0;
      return Math.max(1, Math.ceil(total / this.sqlPorPagina));
    },

    // ──────────────────────────────────────────────────────────────
    // ✅ NOVAS FUNÇÕES DE TRADUÇÃO
    // ──────────────────────────────────────────────────────────────

    /**
     * Traduz nome de coluna original para português
     */
    traduzirColuna(nomeOriginal) {
      return traduzirNomeColuna(nomeOriginal);
    },

    exibirNomeTabela(nomeTabela) {
      if (!nomeTabela) return '';
      return this.modoAvancado ? nomeTabela : formatarNome(nomeTabela);
    },

    exibirNomeCampo(nomeCampo) {
      if (!nomeCampo) return '';
      if (this.modoAvancado) return nomeCampo;
      const traduzido = this.traduzirColuna(nomeCampo);
      if (this.mostrarNomesTecnicos && traduzido !== nomeCampo) {
        return `${traduzido} (${nomeCampo})`;
      }
      return traduzido;
    },

    exibirCabecalhoColuna(col) {
      if (this.modoAvancado) return col.nome;
      const traduzido = col.nomeTraduzido || col.nome;
      if (this.mostrarNomesTecnicos && traduzido !== col.nome) {
        return `${traduzido} (${col.nome})`;
      }
      return traduzido;
    },

    camposRegistroSimples(registro, ordem = null) {
      if (!registro) return [];
      const campos = (ordem || Object.keys(registro))
        .filter(nome => Object.prototype.hasOwnProperty.call(registro, nome))
        .map(nome => ({ nome, valor: registro[nome] }))
        .filter(campo => this.valorTemConteudo(campo.valor));

      if (campos.length > 0) return campos;

      return (ordem || Object.keys(registro))
        .filter(nome => Object.prototype.hasOwnProperty.call(registro, nome))
        .slice(0, 1)
        .map(nome => ({ nome, valor: registro[nome] }));
    },

    simplificarResultadosBusca() {
      const grupos = {
        'Processos': [],
        'Publicações': [],
        'Audiências': [],
        'Pedidos e Andamentos': [],
      };

      const primeiraLinha = (registro, chaves) => {
        for (const chave of chaves) {
          const valor = registro?.[chave];
          if (valor !== null && valor !== undefined && String(valor).trim() !== '') return valor;
        }
        return null;
      };

      for (const grupo of this.resultadosBusca) {
        for (const registro of grupo.registros || []) {
          let nomeGrupo = null;
          let item = null;

          if (grupo.tabela === 'lawsuits') {
            nomeGrupo = 'Processos';
            item = {
              'Cliente': primeiraLinha(registro, ['client_id', 'client_name', 'cliente']),
              'Processo': primeiraLinha(registro, ['numero', 'lawsuitnumber', 'cnj', 'number']),
              'Parte': primeiraLinha(registro, ['person_id', 'person_name', 'parte']),
              'Situação': primeiraLinha(registro, ['status', 'situation', 'phase']),
              'Valor': primeiraLinha(registro, ['amount', 'value', 'valor_causa', 'instance01_amount']),
            };
          } else if (['publicationxml', 'publicationxml_extra'].includes(grupo.tabela)) {
            nomeGrupo = 'Publicações';
            item = {
              'Cliente': primeiraLinha(registro, ['client_id', 'client_name', 'cliente']),
              'Processo': primeiraLinha(registro, ['lawsuit_id', 'numero', 'lawsuitnumber', 'processo']),
              'Data': primeiraLinha(registro, ['publication_date', 'date', 'created_at']),
              'Situação': primeiraLinha(registro, ['status', 'pub_classification', 'classification']),
              'Resumo': primeiraLinha(registro, ['summary', 'publication', 'content', 'texto']),
            };
          } else if (grupo.tabela === 'hearingcontrol') {
            nomeGrupo = 'Audiências';
            item = {
              'Cliente': primeiraLinha(registro, ['client_id', 'client_name', 'cliente']),
              'Processo': primeiraLinha(registro, ['lawsuit_id', 'numero', 'lawsuitnumber']),
              'Data': primeiraLinha(registro, ['hearing_date', 'date', 'scheduled_at']),
              'Tipo de Audiência': primeiraLinha(registro, ['hearing_type_id', 'type', 'hearing_type']),
              'Situação': primeiraLinha(registro, ['status', 'situation']),
            };
          } else if (grupo.tabela === 'pedidos2lawsuit') {
            nomeGrupo = 'Pedidos e Andamentos';
            item = {
              'Cliente': primeiraLinha(registro, ['client_id', 'client_name', 'cliente']),
              'Processo': primeiraLinha(registro, ['lawsuit_id', 'numero', 'lawsuitnumber']),
              'Pedido': primeiraLinha(registro, ['claim_text', 'request_text', 'pedido', 'description']),
              'Andamento': primeiraLinha(registro, ['progress_text', 'status', 'instance02', 'instance01']),
              'Valor': primeiraLinha(registro, ['instance01_amount', 'amount', 'value']),
            };
          }

          if (nomeGrupo && item) {
            const colunas = this.colunasBuscaGrupo(grupo, registro);
            grupos[nomeGrupo].push({
              tabela: grupo.tabela,
              colunaCorrespondencia: grupo.coluna,
              registro,
              colunas,
              resumo: this.garantirResumoSimplesVisivel(item, registro, {
                grupoBusca: grupo,
                colunas,
              }),
              correspondencia: this.contextoCorrespondenciaBusca(grupo, registro),
            });
          }
        }
      }

      this.resultadosBuscaSimplificados = Object.fromEntries(
        Object.entries(grupos).filter(([, itens]) => itens.length > 0)
      );
    },

    /**
     * Obtém nome traduzido de uma coluna pelo índice
     */
    obterNomeColunaTraduzido(indice) {
      if (!this.colunasOriginais || !this.colunasOriginais[indice]) return '?';
      return this.traduzirColuna(this.colunasOriginais[indice].nome);
    },

    valorTemConteudo(valor) {
      return valor !== null && valor !== undefined && String(valor).trim() !== '';
    },

    ehColunaTecnicaResumo(nomeColuna) {
      return REGEX_COLUNA_TECNICA_RESUMO.test(nomeColuna || '');
    },

    ordemColunasResumo(colunas, registro) {
      const nomes = (colunas || Object.keys(registro || {}))
        .map(col => col?.nome || col)
        .filter(Boolean);
      return nomes.filter(nome => Object.prototype.hasOwnProperty.call(registro || {}, nome));
    },

    colunaLabelResumo(registro, colunas) {
      const nomesDisponiveis = new Set(this.ordemColunasResumo(colunas, registro).map(nome => nome.toLowerCase()));
      for (const candidata of CANDIDATAS_LABEL_RESUMO) {
        if (!nomesDisponiveis.has(candidata)) continue;
        const nomeReal = this.ordemColunasResumo(colunas, registro).find(nome => nome.toLowerCase() === candidata);
        if (nomeReal && this.valorTemConteudo(registro?.[nomeReal])) return nomeReal;
      }
      return null;
    },

    colunaIdFallbackResumo(registro, colunas) {
      for (const col of colunas || []) {
        if (col?.chave === 'PRI' && this.valorTemConteudo(registro?.[col.nome])) {
          return col.nome;
        }
      }

      for (const nome of ['id', 'codigo', 'code']) {
        if (this.valorTemConteudo(registro?.[nome])) return nome;
      }

      return this.ordemColunasResumo(colunas, registro).find(
        nome => nome.toLowerCase().endsWith('id') && this.valorTemConteudo(registro?.[nome])
      ) || null;
    },

    colunasBuscaGrupo(grupo, registro = null) {
      if (grupo?.colunas?.length) return grupo.colunas;

      const nomes = Object.keys(registro || grupo?.registros?.[0] || {});
      return nomes.map(nome => ({ nome }));
    },

    colunaEhCorrespondenciaBusca(nomeColuna, valor, termoBusca = null) {
      const nomeNormalizado = String(nomeColuna || '').trim().toLowerCase();
      if (!termoBusca || !this.valorTemConteudo(valor)) return false;
      const valorNormalizado = String(valor).trim().toLowerCase();
      return valorNormalizado === String(termoBusca).trim().toLowerCase()
        && /^(search_?term|termo|term)$/.test(nomeNormalizado);
    },

    camposResumoBuscaGlobal(grupo, registro, limite = 3) {
      const colunas = this.colunasBuscaGrupo(grupo, registro);
      const ignorarColunas = new Set();
      if (grupo?.coluna) ignorarColunas.add(grupo.coluna);

      for (const coluna of colunas) {
        if (this.colunaEhCorrespondenciaBusca(coluna?.nome, registro?.[coluna?.nome], this.termoBuscaAtiva)) {
          ignorarColunas.add(coluna.nome);
        }
      }

      const semCorrespondencia = this.camposResumoGenerico(registro, colunas, limite, {
        ignorarColunas,
        permitirFallback: false,
      });
      if (semCorrespondencia.length > 0) return semCorrespondencia;

      return this.camposResumoGenerico(registro, colunas, limite);
    },

    chaveCardBuscaSimples(assunto, indiceItem, item) {
      return `busca_simples_${assunto}_${item?.tabela || 'tabela'}_${item?.colunaCorrespondencia || 'coluna'}_${indiceItem}`;
    },

    chaveCardBuscaAvancada(grupo, indice) {
      return `busca_avancada_${grupo?.tabela || 'tabela'}_${grupo?.coluna || 'coluna'}_${indice}`;
    },

    contextoCorrespondenciaBusca(grupo, registro) {
      if (!grupo?.coluna || !this.valorTemConteudo(registro?.[grupo.coluna])) return null;
      return {
        nome: grupo.coluna,
        rotulo: 'Correspondência',
        valor: registro[grupo.coluna],
      };
    },

    camposResumoGenerico(registro, colunas, limite = 3, opcoes = {}) {
      if (!registro) return [];

      const ignorarColunas = new Set(
        [...(opcoes?.ignorarColunas || [])]
          .filter(Boolean)
          .map(nome => String(nome).toLowerCase())
      );
      const permitirFallback = opcoes?.permitirFallback !== false;
      const ordem = this.ordemColunasResumo(colunas, registro);
      const campos = [];
      const usados = new Set();
      const nomeLabel = this.colunaLabelResumo(registro, colunas);

      if (nomeLabel && !ignorarColunas.has(String(nomeLabel).toLowerCase())) {
        campos.push({ nome: nomeLabel, valor: registro[nomeLabel] });
        usados.add(nomeLabel);
      }

      for (const nome of ordem) {
        if (campos.length >= limite) break;
        if (ignorarColunas.has(String(nome).toLowerCase())) continue;
        if (usados.has(nome) || !this.valorTemConteudo(registro[nome])) continue;
        if (typeof registro[nome] !== 'string') continue;
        campos.push({ nome, valor: registro[nome] });
        usados.add(nome);
      }

      for (const nome of ordem) {
        if (campos.length >= limite) break;
        if (ignorarColunas.has(String(nome).toLowerCase())) continue;
        if (usados.has(nome) || !this.valorTemConteudo(registro[nome])) continue;
        if (this.ehColunaTecnicaResumo(nome)) continue;
        campos.push({ nome, valor: registro[nome] });
        usados.add(nome);
      }

      if (campos.length > 0) return campos;
      if (!permitirFallback) return [];

      const nomeId = this.colunaIdFallbackResumo(registro, colunas);
      if (nomeId) {
        return [{ nome: nomeId, rotulo: 'Registro', valor: `#${String(registro[nomeId]).trim()}` }];
      }

      return [{ nome: 'registro', rotulo: 'Registro', valor: 'Sem identificação visível' }];
    },

    garantirResumoSimplesVisivel(item, registro, opcoes = {}) {
      const preenchidos = Object.fromEntries(
        Object.entries(item || {}).filter(([, valor]) => this.valorTemConteudo(valor))
      );
      if (Object.keys(preenchidos).length > 0) return preenchidos;

      const fallback = {};
      const grupoBusca = opcoes?.grupoBusca || null;
      const colunas = opcoes?.colunas || this.ordemColunasResumo(null, registro);
      const camposFallback = grupoBusca
        ? this.camposResumoBuscaGlobal(grupoBusca, registro, 3)
        : this.camposResumoGenerico(registro, colunas, 3);
      for (const campo of camposFallback) {
        fallback[campo.rotulo || this.exibirNomeCampo(campo.nome)] = campo.valor;
      }
      return fallback;
    },

    /**
     * Converte array de colunas com tradução
     */
    traduzirListaColunas(colunas) {
      return colunas.map(col => ({
        ...col,
        nomeTraduzido: this.traduzirColuna(col.nome || col),
      }));
    },

    // ── Inicialização ─────────────────────────────────────────────

    async iniciar() {
      this.carregarPreferenciasLocal();
      this.sqlHistorico = this.lerJsonLocal('saidjur_sql_historico', []);
      
      // ✅ Fixar paginação no topo durante scroll
      this.configurarScrollFixo();
      
      await Promise.all([this.carregarTraducoes(), this.carregarTabelas(), this.carregarDashboard(), this.carregarDicionarios()]);
      window.addEventListener('keydown', (event) => this.atalhosTeclado(event));
    },

    /**
     * ✅ NOVO: Configura scroll fixo para paginação
     */
    configurarScrollFixo() {
      // Usar requestAnimationFrame para melhor performance
      let ticking = false;
      
      window.addEventListener('scroll', () => {
        if (!ticking) {
          window.requestAnimationFrame(() => {
            const paginacao = document.querySelector('.bg-white.border-t.px-4.py-2.flex.flex-wrap');
            if (paginacao) {
              if (window.scrollY > 100) {
                paginacao.style.position = 'fixed';
                paginacao.style.bottom = '0';
                paginacao.style.left = '0';
                paginacao.style.right = '0';
                paginacao.style.zIndex = '50';
                paginacao.style.width = '100%';
              } else {
                paginacao.style.position = 'relative';
              }
            }
            ticking = false;
          });
          ticking = true;
        }
      });
    },

    // ── Persistência local ───────────────────────────────────────

    lerJsonLocal(chave, padrao) {
      try {
        const raw = localStorage.getItem(chave);
        return raw ? JSON.parse(raw) : padrao;
      } catch {
        return padrao;
      }
    },

    salvarJsonLocal(chave, valor) {
      localStorage.setItem(chave, JSON.stringify(valor));
    },

    carregarPreferenciasLocal() {
      this.favoritos = this.lerJsonLocal('saidjur_favoritos', []);
      this.recentes = this.lerJsonLocal('saidjur_recentes', []);
      this.mostrarLabels = this.lerJsonLocal('saidjur_mostrar_labels', true);
      // Modo Avançado sempre começa desligado a cada carregamento da página.
      // Decisão de design: não persiste entre sessões — só dura enquanto a
      // aba estiver aberta. Isso garante comportamento consistente após
      // reinicialização do servidor. Veja README.md para detalhes.
      this.modoAvancado = false;
      this.mostrarNomesTecnicos = this.lerJsonLocal('saidjur_mostrar_nomes_tecnicos', false);
      this.modoVisualizacao = this.lerJsonLocal('saidjur_modo_visualizacao', 'cards');
    },

    alternarNomesTecnicos() {
      this.mostrarNomesTecnicos = !this.mostrarNomesTecnicos;
      this.salvarJsonLocal('saidjur_mostrar_nomes_tecnicos', this.mostrarNomesTecnicos);
    },

    alternarModoAvancado() {
      this.modoAvancado = !this.modoAvancado;
      // Modo Avançado não é persistido — dura apenas enquanto a aba está aberta.

      if (!this.modoAvancado) {
        if (this.abaAtiva === 'sql') this.abaAtiva = 'dados';
        this.popoverColunasAberto = false;
        this.filtroAberto = null;
        this.statsAbertoColuna = null;
        this.statsColuna = null;
      }
    },

    alternarModoVisualizacao() {
      this.modoVisualizacao = this.modoVisualizacao === 'cards' ? 'tabela' : 'cards';
      this.salvarJsonLocal('saidjur_modo_visualizacao', this.modoVisualizacao);
      this.cardsExpandidos = new Set();
    },

    alternarCardExpandido(indice) {
      const novo = new Set(this.cardsExpandidos);
      if (novo.has(indice)) {
        novo.delete(indice);
      } else {
        novo.add(indice);
      }
      this.cardsExpandidos = novo;
    },

    cardEstaExpandido(indice) {
      return this.cardsExpandidos.has(indice);
    },

    camposCardResumido(linha, colunas) {
      // Retorna até 3 campos visíveis com fallback em cascata.
      return this.camposResumoGenerico(linha, colunas, 3);
    },

    camposCardBuscaGlobalResumido(grupo, linha) {
      return this.camposResumoBuscaGlobal(grupo, linha, 3);
    },

    camposCardExpandido(linha, colunas) {
      // Retorna todos os campos não-nulos para o card expandido.
      // Colunas com todos os valores nulos/vazios são ocultadas automaticamente
      // — mesma lógica de camposRegistroSimples, aplicada no escopo dos dados
      // atualmente carregados (página atual).
      const tudo = (colunas || []).map(c => c.nome || c);
      const campos = tudo
        .filter(n => Object.prototype.hasOwnProperty.call(linha, n))
        .map(nome => ({ nome, valor: linha[nome] }))
        .filter(campo => this.valorTemConteudo(campo.valor));

      if (campos.length > 0) return campos;

      return this.camposResumoGenerico(linha, colunas, 1);
    },

    camposCardBuscaGlobalExpandido(grupo, linha) {
      return this.camposCardExpandido(linha, this.colunasBuscaGrupo(grupo, linha));
    },

    salvarFavoritos() {
      this.salvarJsonLocal('saidjur_favoritos', this.favoritos);
    },

    salvarRecentes() {
      this.salvarJsonLocal('saidjur_recentes', this.recentes.slice(0, 5));
    },

    chaveColunasTabela(nomeTabela) {
      return `saidjur_colunas_visiveis_${nomeTabela}`;
    },

    // ── Tabelas ───────────────────────────────────────────────────

    async carregarTabelas() {
      this.carregandoTabelas = true;
      try {
        const res = await fetch('/api/tabelas');
        if (!res.ok) throw new Error(await res.text());
        this.tabelas = await res.json();
        if (this.tabelas.length > 0) this.nomeBanco = 'SaidJur';
      } catch (e) {
        this.exibirErro('Não foi possível carregar a lista de tabelas.');
        this.tabelas = [];
      } finally {
        this.carregandoTabelas = false;
      }
    },

    async carregarDashboard() {
      this.carregandoDashboard = true;
      try {
        const res = await fetch('/api/dashboard');
        if (!res.ok) throw new Error(await res.text());
        this.dashboard = await res.json();
      } catch {
        this.dashboard = null;
      } finally {
        this.carregandoDashboard = false;
      }
    },

    async carregarDicionarios() {
      try {
        const res = await fetch('/api/dicionarios');
        if (!res.ok) throw new Error(await res.text());
        this.dicionarios = await res.json();
      } catch {
        this.dicionarios = {};
      }
    },

    async carregarTraducoes() {
      try {
        const res = await fetch('/api/traducoes/colunas');
        if (!res.ok) throw new Error(await res.text());
        const dados = await res.json();
        // Atualiza o dicionário global usado por traduzirNomeColuna()
        Object.assign(_traducoesColunas, dados);
      } catch {
        // Falha silenciosa: colunas serão exibidas com capitalização automática
      }
    },

    alternarFavorito(nomeTabela) {
      if (this.favoritos.includes(nomeTabela)) {
        this.favoritos = this.favoritos.filter(n => n !== nomeTabela);
      } else {
        this.favoritos = [nomeTabela, ...this.favoritos];
      }
      this.salvarFavoritos();
    },

    ehFavorito(nomeTabela) {
      return this.favoritos.includes(nomeTabela);
    },

    registrarRecente(nomeTabela) {
      this.recentes = [nomeTabela, ...this.recentes.filter(n => n !== nomeTabela)].slice(0, 5);
      this.salvarRecentes();
    },

    async selecionarTabela(nome) {
      this.abaAtiva = 'dados';
      this.mostrarBusca = false;
      this.tabelaSelecionada = nome;
      this.registrarRecente(nome);
      this.pagina = 1;
      this.ordenarColuna = null;
      this.direcaoOrdem = 'asc';
      this.filtrosAtivos = {};
      this.statsAbertoColuna = null;
      this.linhas = [];
      this.colunas = [];
      this.colunasOriginais = []; // ✅ NOVO
      this.totalRegistros = 0;
      this.cardsExpandidos = new Set();

      await Promise.all([
        this.carregarColunas(nome),
        this.carregarDados(),
        this.carregarFks(nome),
        this.carregarFksInferidas(nome),
      ]);
      await this.carregarLabelsParaLinhas(nome, this.linhas);
    },

    async carregarColunas(nome) {
      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(nome)}/colunas`);
        if (!res.ok) throw new Error(await res.text());
        const colunasCarregadas = await res.json();
        
        // ✅ NOVO: guardar nomes originais e traduzir
        this.colunasOriginais = colunasCarregadas;
        this.colunas = this.traduzirListaColunas(colunasCarregadas);
        
        this.aplicarPreferenciasColunas(nome);
      } catch {
        this.exibirErro('Não foi possível carregar as colunas desta tabela.');
      }
    },

    aplicarPreferenciasColunas(nomeTabela) {
      const salva = this.lerJsonLocal(this.chaveColunasTabela(nomeTabela), null);
      const novo = {};
      const nomesColunas = this.colunasOriginais.map(c => c.nome);
      for (const col of nomesColunas) {
        novo[col] = salva && Object.prototype.hasOwnProperty.call(salva, col) ? salva[col] : true;
      }
      this.colunasVisiveis = novo;
    },

    alternarColunaVisivel(nomeColuna) {
      this.colunasVisiveis[nomeColuna] = this.colunasVisiveis[nomeColuna] === false;
      this.colunasVisiveis = { ...this.colunasVisiveis };
      if (this.tabelaSelecionada) {
        this.salvarJsonLocal(this.chaveColunasTabela(this.tabelaSelecionada), this.colunasVisiveis);
      }
    },

    // ── FKs ───────────────────────────────────────────────────────

    async carregarFks(nomeTabela) {
      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(nomeTabela)}/fks`);
        if (!res.ok) throw new Error(await res.text());
        const fks = await res.json();
        const mapa = {};
        for (const fk of fks) mapa[fk.coluna] = fk;
        this.fksPorTabela[nomeTabela] = mapa;
        if (this.tabelaSelecionada === nomeTabela) this.fksMapAtual = mapa;
      } catch {
        this.fksPorTabela[nomeTabela] = {};
        if (this.tabelaSelecionada === nomeTabela) this.fksMapAtual = {};
      }
    },

    async carregarFksInferidas(nomeTabela) {
      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(nomeTabela)}/fks_inferidas`);
        if (!res.ok) return;
        const fks = await res.json();
        const mapa = {};
        for (const fk of fks) mapa[fk.coluna] = fk;
        this.fksInferidas[nomeTabela] = mapa;
      } catch {
        this.fksInferidas[nomeTabela] = {};
      }
    },

    async garantirMetadadosTabela(nomeTabela) {
      if (!nomeTabela) return;
      const pendencias = [];
      if (!this.fksPorTabela[nomeTabela]) pendencias.push(this.carregarFks(nomeTabela));
      if (!this.fksInferidas[nomeTabela]) pendencias.push(this.carregarFksInferidas(nomeTabela));
      if (pendencias.length > 0) await Promise.all(pendencias);
    },

    fkDeTabela(nomeTabela, coluna) {
      return this.fksPorTabela[nomeTabela]?.[coluna] || null;
    },

    fkInferidaDeTabela(nomeTabela, coluna) {
      return this.fksInferidas[nomeTabela]?.[coluna] || null;
    },

    fkAtual(coluna) {
      return this.fksMapAtual[coluna] || null;
    },

    fkAtualOuInferida(coluna) {
      return this.fkAtual(coluna) || this.fkInferidaDeTabela(this.tabelaSelecionada, coluna) || null;
    },

    alternarMostrarLabels() {
      this.mostrarLabels = !this.mostrarLabels;
      this.salvarJsonLocal('saidjur_mostrar_labels', this.mostrarLabels);
    },

    async carregarLabels() {
      await this.carregarLabelsParaLinhas(this.tabelaSelecionada, this.linhas);
    },

    async carregarLabelsParaLinhas(tabela, linhas) {
      if (!tabela || !linhas?.length) return;
      await this.garantirMetadadosTabela(tabela);

      const todasFks = {
        ...(this.fksPorTabela[tabela] || {}),
        ...(this.fksInferidas[tabela] || {}),
      };

      const pedidos = [];
      for (const [coluna, fk] of Object.entries(todasFks)) {
        const ids = [...new Set(
          linhas
            .map(l => l[coluna])
            .filter(v => v !== null && v !== undefined && v !== '')
        )];
        if (ids.length > 0) {
          pedidos.push({ tabela: fk.tabela_referenciada, coluna_chave: fk.coluna_referenciada || 'id', ids });
        }
      }

      if (!pedidos.length) return;

      try {
        const res = await fetch('/api/labels/resolver', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolucoes: pedidos }),
        });
        if (!res.ok) return;
        const dados = await res.json();
        this.labels = { ...this.labels, ...dados };
      } catch {
        // silently fail — UI shows raw IDs
      }
    },

    textoCru(valor) {
      if (valor === null || valor === undefined) return '—';
      if (typeof valor === 'object') return JSON.stringify(valor);
      return String(valor);
    },

    labelParaValor(tabelaRef, valor) {
      if (valor === null || valor === undefined || valor === '') return null;
      const mapa = this.labels[tabelaRef] || {};
      return mapa[String(valor)] || null;
    },

    traduzirValor(tabela, coluna, valor) {
      if (!this.mostrarLabels || valor === null || valor === undefined || valor === '') return null;
      return this.dicionarios?.[tabela]?.[coluna]?.[String(valor)] || null;
    },

    descricaoHumana(nomeTabela, coluna, valor) {
      if (!this.mostrarLabels || valor === null || valor === undefined || valor === '') return null;
      const fk = this.fkDeTabela(nomeTabela, coluna) || this.fkInferidaDeTabela(nomeTabela, coluna);
      if (fk) {
        const label = this.labelParaValor(fk.tabela_referenciada, valor);
        if (label) return label;
      }
      return this.traduzirValor(nomeTabela, coluna, valor);
    },

    exibirComLabel(nomeTabela, coluna, valor) {
      if (valor === null || valor === undefined || valor === '') return '—';
      return this.descricaoHumana(nomeTabela, coluna, valor) || this.textoCru(valor);
    },

    exibirValor(nomeTabela, coluna, valor) {
      if (valor === null || valor === undefined || valor === '') return '—';
      const descricao = this.descricaoHumana(nomeTabela, coluna, valor);
      if (descricao) return `${descricao} (${this.textoCru(valor)})`;
      return this.textoCru(valor);
    },

    valorDetalhe(nomeTabela, coluna, valor) {
      const descricao = this.descricaoHumana(nomeTabela, coluna, valor);
      if (descricao) return `${descricao} (${this.textoCru(valor)})`;
      return this.valorFormatado(valor);
    },

    ehFkValido(coluna, valor) {
      return Boolean(this.fkAtualOuInferida(coluna) && valor !== null && valor !== undefined && valor !== '');
    },

    ehFkValidoNaTabela(nomeTabela, coluna, valor) {
      return Boolean(
        (this.fkDeTabela(nomeTabela, coluna) || this.fkInferidaDeTabela(nomeTabela, coluna))
        && valor !== null
        && valor !== undefined
        && valor !== ''
      );
    },

    async abrirFk(event, tabelaOrigem, colunaOrigem, valor) {
      event.stopPropagation();
      if (valor === null || valor === undefined || valor === '') return;

      if (!this.fksPorTabela[tabelaOrigem]) {
        await this.carregarFks(tabelaOrigem);
      }
      if (!this.fksInferidas[tabelaOrigem]) {
        await this.carregarFksInferidas(tabelaOrigem);
      }
      const fk = this.fkDeTabela(tabelaOrigem, colunaOrigem) || this.fkInferidaDeTabela(tabelaOrigem, colunaOrigem);
      if (!fk) return;

      const filtros = encodeURIComponent(JSON.stringify({
        [fk.coluna_referenciada]: { op: 'igual', valor: String(valor) },
      }));

      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(fk.tabela_referenciada)}/linhas?por_pagina=1&filtros=${filtros}`);
        if (!res.ok) throw new Error(await res.text());
        const dados = await res.json();
        if (!dados.linhas || dados.linhas.length === 0) {
          this.exibirErro(`Registro referenciado não encontrado em ${fk.tabela_referenciada}.`);
          return;
        }

        const colsRes = await fetch(`/api/tabelas/${encodeURIComponent(fk.tabela_referenciada)}/colunas`);
        const cols = colsRes.ok ? await colsRes.json() : [];

        this.abrirDetalheRegistro({
          tabela: fk.tabela_referenciada,
          registro: dados.linhas[0],
          colunas: cols,
          contextoLinhas: dados.linhas,
          indice: 0,
        });
      } catch (e) {
        this.exibirErro('Falha ao abrir referência: ' + e.message);
      }
    },

    // ── Dados / paginação ─────────────────────────────────────────

    async carregarDados() {
      if (!this.tabelaSelecionada) return;

      this.carregandoDados = true;
      try {
        const params = new URLSearchParams({
          pagina: this.pagina,
          por_pagina: this.porPagina,
        });

        if (this.ordenarColuna) {
          params.set('ordenar_por', this.ordenarColuna);
          params.set('direcao', this.direcaoOrdem);
        }

        if (Object.keys(this.filtrosAtivos).length > 0) {
          params.set('filtros', JSON.stringify(this.filtrosAtivos));
        }

        const res = await fetch(
          `/api/tabelas/${encodeURIComponent(this.tabelaSelecionada)}/linhas?${params}`
        );
        if (!res.ok) throw new Error(await res.text());

        const dados = await res.json();
        this.linhas = dados.linhas;
        this.totalRegistros = dados.total;
        await this.carregarLabelsParaLinhas(this.tabelaSelecionada, this.linhas);
      } catch (e) {
        this.exibirErro('Erro ao carregar os dados: ' + e.message);
      } finally {
        this.carregandoDados = false;
      }
    },

    irPagina(nova) {
      if (nova < 1 || nova > this.totalPaginas) return;
      this.pagina = nova;
      this.cardsExpandidos = new Set();
      this.carregarDados();
      // ✅ Scroll para topo após mudar página
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    // ── Ordenação ─────────────────────────────────────────────────

    ordenarPor(coluna) {
      if (this.ordenarColuna === coluna) {
        this.direcaoOrdem = this.direcaoOrdem === 'asc' ? 'desc' : 'asc';
      } else {
        this.ordenarColuna = coluna;
        this.direcaoOrdem = 'asc';
      }
      this.pagina = 1;
      this.carregarDados();
    },

    // ── Filtros ───────────────────────────────────────────────────

    abrirFiltro(coluna) {
      if (this.filtroAberto === coluna) {
        this.filtroAberto = null;
        return;
      }
      this.filtroAberto = coluna;
      const atual = this.filtrosAtivos[coluna];
      this.filtroTemp = atual
        ? { op: atual.op, valor: atual.valor }
        : { op: 'contem', valor: '' };
    },

    aplicarFiltro(coluna) {
      if (!this.filtroTemp.valor.trim()) {
        this.removerFiltro(coluna);
        return;
      }
      this.filtrosAtivos[coluna] = { ...this.filtroTemp };
      this.filtroAberto = null;
      this.pagina = 1;
      this.carregarDados();
    },

    removerFiltro(coluna) {
      delete this.filtrosAtivos[coluna];
      this.filtrosAtivos = { ...this.filtrosAtivos };
      this.pagina = 1;
      this.carregarDados();
    },

    limparFiltros() {
      this.filtrosAtivos = {};
      this.pagina = 1;
      this.carregarDados();
    },

    // ── Busca global incremental ─────────────────────────────────

    cancelarBuscaGlobal() {
      if (this.buscaController) {
        this.buscaController.abort();
        this.buscaController = null;
      }
      this.buscandoGlobal = false;
      this.buscaCancelada = true;
    },

    async buscarGlobal() {
      const termo = this.termoBusca.trim();
      if (!termo) return;

      if (this.buscaController) this.buscaController.abort();

      this.termoBuscaAtiva = termo;
      this.abaAtiva = 'dados';
      this.mostrarBusca = true;
      this.tabelaSelecionada = null;
      this.buscandoGlobal = true;
      this.buscaCancelada = false;
      this.resultadosBusca = [];
      this.resultadosBuscaSimplificados = {};
      this.buscaProgresso = { processadas: 0, total: 0, encontrados: 0 };
      this.buscaController = new AbortController();

      try {
        const res = await fetch(`/api/busca/stream?q=${encodeURIComponent(termo)}`, {
          signal: this.buscaController.signal,
        });
        if (!res.ok || !res.body) throw new Error(await res.text());

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const eventos = buffer.split('\n\n');
          buffer = eventos.pop() || '';

          for (const bloco of eventos) {
            const linha = bloco.split('\n').find(l => l.startsWith('data: '));
            if (!linha) continue;
            const evento = JSON.parse(linha.slice(6));
            if (evento.tipo === 'result') {
              this.resultadosBusca = [...this.resultadosBusca, ...evento.items];
            } else if (evento.tipo === 'progress' || evento.tipo === 'done') {
              this.buscaProgresso = {
                processadas: evento.processadas || 0,
                total: evento.total || 0,
                encontrados: evento.encontrados || 0,
              };
            } else if (evento.tipo === 'error') {
              throw new Error(evento.mensagem || 'Erro na busca.');
            }
          }
        }

        // ✅ Carrega labels para os resultados da busca
        if (this.resultadosBusca.length > 0) {
          const tabelas_unicas = [...new Set(this.resultadosBusca.map(r => r.tabela))];
          for (const nomeTabela of tabelas_unicas) {
            const gruposTabela = this.resultadosBusca.filter(r => r.tabela === nomeTabela);
            const linhasTabela = gruposTabela.flatMap(grupo => grupo.registros || []);
            await this.garantirMetadadosTabela(nomeTabela);
            await this.carregarLabelsParaLinhas(nomeTabela, linhasTabela);
          }
          this.simplificarResultadosBusca();
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          this.exibirErro('Erro na busca: ' + e.message);
        }
      } finally {
        this.buscandoGlobal = false;
      }
    },

    fecharBusca() {
      this.cancelarBuscaGlobal();
      this.mostrarBusca = false;
      this.termoBusca = '';
      this.resultadosBusca = [];
      this.resultadosBuscaSimplificados = {};
      this.buscaProgresso = { processadas: 0, total: 0, encontrados: 0 };
      this.buscaCancelada = false;
    },

    reiniciarBusca() {
      this.termoBusca = this.termoBuscaAtiva;
      this.buscarGlobal();
    },

    // ── ✅ EXPORTAÇÃO DE BUSCA ────────────────────────────────────

    /**
     * Exporta resultados de busca em Excel ou CSV
     */
    async exportarResultadosBusca(formato = 'excel', tabela = null, modo = 'tecnico') {
      if (this.resultadosBusca.length === 0) {
        this.exibirErro('Nenhum resultado para exportar');
        return;
      }

      this.exportandoBusca = true;

      try {
        const params = new URLSearchParams({ formato, modo });
        if (tabela) {
          params.set('tabela', tabela);
        }

        const res = await fetch('/api/exportar/busca?' + params, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dados: this.resultadosBusca, termo: this.termoBuscaAtiva }),
        });

        if (!res.ok) {
          const erro = await res.json();
          throw new Error(erro.detail || 'Erro ao exportar');
        }

        // Extrair nome do arquivo do header Content-Disposition
        const contentDisposition = res.headers.get('content-disposition');
        let nomeArquivo = `busca_saidjur.${formato === 'excel' ? 'xlsx' : 'csv'}`;
        
        if (contentDisposition) {
          const match = contentDisposition.match(/filename=(.+?)(?:;|$)/);
          if (match) nomeArquivo = match[1].replace(/"/g, '');
        }

        // Criar blob e fazer download
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = nomeArquivo;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        this.exibirErro(null);
      } catch (e) {
        this.exibirErro('Erro ao exportar: ' + e.message);
      } finally {
        this.exportandoBusca = false;
      }
    },

    /**
     * Obtém lista de tabelas encontradas na busca
     */
    obterTabelasEncontradas() {
      if (!this.resultadosBusca.length) return [];
      const tabelas = [...new Set(this.resultadosBusca.map(r => r.tabela))];
      return tabelas.sort();
    },

    // ── Estatísticas de coluna ───────────────────────────────────

    async abrirStatsColuna(coluna) {
      if (this.statsAbertoColuna === coluna) {
        this.statsAbertoColuna = null;
        this.statsColuna = null;
        return;
      }

      this.statsAbertoColuna = coluna;
      this.carregandoStats = true;
      this.statsColuna = null;

      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(this.tabelaSelecionada)}/colunas/${encodeURIComponent(coluna)}/stats`);
        if (!res.ok) throw new Error(await res.text());
        this.statsColuna = await res.json();
      } catch (e) {
        this.exibirErro('Falha ao carregar estatísticas: ' + e.message);
      } finally {
        this.carregandoStats = false;
      }
    },

    // ── Modal de detalhe ─────────────────────────────────────────

    abrirDetalheIndice(indice) {
      if (!this.linhas[indice]) return;
      this.abrirDetalheRegistro({
        tabela: this.tabelaSelecionada,
        registro: this.linhas[indice],
        colunas: this.colunasOriginais,
        contextoLinhas: this.linhas,
        indice,
      });
    },

    abrirDetalheRegistro({ tabela, registro, colunas, contextoLinhas, indice }) {
      this.detalheTabela = tabela;
      this.detalheRegistro = registro;
      this.detalheColunas = colunas || [];
      this.detalheLinhasContexto = contextoLinhas || [];
      this.detalheIndiceContexto = Number.isInteger(indice) ? indice : -1;
      this.detalheAberto = true;
    },

    fecharDetalhe() {
      this.detalheAberto = false;
      this.detalheRegistro = null;
      this.detalheTabela = null;
      this.detalheIndiceContexto = -1;
    },

    navegarDetalhe(delta) {
      if (!this.detalheLinhasContexto.length || this.detalheIndiceContexto < 0) return;
      const novo = this.detalheIndiceContexto + delta;
      if (novo < 0 || novo >= this.detalheLinhasContexto.length) return;
      this.abrirDetalheRegistro({
        tabela: this.detalheTabela,
        registro: this.detalheLinhasContexto[novo],
        colunas: this.detalheColunas,
        contextoLinhas: this.detalheLinhasContexto,
        indice: novo,
      });
    },

    async copiarValor(valor) {
      await navigator.clipboard.writeText(this.valorTexto(valor));
    },

    atalhosTeclado(event) {
      if (!this.detalheAberto) return;
      if (event.key === 'Escape') this.fecharDetalhe();
      if (event.key === 'ArrowRight') this.navegarDetalhe(1);
      if (event.key === 'ArrowLeft') this.navegarDetalhe(-1);
    },

    valorTexto(valor) {
      if (valor === null || valor === undefined) return '—';
      if (typeof valor === 'object') return JSON.stringify(valor, null, 2);
      return String(valor);
    },

    valorFormatado(valor) {
      if (valor === null || valor === undefined) return '—';
      if (typeof valor === 'number') return String(valor);

      const texto = String(valor);
      if (this.ehDataZero(texto)) return '—';
      if (this.ehData(texto)) return this.formatarData(texto);

      if (this.ehJson(texto)) {
        try { return JSON.stringify(JSON.parse(texto), null, 2); } catch { return texto; }
      }
      if (this.ehXml(texto)) return this.indentarXml(texto);
      return texto;
    },

    classeCodigo(valor) {
      const texto = this.valorTexto(valor);
      if (this.ehJson(texto)) return 'language-json';
      if (this.ehXml(texto)) return 'language-markup';
      return '';
    },

    ehJson(texto) {
      const t = (texto || '').trim();
      return (t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'));
    },

    ehXml(texto) {
      const t = (texto || '').trim();
      return t.startsWith('<') && t.endsWith('>') && t.includes('</');
    },

    ehUrl(texto) {
      return /^https?:\/\//i.test((texto || '').trim());
    },

    ehDataZero(texto) {
      if (!texto) return false;
      // Detecta valor sentinela de data/hora zerada do MySQL
      return /^0{4}-0{2}-0{2}([ T]0{2}:0{2}(:\d{2})?)?$/.test(texto.trim())
        || /^0{2}:0{2}(:\d{2})?$/.test(texto.trim());
    },

    ehData(texto) {
      if (!texto) return false;
      if (this.ehDataZero(texto)) return false;
      if (/^\d{4}-\d{2}-\d{2}/.test(texto) || /^\d{10,13}$/.test(texto)) return !Number.isNaN(new Date(texto).getTime());
      return false;
    },

    formatarData(valor) {
      const d = /^\d{10,13}$/.test(String(valor)) ? new Date(Number(valor)) : new Date(valor);
      if (Number.isNaN(d.getTime())) return String(valor);
      return d.toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },

    indentarXml(xml) {
      return xml
        .replace(/(>)(<)(\/*)/g, '$1\n$2$3')
        .split('\n')
        .reduce((acc, line) => {
          const limpo = line.trim();
          if (!limpo) return acc;
          const ultima = acc.length ? acc[acc.length - 1].nivel : 0;
          let nivel = ultima;
          if (/^<\//.test(limpo)) nivel = Math.max(0, nivel - 1);
          acc.push({ texto: `${'  '.repeat(nivel)}${limpo}`, nivel: /^<[^!?/][^>]*[^/]?>$/.test(limpo) ? nivel + 1 : nivel });
          return acc;
        }, [])
        .map(x => x.texto)
        .join('\n');
    },

    // ── Console SQL ──────────────────────────────────────────────

    async executarSql() {
      if (!this.sqlQuery.trim()) return;
      this.abaAtiva = 'sql';
      this.sqlCarregando = true;
      this.sqlPagina = 1;

      try {
        const res = await fetch('/api/sql', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: this.sqlQuery }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || await res.text());
        const dados = await res.json();
        this.sqlResultado = dados;
        this.sqlTabelaContexto = this.extrairTabelaPrincipalSql(this.sqlQuery);
        this.atualizarHistoricoSql(this.sqlQuery);
        await this.carregarLabelsParaLinhas(this.sqlTabelaContexto, dados.linhas || []);
      } catch (e) {
        this.exibirErro('Erro no SQL: ' + e.message);
      } finally {
        this.sqlCarregando = false;
      }
    },

    atualizarHistoricoSql(query) {
      const limpa = query.trim();
      this.sqlHistorico = [limpa, ...this.sqlHistorico.filter(q => q !== limpa)].slice(0, 10);
      this.salvarJsonLocal('saidjur_sql_historico', this.sqlHistorico);
    },

    usarQueryHistorico(query) {
      this.sqlQuery = query;
      this.abaAtiva = 'sql';
    },

    extrairTabelaPrincipalSql(query) {
      const match = query.match(/\bfrom\s+(?:[`"]?[a-zA-Z0-9_]+[`"]?\.)?[`"]?([a-zA-Z0-9_]+)[`"]?/i);
      return match ? match[1] : null;
    },

    irPaginaSql(delta) {
      const nova = this.sqlPagina + delta;
      if (nova < 1 || nova > this.sqlTotalPaginas) return;
      this.sqlPagina = nova;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    // ── Exportação ────────────────────────────────────────────────

    urlExportar(formato) {
      if (!this.tabelaSelecionada) return '#';
      const params = new URLSearchParams({ formato });
      if (Object.keys(this.filtrosAtivos).length > 0) {
        params.set('filtros', JSON.stringify(this.filtrosAtivos));
      }
      return `/api/exportar/${encodeURIComponent(this.tabelaSelecionada)}?${params}`;
    },

    // ── Utilitários ───────────────────────────────────────────────

    formatarNumero(n) {
      if (n === null || n === undefined) return '—';
      return Number(n).toLocaleString('pt-BR');
    },

    exibirErro(msg) {
      this.mensagemErro = msg;
      setTimeout(() => { this.mensagemErro = null; }, 8000);
    },
  };
}
