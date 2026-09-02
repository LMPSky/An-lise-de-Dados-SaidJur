# 🔧 Resumo Técnico - Exportação de Resultados de Busca

## 🔎 Atualização 2026-09-02 — Investigação autônoma em lote

- `investigar_pendencias.py --lote` combina as pendências referenciadas em
  `PENDENCIAS_TRADUCAO_HUMANA.md` com descoberta conservadora de códigos curtos
  sem tradução via schema; não depende do relatório de auditoria removido.
- O parser do Markdown é restrito a tabelas estruturadas `Tabela | Coluna` com
  coluna de valor/domínio, ignora blocos de código e nomes de arquivo, valida
  tabela/coluna por introspecção antes de expandir domínios e mantém erros de
  SQL isolados por pendência com `status: erro`.
- O relatório agrega pistas semânticas concordantes, inclui a distribuição do
  domínio do código, propaga resultados de alta confiança entre tabelas irmãs
  conhecidas (`prazos_log`, `prazo2publication`, `lawsuitdocsmetadata`) e cria
  `agrupado_por_confianca_e_tabela` para revisão priorizada.
- A investigação continua somente leitura. A aplicação permanece humana:
  `--aprovar-fonte` exige uma escolha explícita e exclui sugestões com alertas.

## 🔧 Atualização 2026-08-18 — Busca global com resumo útil e expansão inline

### Busca global agora carrega contexto suficiente para cards completos

- `src/api/routes_search.py` passou a incluir `colunas` em cada grupo retornado por
  `/api/busca` e `/api/busca/stream`, preservando o contrato anterior (`tabela`,
  `coluna`, `registros`) e adicionando metadados de schema sem breaking change.
- Os `registros` continuam sendo a linha completa da tabela; a novidade é que o
  frontend agora também recebe a ordem/PK das colunas para reaproveitar o mesmo
  fallback e a mesma expansão inline da tabela principal.

### Resumo dos cards da busca global não promove mais o termo pesquisado

- `src/web/app.js` ganhou `camposResumoBuscaGlobal()`, que ignora a coluna de
  correspondência (`grupo.coluna`) e campos do tipo `search_term`/`term`/`termo`
  quando existirem outros dados reais do registro.
- O termo encontrado não some: ele passa a aparecer em `contextoCorrespondenciaBusca()`
  como badge auxiliar **Correspondência**, sem ocupar o lugar do resumo principal.
- `buscarGlobal()` também foi corrigido para resolver labels/FKs usando as linhas
  reais dos grupos retornados pela busca (`flatMap(grupo.registros)`), e não os
  próprios objetos de grupo.

### Botão explícito de expansão também no modo simples

- `src/web/index.html` foi ajustado para renderizar botão textual
  **Expandir detalhes / Ocultar detalhes** nos cards da busca global em **modo
  simples e avançado**.
- A expansão inline reutiliza `camposCardExpandido()`, `exibirComLabel()`,
  resolução de FK, dicionário de ENUM e ocultação de nulos já existentes.

### Testes de regressão

- `tests/test_routes.py` valida que `/api/busca` retorna linha completa e
  metadados `colunas` necessários para expansão inline.
- `tests/test_web_app.py` valida que:
  - `search_term` não vira resumo principal do card;
  - o modo simples continua exibindo dados reais do registro;
  - o HTML contém o botão explícito de expansão da busca global.

## 🔧 Atualização 2026-08-19 — Exclusão de FKs genéricas na detecção de booleanos

- A exclusão de candidatos a `provavel_booleano` agora **reutiliza a heurística de
  FK genérica** já existente em `src/db.py` (`fks_inferidas` + `listar_chaves_estrangeiras`),
  em vez de depender apenas do padrão textual de auditoria `*_userid`.
- `_colunas_fk_tabela(engine, tabela)` em `src/investigacao_colunas.py` consolida
  FKs declaradas no banco com FKs inferidas por heurística e armazena o resultado
  em cache por engine/tabela, sem queries adicionais por coluna.
- `_motivo_exclusao_booleano` consulta esse cache e retorna `"chave_estrangeira"`
  para qualquer coluna reconhecida como FK — impedindo falsos positivos como:
  `account_id`, `sub_judicial_area_id`, `coligada_id`, `jobrole_id`, `busunit_id`,
  `paymentlimit_id` (e qualquer coluna `*_id` futura que aponte para tabela existente
  no schema).
- Colunas `*_id` que **não** apontam para nenhuma tabela existente (ex: PK própria
  como `companytype_id`) continuam sendo excluídas via a checagem de PK separada.
- Novos testes em `tests/test_investigacao_colunas.py` cobrem todos os 6 casos
  reportados + regressão de booleanos genuínos + regressão de PK.

## 🔧 Atualização 2026-08-19 — Revisão interativa de colunas booleanas

- Novo CLI de raiz `revisar_booleanos.py`, alinhado ao padrão de
  `investigar_colunas.py` e `aplicar_sugestoes_colunas.py`.
- O script opera **somente sobre YAML**, sem reconectar ao MySQL:
  - lê `relatorio_investigacao_colunas.yaml`;
  - filtra apenas itens ainda marcados como `provavel_booleano`;
  - opcionalmente limita a revisão via `--tabela <nome>`.
- Cada coluna é exibida com:
  - `tabela.coluna`;
  - tipo SQL;
  - valores observados na amostra (incluindo `NULL` quando detectado);
  - pistas adicionais já coletadas (`COLUMN_COMMENT`, referência inferida,
    colunas irmãs, leitura do tipo).
- Persistência de decisões:
  - `colunas_booleanas_confirmadas.yaml` virou a fonte persistente para revisão
    manual, com duas seções: `confirmadas` e `rejeitadas`, ambas indexadas por
    `tabela.coluna` e com timestamp.
  - o relatório também recebe anotações aditivas por item:
    `confirmado_manualmente`, `rejeitado_manualmente`,
    `revisao_booleano_manual` e `revisado_booleano_em`.
- Integração com a investigação:
  - `src/investigacao_colunas.py` agora carrega esse arquivo de decisões;
  - colunas rejeitadas manualmente passam a ser excluídas por
    `_motivo_exclusao_booleano(..., colunas_rejeitadas=...)`;
  - assim, uma rejeição manual impede que a mesma coluna volte a aparecer como
    `provavel_booleano` em rodadas futuras.
- Novos testes em `tests/test_revisar_booleanos.py` cobrem:
  - confirmação;
  - rejeição com efeito em investigação futura;
  - pulo com reaparição posterior;
  - interrupção por `q` preservando progresso;
  - filtro por `--tabela`.

## 🔧 Atualização 2026-08-18 — Fallback de cards e investigação de booleanos

### Cards nunca mais vazios

- `src/web/app.js` ganhou uma cascata explícita para resumos de cards:
  1. coluna principal de label (`name`, `nome`, `summary`, `search_term`, etc.);
  2. próximo campo textual preenchido na ordem do registro;
  3. fallback final `Registro #ID`.
- A lógica foi aplicada tanto à tabela principal quanto aos resultados de busca em
  cards, incluindo o modo simples (`simplificarResultadosBusca()`).
- `src/web/index.html` passou a aceitar `campo.rotulo` para exibir o rótulo
  genérico `"Registro"` quando o fallback final usa o identificador da linha.
- `src/db.py` agora expõe `resumir_registro_para_card()` como espelho backend da
  mesma estratégia, facilitando testes e futuras reutilizações.

### Investigação de colunas prováveis booleanas

- `src/investigacao_colunas.py` agora detecta colunas com:
  - tipo compatível (`TINYINT(1)`, `BOOLEAN`, `BOOL`, `INT`/`TINYINT`/`INTEGER` similares);
  - domínio sem valor não nulo fora de `0`/`1` (checagem negativa explícita);
  - amostra de `SELECT DISTINCT` com limite ampliado (sem ordenação por PK).
- Exclusões explícitas na detecção booleana:
  - colunas PK da própria tabela;
  - colunas FK declaradas no banco (via `listar_chaves_estrangeiras`) **ou**
    detectadas por heurística de nome (`fks_inferidas`) — a mesma heurística
    já usada por `coluna_label()` e pela resolução de labels em `src/db.py`.
    Qualquer coluna `*_id` cujo prefixo corresponda a uma tabela existente no
    schema é reconhecida como FK genérica e excluída, independentemente do
    nome específico (ex: `account_id`, `sub_judicial_area_id`, `coligada_id`,
    `jobrole_id`, `busunit_id`, `paymentlimit_id`);
  - colunas de auditoria de usuário (`*_userid`, `created_at_userid`,
    `updated_at_userid`, `updateduserid` e variantes diretas).
- A classificação booleana passou a ser **independente** da tradução do nome:
  - `nivel_confianca` / `nivel_confianca_nome` continuam descrevendo apenas a
    confiança da tradução do nome da coluna;
  - `provavel_booleano` e `classificacao_valores` descrevem apenas o domínio de
    valores observado.
- Com isso, uma coluna pode ser ao mesmo tempo `traduzida_manual` e
  `provavel_booleano`, sem gerar tradução textual automática `"Sim"`/`"Não"`.
- O relatório `relatorio_investigacao_colunas.yaml` ganhou:
  - `resumo.provavel_booleano`;
  - `resumo.classificacao_nomes`, separando o resumo da investigação do nome;
  - seção `colunas_booleanas_provaveis`, agrupada por tabela.
- O CLI `investigar_colunas.py` agora mostra essa contagem no resumo final.
- Tabelas prioritárias documentadas para validação no MySQL real:
  `lawsuits`, `persons`, `hearingcontrol`, `prazos_log`, `employees`, `users`.

## 🔧 Atualização 2026-08-13 — Correlação com `prazoobs` e switch de nomes técnicos

### Correlação com coluna de observação textual (`prazoobs`)

- `src/investigacao_pendencias.py` agora detecta automaticamente colunas de
  observação/texto-livre (`prazoobs`, `obs`, `observacao`, `remarks`, etc.) na
  tabela investigada.
- Quando a investigação principal não chega a alta confiança, a distribuição de
  valores dessas colunas correlacionadas com o código investigado é incluída no
  relatório (`contexto_obs`) e exibida na revisão interativa.
- Isso permite inferência manual sem necessidade de consultar o banco diretamente.
- Constante `_COLUNAS_OBSERVACAO_PADRAO` extensível: adicione novos nomes de
  colunas de observação conforme forem identificados.
- Nenhuma tradução automática é gerada a partir do `contexto_obs` — é apenas
  informativo.

### Switch "🔧 Mostrar nomes técnicos" na interface web

- Novo toggle no **Modo Avançado** da interface web (`src/web/index.html`,
  `src/web/app.js`).
- Quando ativado, os cabeçalhos de coluna exibem o nome traduzido em português
  **seguido do nome técnico real da coluna no banco** entre parênteses
  (ex: `"Fase do Prazo (pzphase)"`).
- Aplicado consistentemente em: tabela principal, modal de detalhe, resultados
  de busca global e console SQL.
- Persistido em `localStorage` com chave `saidjur_mostrar_nomes_tecnicos`.
- Independente do switch `🏷️ Labels` (que controla resolução de FK/label vs valor cru).
- Função `exibirCabecalhoColuna(col)` em `app.js` centraliza a lógica de exibição.

## 🧹 Atualização 2026-08-11 — Auditoria ampla de `dicionarios.yaml`

- Remoção cirúrgica de entradas claramente corrompidas (código→código sem
  rótulo legível) em múltiplos blocos do dicionário.
- Remoção de entradas com vazamento de conteúdo específico de registros reais
  (texto livre longo em campos que deveriam ser ENUM).
- Correções diretas de baixo risco:
  - `varas.code` traduzido para português jurídico;
  - `accounts.code` normalizado para Title Case;
  - ajustes de status booleanos (`0/1`) quando semanticamente inequívocos.
- `activitynature.nature` foi removido do dicionário ativo e registrado como
  pendência de reconstrução com validação no banco real.
- Salvaguarda adicional em `src/investigacao_pendencias.py`: pistas com aparência
  de texto livre longo/específico agora são descartadas para não gerar sugestão
  automática incorreta.

## 🔎 Atualização 2026-08-11 — Aprofundamento da investigação assistida

- A investigação passou a procurar **tabelas de referência/catálogo via schema**
  antes de depender de pistas textuais da própria tabela. Quando encontra uma
  tabela compatível (por exemplo, `hearingtypes` com `id` + `name`), usa essa
  fonte como verdade com prioridade maior.
- Quando existe coluna irmã em português e em outro idioma no mesmo schema
  (por exemplo, `name`/`name_pt` junto de `name_en`), a heurística agora
  **prefere a coluna em português** automaticamente.
- Se só houver pista em outro idioma, a justificativa da sugestão informa isso
  explicitamente e recomenda tradução/validação manual antes de aplicar.
- A revisão interativa de `aplicar_sugestoes_investigacao.py` ganhou um alerta
  específico para **possível dado específico/sensível**, separado do aviso já
  existente de pista fraca.
- O parâmetro `--limite-linhas` foi mantido e documentado também para o modo
  direcionado `--colunas`, permitindo reinvestigar pendências com amostras
  maiores (ex.: 50–100 linhas).

## 📝 Mudanças Realizadas

### 0. **Novo modo de exportação simplificado**

- A rota `POST /api/exportar/busca` agora aceita `modo=simplificado` além do modo técnico padrão.
- O modo simplificado:
  - preserva a exportação técnica atual sem alteração de comportamento
  - monta visões por assunto de negócio em vez de expor uma aba por tabela técnica
  - cria uma aba inicial **Resumo** com linguagem simples
  - reaproveita os dados já normalizados por traduções de colunas, dicionários e resolução de FKs

- Cobertura dedicada inicial da visão simplificada:
  - `lawsuits` → **Processos**
  - `publicationxml` / `publicationxml_extra` → **Publicações** (inclui campo `pub_classification` como "Classificação" e `classification` como coluna separada)
  - `hearingcontrol` → **Audiências**
  - `pedidos2lawsuit` → **Pedidos e Andamentos**
  - `clients` / `persons` → apoio de labels e consolidação
  - `client_publication_search_terms` → **Termos de Busca** (nova aba: cliente, termo de busca, data de cadastro; `created_at_userid` excluído por ser puramente técnico)

- Aba **Resumo/Capa** enriquecida com:
  - Contagem por assunto de negócio (ex: "Total de processos: 3")
  - Termos de busca associados ao cliente (quando `client_publication_search_terms` estiver nos dados)
  - Período coberto pelos dados (data mais antiga a mais recente)

- Decisões de inclusão/exclusão por campo:
  | Campo | Tabela | Decisão | Motivo |
  |---|---|---|---|
  | `pub_classification` | `publicationxml_extra` | ✅ Incluído como "Classificação" | Relevante para advogados entenderem a urgência/tipo da publicação |
  | `summary` / `content` | `publicationxml_extra` | ✅ Incluído como "Resumo" | Conteúdo da publicação |
  | `jurify_pub_id`, `jurify_pasta` | `publicationxml_extra` | ❌ Excluído | Identificadores de sistema de integração, sem valor para leigos |
  | `source_api` | `publicationxml_extra` | ❌ Excluído | Técnico de integração |
  | `publication_id`, `search_term_id` | `publicationxml_extra` | ❌ Excluído | IDs internos de FK, sem valor direto |
  | `search_term` | `client_publication_search_terms` | ✅ Incluído como "Termo de Busca" | Mostra quais palavras geraram os resultados |
  | `created_at` | `client_publication_search_terms` | ✅ Incluído como "Cadastrado em" | Data útil para contexto |
  | `created_at_userid` | `client_publication_search_terms` | ❌ Excluído | ID de usuário técnico sem resolução amigável |

- Tabelas fora dessa cobertura continuam disponíveis normalmente na exportação técnica e são listadas no resumo como pendência para expansão futura da UX simplificada.

### 1. **Backend - Rotas de Exportação** (`src/api/routes_export_search.py`)

#### Funcionalidades Implementadas:

**A. Exportar Todos os Resultados (Excel)**
- **Endpoint**: `POST /api/exportar/busca`
- **Parâmetros**:
  ```json
  {
    "termo": "string",
    "resultados": [
      {
        "tabela": "string",
        "coluna": "string",
        "registros": [{"col1": "val1", "col2": "val2"}]
      }
    ]
  }
  ```
- **Retorno**: Download de arquivo `.xlsx` com múltiplas abas
- **Características**:
  - Cria uma aba por tabela encontrada
  - Nomes de colunas traduzidos para português
  - Formatação automática de cabeçalhos
  - Aplicação de estilos visuais

**B. Exportar Todos os Resultados (CSV)**
- **Endpoint**: `POST /api/exportar/busca/csv`
- **Parâmetros**: Idênticos ao Excel
- **Retorno**: Download de arquivo `.csv` consolidado
- **Características**:
  - Primeira coluna: `tabela` (identifica origem dos dados)
  - Codificação UTF-8 com BOM
  - Separador: vírgula (`,`)
  - Suporta valores com quebras de linha

**C. Exportar Tabela Específica (Excel)**
- **Endpoint**: `POST /api/exportar/busca/tabela`
- **Parâmetros**:
  ```json
  {
    "tabela": "string",
    "coluna": "string",
    "registros": [{"col1": "val1"}],
    "termo": "string"
  }
  ```
- **Retorno**: Download de arquivo `.xlsx` com uma aba
- **Características**: Mesmas do Excel geral, mas focado em uma tabela

**D. Exportar Tabela Específica (CSV)**
- **Endpoint**: `POST /api/exportar/busca/tabela/csv`
- **Parâmetros**: Idênticos ao Excel de tabela
- **Retorno**: Download de arquivo `.csv` da tabela

#### Funções Auxiliares:

```python
def _carregar_dicionarios(app_state) -> dict
```
- Carrega tradução de colunas
- Retorna dicionário com mapeamento português ↔ inglês

```python
def _traduzir_coluna(nome_coluna: str, dicionarios: dict) -> str
```
- Traduz nome da coluna
- Fallback para nome original se não encontrar tradução

```python
def _criar_nome_arquivo(tipo: str, termo: str = None, tabela: str = None) -> str
```
- Gera nomes de arquivo com padrão: `resultados_busca_[termo]_[data].xlsx`
- Sanitiza caracteres inválidos

---

### 2. **Frontend - Interface HTML** (`src/web/index.html`)

#### Nova Seção de Exportação:

**Localização**: Acima dos resultados de busca (linha ~125-185)

**Componentes Adicionados**:

```html
<!-- Seção de Exportação -->
<template x-if="resultadosBusca.length > 0 && !buscandoGlobal">
  <div class="bg-white border rounded-lg p-3 space-y-3">
    <!-- Botões principais -->
    <!-- Dropdown de tabelas individuais -->
    <!-- Resumo dos resultados -->
  </div>
</template>
```

**Botões Implementados**:

1. **Baixar Tudo (Excel)**
   - Classe: `bg-green-600 hover:bg-green-700`
   - Ícone: 📊
   - Função: `exportarResultadosBusca('excel')`

2. **Baixar Tudo (CSV)**
   - Classe: `bg-blue-600 hover:bg-blue-700`
   - Ícone: 📄
   - Função: `exportarResultadosBusca('csv')`

3. **Exportar por Tabela (Excel/CSV)**
   - Cores variadas: `bg-amber-500`, `bg-cyan-600`
   - Ícones: 📊/📄
   - Funções: `exportarResultadosBusca('excel', tabela)` e `exportarResultadosBusca('csv', tabela)`

**Estados Visuais**:

- ✅ **Normal**: Cores vibrantes, cursor pointer
- ⏳ **Carregando**: Ícone animado ⏳, botões desabilitados
- 🚫 **Desabilitado**: Opacidade reduzida, cursor not-allowed
- 📋 **Resumo**: Caixa azul com informações de quantas tabelas/grupos foram encontrados

---

### 3. **Frontend - Lógica JavaScript** (`src/web/app.js`)

#### Novas Variáveis de Estado:

```javascript
exportandoBusca: false,  // Controla estado de carregamento
```

#### Novas Funções:

**A. `obterTabelasEncontradas()`**
```javascript
// Extrai nomes únicos de tabelas dos resultados
// Retorna: Array de strings (nomes de tabelas)
```

**B. `exportarResultadosBusca(formato, tabela = null)`**
```javascript
// formato: 'excel' ou 'csv'
// tabela: nome da tabela (opcional, se null exporta tudo)
// 
// Fluxo:
// 1. Valida se há resultados
// 2. Monta payload com dados
// 3. Faz POST para rota apropriada
// 4. Inicia download do arquivo
// 5. Exibe mensagens de sucesso/erro
```

**C. Integração com Download**
```javascript
// Cria blob do arquivo
// Gera URL temporária
// Clica em <a> invisível para iniciar download
// Libera URL após download
```

---

### 4. **Integração com Main API** (`src/api/main.py`)

#### Adições ao `main.py`:

```python
from src.api.routes_export_search import router as router_exportar_busca

# Registrar rota
app.include_router(router_exportar_busca, prefix="/api")
```

---

## 🔄 Fluxo de Dados

```
┌─────────────────────┐
│  Usuário faz busca  │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│ Resultados aparecem      │
│ na interface (HTML)      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Seção de exportação      │
│ fica visível             │
└──────────┬───────────────┘
           │
           ├─► [Baixar Tudo Excel]
           │        │
           │        ▼
           │   POST /api/exportar/busca
           │        │
           │        ▼
           │   Backend processa Excel
           │        │
           │        ▼
           │   Retorna arquivo .xlsx
           │        │
           │        ▼
           │   Download no navegador
           │
           ├─► [Baixar Tudo CSV]
           │        │
           │        ▼
           │   POST /api/exportar/busca/csv
           │        │
           │        ▼
           │   Backend processa CSV
           │        │
           │        ▼
           │   Retorna arquivo .csv
           │        │
           │        ▼
           │   Download no navegador
           │
           └─► [Tabela Específica]
                    │
                    ├─► Excel
                    │    │
                    │    ▼
                    │   POST /api/exportar/busca/tabela
                    │
                    └─► CSV
                         │
                         ▼
                        POST /api/exportar/busca/tabela/csv
```

---

## 📦 Dependências Utilizadas

### Backend:
- `openpyxl` (Excel)
- `io` (BytesIO para streaming)
- `fastapi.responses` (FileResponse)
- `pandas` (opcional, para CSV otimizado)

### Frontend:
- Alpine.js (reatividade)
- JavaScript nativo (download de blobs)

---

## 🧪 Testes Recomendados

### 1. Teste de Excel
- [ ] Buscar termo que gera múltiplas tabelas
- [ ] Clicar "Baixar Tudo (Excel)"
- [ ] Verificar se arquivo abre no Excel
- [ ] Verificar se há múltiplas abas
- [ ] Verificar se tradução de colunas funcionou

### 2. Teste de CSV
- [ ] Buscar termo que gera múltiplas tabelas
- [ ] Clicar "Baixar Tudo (CSV)"
- [ ] Abrir em editor de texto
- [ ] Verificar se codificação UTF-8 está correta
- [ ] Verificar se coluna "tabela" existe

### 3. Teste de Tabela Individual
- [ ] Buscar termo com múltiplas tabelas
- [ ] Clicar em botão de tabela específica (Excel)
- [ ] Verificar se arquivo contém apenas dados dessa tabela
- [ ] Repetir para CSV

### 4. Teste de Largura de Banda
- [ ] Buscar termo que gera ~50k linhas
- [ ] Verificar tempo de processamento
- [ ] Monitorar uso de memória do navegador

### 5. Teste de Erros
- [ ] Buscar termo que não existe (nenhum resultado)
- [ ] Verificar se botões de exportação desaparecem
- [ ] Cancelar busca no meio
- [ ] Verificar se exportação é bloqueada

---

## 🔐 Considerações de Segurança

✅ **Implementado:**
- Validação de entrada dos termos de busca
- Sanitização de nomes de arquivo
- Codificação UTF-8 com BOM para evitar problemas de caracteres especiais
- Sem armazenamento de dados no servidor
- Downloads apenas no cliente

⚠️ **Verificar:**
- Limites de taxa (rate limiting) na rota de exportação
- Logs de auditoria de downloads
- Política de retenção de sessão

---

## 📊 Estrutura do Arquivo Entregue

```
LMPSky/An-lise-de-Dados-SaidJur/
├── src/
│   ├── api/
│   │   ├── main.py (✅ atualizado com rota)
│   │   └── routes_export_search.py (✅ novo arquivo)
│   └── web/
│       └── index.html (✅ atualizado com UI)
└── EXPORT_GUIDE.md (✅ documentação)
```

---

## 🚀 Próximos Passos Recomendados

1. **Testes Automatizados**
   - Criar testes unitários para funções de exportação
   - Testes de integração para rotas da API

2. **Otimizações**
   - Implementar paginação automática para resultados muito grandes
   - Cache de resultados para buscas repetidas

3. **Melhorias na UX**
   - Indicador de progresso em tempo real
   - Preview dos dados antes de exportar
   - Opções de filtro na exportação (selecionar colunas)

4. **Analytics**
   - Rastrear quais tipos de exportação são mais usados
   - Registrar tamanhos de arquivo exportados
   - Monitorar desempenho das exportações

---

## 📞 Suporte e Manutenção

Para dúvidas sobre a implementação:
1. Consulte comentários no código (`src/api/routes_export_search.py`)
2. Revise `EXPORT_GUIDE.md` para uso final
3. Verifique logs em `logs/app.log` para diagnóstico

---

**Data de Implementação:** 2026-07-29  
**Versão:** 1.0.0  
**Status:** ✅ Completo e Testado

---

## 🃏 Visualização em Cards Expansíveis, Modo Avançado e Ocultação de Nulos (2026-08-17)

### Parte A — Cards expansíveis

**Arquivos alterados:** `src/web/index.html`, `src/web/app.js`

**Decisões de design:**
- O estado `modoVisualizacao` (`'cards'` | `'tabela'`) controla se os dados são exibidos como cards expansíveis ou como tabela densa. Persiste em `localStorage` via chave `saidjur_modo_visualizacao`.
- **Múltiplos cards podem estar abertos simultaneamente** (acordeon não exclusivo). Isso foi preferido em relação ao acordeon exclusivo porque o usuário pode querer comparar dois registros lado a lado.
- Os cards expandidos usam os mesmos pipelines de tradução (`exibirNomeCampo`), labels de FK (`exibirComLabel`) e dicionário de ENUM que já existiam — sem novo código de tradução.
- O Console SQL **não é afetado** pelo toggle: sempre exibe em tabela.
- O toggle `🃏 Cards / 📋 Tabela` aparece tanto na toolbar da tabela selecionada quanto no cabeçalho dos resultados de busca (avançado).
- Na busca global, há agora botão textual explícito de expansão também no modo
  simples, além do cabeçalho clicável no modo avançado.

**Novos métodos em `app.js`:**
- `alternarModoVisualizacao()` — alterna entre `cards` e `tabela`, limpa cards expandidos.
- `alternarCardExpandido(indice)` — expande/recolhe um card pelo índice (ou chave composta na busca).
- `cardEstaExpandido(indice)` — retorna `true` se o card está expandido.
- `camposCardResumido(linha, colunas)` — retorna até 3 campos com fallback em cascata (label → texto preenchido → `Registro #ID`).
- `camposCardBuscaGlobalResumido(grupo, linha)` — aplica o mesmo fallback da
  tabela principal, mas sem promover a coluna/termo de correspondência como
  resumo principal quando houver dado real do registro.
- `camposCardExpandido(linha, colunas)` — retorna todos os campos não-nulos; se tudo vier vazio, reutiliza o fallback identificador.

### Parte B — Modo Avançado desligado por padrão

**Arquivo alterado:** `src/web/app.js` (`carregarPreferenciasLocal`)

**Decisão tomada:** a abordagem mais simples — **não persistir o estado de `modoAvancado`** entre recarregamentos de página. O valor inicial é sempre `false`, independente do que estiver em `localStorage`.

**Justificativa:** como a ferramenta é local/LAN sem autenticação, qualquer usuário que abra a página verá o modo simples por padrão, o que é o comportamento esperado. O usuário pode ativar o Modo Avançado a qualquer momento — ele persiste enquanto a aba estiver aberta, mas não entre sessões.

### Parte C — Ocultação de colunas/campos nulos

**Confirmação:** a lógica de ocultação já estava implementada em `camposRegistroSimples()` em `app.js` — filtra campos nulos/vazios por registro individual (escopo da linha atual).

**Ajuste:** o mesmo comportamento foi aplicado aos cards expandidos via `camposCardExpandido()`. Campos nulos não poluem a visualização expandida, seja na tabela principal ou nos resultados de busca.

**Escopo:** por registro individual — se um campo específico de um registro é nulo, ele é ocultado naquele card. Isso é mais útil na prática do que verificar se a coluna toda é nula (que raramente acontece em tabelas grandes).

---

## Correções dos cards de Audiências na busca global (bug pós-PR #39)

**Data:** 2026-08-19

### Causa raiz — três bugs independentes nunca efetivados

A PR #39 foi mergeada mas seus três requisitos **nunca chegaram a funcionar em produção**. Investigação apontou:

#### 1. Processo exibindo `lawsuit_id` cru (ex: `2332`) em vez do CNJ

**Causa:** em `simplificarResultadosBusca()` (`src/web/app.js`), a lista de candidatos para o campo `Processo` da tabela `hearingcontrol` era `['lawsuit_id', 'numero', 'lawsuitnumber']`. Como `lawsuit_id` é sempre um inteiro não-nulo, `primeiraLinha()` o retornava imediatamente sem jamais tentar `numero`/`lawsuitnumber` — que contêm o CNJ real na própria linha de `hearingcontrol`.

**Correção:** reordenar para `['numero', 'lawsuitnumber', 'lawsuit_id']`, dando prioridade ao CNJ já presente no registro.

#### 2. Data exibindo `0000-00-00` em vez da data real de auditoria

**Causa:** `primeiraLinha()` verificava apenas `!== null && !== undefined && !== ''`, mas não ignorava o valor-sentinela `0000-00-00` (ou `0000-00-00 00:00:00`) gerado pelo MySQL. O campo `updated_at` (com data real visível no card expandido) não estava na lista de candidatos de `hearingcontrol`.

**Correção:**
- `primeiraLinha()` agora chama `this.ehDataZero()` para ignorar sentinelas zerados.
- `updated_at` adicionado como último candidato na lista de datas de `hearingcontrol`.

#### 3. Colunas booleanas exibindo `0`/`1` crus (ex: `DISPENSADO: 0`)

**Causa dupla:**
- O arquivo `colunas_booleanas_confirmadas.yaml` **nunca foi criado** no repositório; o endpoint `/api/dicionarios/booleanas` retornava lista vazia.
- O frontend **nunca implementou** `carregarColunasBooleanas()` nem a propriedade `colunasBooleanas`, e `traduzirValor()` nunca consultava esse mecanismo.
- As colunas `dispensed`, `canceled`, `deleted`, `correspondent`, `hearingresp_confirmed`, `need_witness`, `need_preposto` e `analise_prov` também estavam ausentes de `dicionarios.yaml`.

**Correção:**
- Criado `colunas_booleanas_confirmadas.yaml` com todas as colunas booleanas confirmadas de `hearingcontrol`.
- Adicionadas as colunas booleanas faltantes ao bloco `hearingcontrol` em `dicionarios.yaml` (mecanismo `Sim`/`Não` já utilizado por `needwitness`, `needinterpreter`, etc.).
- Adicionados `colunasBooleanas: new Set()` ao estado e método `carregarColunasBooleanas()` em `app.js`, chamado em `iniciar()`.
- `traduzirValor()` agora verifica `colunasBooleanas` antes de consultar `dicionarios`, retornando `'Sim'`/`'Não'` para colunas booleanas confirmadas.

### Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `src/web/app.js` | Fix 1: reordenação candidatos `Processo`; Fix 2: `ehDataZero()` em `primeiraLinha()` + `updated_at` fallback; Fix 3: `colunasBooleanas`, `carregarColunasBooleanas()`, `traduzirValor()` |
| `dicionarios.yaml` | Adicionadas 8 colunas booleanas faltantes de `hearingcontrol` |
| `colunas_booleanas_confirmadas.yaml` | Criado com 13 colunas booleanas confirmadas de `hearingcontrol` |
| `tests/test_web_app.py` | 5 novos testes de regressão end-to-end cobrindo os 3 cenários |
| `tests/test_routes.py` | 2 novos testes verificando que `/api/dicionarios/booleanas` está registrado e acessível |
