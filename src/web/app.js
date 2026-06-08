/**
 * Lógica principal do Visualizador de Dados SaidJur
 * Usa Alpine.js para reatividade sem build step.
 */

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
    buscandoGlobal: false,
    mostrarBusca: false,
    buscaProgresso: { processadas: 0, total: 0, encontrados: 0 },
    buscaController: null,

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

    // ── Inicialização ─────────────────────────────────────────────

    async iniciar() {
      this.carregarPreferenciasLocal();
      this.sqlHistorico = this.lerJsonLocal('saidjur_sql_historico', []);
      await Promise.all([this.carregarTabelas(), this.carregarDashboard()]);
      window.addEventListener('keydown', (event) => this.atalhosTeclado(event));
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
      this.totalRegistros = 0;

      await Promise.all([
        this.carregarColunas(nome),
        this.carregarDados(),
        this.carregarFks(nome),
      ]);
    },

    async carregarColunas(nome) {
      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(nome)}/colunas`);
        if (!res.ok) throw new Error(await res.text());
        this.colunas = await res.json();
        this.aplicarPreferenciasColunas(nome);
      } catch {
        this.exibirErro('Não foi possível carregar as colunas desta tabela.');
      }
    },

    aplicarPreferenciasColunas(nomeTabela) {
      const salva = this.lerJsonLocal(this.chaveColunasTabela(nomeTabela), null);
      const novo = {};
      const nomesColunas = this.colunas.map(c => c.nome);
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

    fkDeTabela(nomeTabela, coluna) {
      return this.fksPorTabela[nomeTabela]?.[coluna] || null;
    },

    fkAtual(coluna) {
      return this.fksMapAtual[coluna] || null;
    },

    async abrirFk(event, tabelaOrigem, colunaOrigem, valor) {
      event.stopPropagation();
      if (valor === null || valor === undefined || valor === '') return;

      if (!this.fksPorTabela[tabelaOrigem]) {
        await this.carregarFks(tabelaOrigem);
      }
      const fk = this.fkDeTabela(tabelaOrigem, colunaOrigem);
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
      } catch (e) {
        this.exibirErro('Erro ao carregar os dados: ' + e.message);
      } finally {
        this.carregandoDados = false;
      }
    },

    irPagina(nova) {
      if (nova < 1 || nova > this.totalPaginas) return;
      this.pagina = nova;
      this.carregarDados();
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
      }
      this.buscandoGlobal = false;
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
      this.resultadosBusca = [];
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
      this.buscaProgresso = { processadas: 0, total: 0, encontrados: 0 };
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
        colunas: this.colunas,
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
      this.$nextTick(() => {
        if (window.Prism) {
          window.Prism.highlightAllUnder(this.$refs.modalDetalhe);
        }
      });
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

    ehData(texto) {
      if (!texto) return false;
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
        this.sqlResultado = await res.json();
        this.atualizarHistoricoSql(this.sqlQuery);
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

    irPaginaSql(delta) {
      const nova = this.sqlPagina + delta;
      if (nova < 1 || nova > this.sqlTotalPaginas) return;
      this.sqlPagina = nova;
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
