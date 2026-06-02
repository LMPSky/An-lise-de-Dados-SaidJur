/**
 * Lógica principal do Visualizador de Dados SaidJur
 * Usa Alpine.js para reatividade sem build step.
 */

function app() {
  return {
    // ── Estado global ─────────────────────────────────────────────
    nomeBanco: '',
    mensagemErro: null,

    // ── Tabelas (sidebar) ─────────────────────────────────────────
    tabelas: [],
    carregandoTabelas: true,
    filtroTabela: '',
    tabelaSelecionada: null,

    // ── Dados da tabela ───────────────────────────────────────────
    colunas: [],
    linhas: [],
    totalRegistros: 0,
    pagina: 1,
    porPagina: 50,
    ordenarColuna: null,
    direcaoOrdem: 'asc',
    carregandoDados: false,
    filtrosAtivos: {},     // { coluna: { op, valor } }
    filtroAberto: null,    // nome da coluna com popover aberto
    filtroTemp: { op: 'contem', valor: '' },

    // ── Busca global ──────────────────────────────────────────────
    termoBusca: '',
    termoBuscaAtiva: '',
    resultadosBusca: [],
    buscandoGlobal: false,
    mostrarBusca: false,

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

    // ── Inicialização ─────────────────────────────────────────────

    async iniciar() {
      await this.carregarTabelas();
    },

    // ── Tabelas ───────────────────────────────────────────────────

    async carregarTabelas() {
      this.carregandoTabelas = true;
      try {
        const res = await fetch('/api/tabelas');
        if (!res.ok) throw new Error(await res.text());
        this.tabelas = await res.json();

        // Tenta descobrir o nome do banco pela URL (informação contextual)
        if (this.tabelas.length > 0) {
          this.nomeBanco = 'SaidJur';
        }
      } catch (e) {
        this.exibirErro('Não foi possível carregar a lista de tabelas. Verifique se o servidor está rodando e o banco configurado.');
        this.tabelas = [];
      } finally {
        this.carregandoTabelas = false;
      }
    },

    async selecionarTabela(nome) {
      if (this.tabelaSelecionada === nome) return;

      this.tabelaSelecionada = nome;
      this.mostrarBusca = false;
      this.pagina = 1;
      this.ordenarColuna = null;
      this.direcaoOrdem = 'asc';
      this.filtrosAtivos = {};
      this.linhas = [];
      this.colunas = [];
      this.totalRegistros = 0;

      await Promise.all([
        this.carregarColunas(nome),
        this.carregarDados(),
      ]);
    },

    async carregarColunas(nome) {
      try {
        const res = await fetch(`/api/tabelas/${encodeURIComponent(nome)}/colunas`);
        if (!res.ok) throw new Error(await res.text());
        this.colunas = await res.json();
      } catch (e) {
        this.exibirErro('Não foi possível carregar as colunas desta tabela.');
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

        const filtros = this.filtrosAtivos;
        if (Object.keys(filtros).length > 0) {
          params.set('filtros', JSON.stringify(filtros));
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
      this.filtrosAtivos = { ...this.filtrosAtivos }; // força reatividade
      this.pagina = 1;
      this.carregarDados();
    },

    limparFiltros() {
      this.filtrosAtivos = {};
      this.pagina = 1;
      this.carregarDados();
    },

    // ── Busca global ──────────────────────────────────────────────

    async buscarGlobal() {
      const termo = this.termoBusca.trim();
      if (!termo) return;

      this.termoBuscaAtiva = termo;
      this.mostrarBusca = true;
      this.tabelaSelecionada = null;
      this.buscandoGlobal = true;
      this.resultadosBusca = [];

      try {
        const res = await fetch(`/api/busca?q=${encodeURIComponent(termo)}`);
        if (!res.ok) throw new Error(await res.text());
        this.resultadosBusca = await res.json();
      } catch (e) {
        this.exibirErro('Erro na busca: ' + e.message);
      } finally {
        this.buscandoGlobal = false;
      }
    },

    fecharBusca() {
      this.mostrarBusca = false;
      this.termoBusca = '';
      this.resultadosBusca = [];
    },

    // ── Exportação ────────────────────────────────────────────────

    urlExportar(formato) {
      if (!this.tabelaSelecionada) return '#';
      const params = new URLSearchParams({ formato });
      const filtros = this.filtrosAtivos;
      if (Object.keys(filtros).length > 0) {
        params.set('filtros', JSON.stringify(filtros));
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
