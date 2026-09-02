# 📊 Visualizador de Dados SaidJur

Bem-vindo! Este programa permite **visualizar, pesquisar e exportar** o conteúdo
do banco de dados SaidJur diretamente no seu navegador — sem precisar escrever
nenhum comando técnico.

---

## 🤔 O que é isso?

É uma ferramenta que transforma um arquivo de banco de dados (`.sql`) em uma
interface fácil de usar, parecida com uma planilha do Excel, onde você pode:

- 🔍 **Pesquisar** qualquer texto em todo o banco de um só lugar
- 📋 **Navegar** pelos registros com paginação automática
- 🔽 **Filtrar** por coluna (como no Excel)
- 📥 **Exportar** para CSV ou Excel
- 🖥️ Tudo rodando **no seu próprio computador**, sem internet

---

## ✅ O que você precisa ter instalado

Antes de começar, instale os dois programas abaixo:

| Programa | Link para download | Para que serve |
|---|---|---|
| **Python 3.11 ou superior** | [python.org/downloads](https://www.python.org/downloads/) | Linguagem que roda o servidor |
| **MySQL Community Server 8.x** | [dev.mysql.com/downloads/installer](https://dev.mysql.com/downloads/installer/) | Banco de dados onde os dados ficam armazenados |

> 💡 **Dica:** Durante a instalação do Python, marque a opção **"Add Python to PATH"**.
> Consulte o arquivo [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) para um guia detalhado com imagens descritas.

---

## 🚀 Instalação em 3 passos

### Passo 1 — Instale Python e MySQL
Baixe e instale os dois programas da tabela acima.
Consulte [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) se precisar de ajuda.

### Passo 2 — Execute o instalador
Clique duas vezes no arquivo **`instalar.bat`**.

Ele vai:
- Criar um ambiente Python isolado
- Instalar todas as dependências automaticamente
- Criar o arquivo `config.yaml` para você configurar

### Passo 3 — Configure o banco de dados
Abra o arquivo **`config.yaml`** (com o Bloco de Notas) e preencha:

```yaml
banco:
  usuario: root          # Seu usuário do MySQL
  senha: "sua_senha"     # Sua senha do MySQL
  nome: saidjur          # Nome que será dado ao banco
```

> ✅ Senhas com caracteres especiais (`#`, `@`, `$`, `!` e aspas escapadas como `\"`)
> funcionam normalmente quando informadas entre aspas no `config.yaml`.

---

## 📂 Importando seu arquivo `.sql`

> ⚠️ Esta etapa pode levar **várias horas** para arquivos grandes (50 GB).
> Seu computador precisa ter pelo menos **100 GB livres em disco**.

**Passo a passo:**

1. Copie seu arquivo `.sql` para a pasta **`dados\`** do programa
2. Clique duas vezes em **`importar.bat`**
3. Quando perguntado, confirme com **S** e pressione Enter
4. Aguarde a barra de progresso concluir ☕

O programa mostrará:
- Quanto já foi carregado (ex: "Lido: 12 GB de 50 GB")
- A velocidade de importação
- O tempo restante estimado

---

## 🖥️ Abrindo o visualizador

1. Clique duas vezes em **`iniciar.bat`**
2. O navegador abre automaticamente em `http://127.0.0.1:8000`
3. Para encerrar, feche a janela do terminal

---

## 🆕 Novidades desta versão

- 🔍 **Busca global incremental** com progresso real ("Buscando em X/Y tabelas") e botão **Cancelar**
- 🧾 **Modal de detalhe do registro** ao clicar em qualquer linha (com copiar valor, links e navegação por teclado)
- 🔗 **Navegação por chaves estrangeiras (FK)** clicando no valor referenciado
- 🏷️ **Resolução automática de labels FK** — colunas FK exibem `Nome (ID)` em vez de apenas o número cru
- 🔎 **Detecção de FKs implícitas** — FKs não declaradas no banco são detectadas automaticamente por heurística de nomes de coluna
- 🎛️ **Toggle Mostrar nomes / Mostrar IDs** — botão para alternar entre exibição com nome e exibição de ID puro
- 🏠 **Dashboard inicial** com estatísticas gerais e 10 maiores tabelas
- 💻 **Console SQL** (somente `SELECT`/`WITH`, limite de 5000 linhas)
- 🎛️ **Mostrar/ocultar colunas** com persistência local por tabela
- ⭐ **Favoritos** e 🕒 **Recentes** na sidebar (persistidos no navegador)
- 📊 **Estatísticas rápidas de coluna** (não nulos, distintos, mínimo/máximo e top 5)

### Endpoints novos

- `GET /api/busca/stream` — busca global incremental via SSE
- `GET /api/tabelas/{nome}/fks` — lista foreign keys da tabela
- `GET /api/tabelas/{nome}/fks_inferidas` — lista FKs detectadas por heurística (FKs implícitas)
- `POST /api/labels/resolver` — resolve IDs em labels em lote para múltiplas tabelas
- `GET /api/dashboard` — dados agregados da tela inicial
- `POST /api/sql` — executa consulta SQL somente leitura
- `GET /api/tabelas/{nome}/colunas/{coluna}/stats` — estatísticas rápidas da coluna

## 📖 Como usar o visualizador

### Busca global
Digite qualquer palavra na **barra de pesquisa no topo** (ex: "João Silva")
e clique em **Buscar**. O sistema vai procurar em **todas as tabelas e colunas** de uma só vez.

### Navegar por tabela
No menu **à esquerda**, clique no nome de qualquer tabela para ver seus dados.
O número ao lado mostra a quantidade de registros.

### Ordenar
Clique no **nome de uma coluna** para ordenar os dados por ela.
Clique de novo para inverter a ordem (▲ crescente / ▼ decrescente).

### Filtrar por coluna
Clique no ícone **🔽** ao lado do nome da coluna para abrir o menu de filtro:
- **Contém** — encontra registros que contenham o texto
- **É igual a** — valor exato
- **Começa com** — ex: "João" encontra "João Silva", "Joãozinho"...
- **Maior que / Menor que** — para números e datas

### Exportar para Excel ou CSV
Clique em **📥 Exportar Excel** ou **📥 Exportar CSV** no topo direito da tabela.
Os filtros aplicados são respeitados na exportação.

### 🧾 Relatório Simplificado para apresentação
Na tela de busca global agora existem **duas opções diferentes**:

- **Relatório Simplificado**: pensado para advogados e usuários leigos. Gera um Excel com:
  - aba inicial **Resumo** com contagens por assunto (ex: "Total de processos: 3"), termos de busca associados ao cliente e período coberto pelos dados
  - abas por assunto de negócio: **Processos**, **Publicações** (com campo "Classificação" de `publicationxml_extra`), **Audiências**, **Pedidos e Andamentos** e **Termos de Busca** (quando `client_publication_search_terms` estiver nos resultados)
  - apenas campos com significado direto para leigos; IDs técnicos, identificadores de integração e campos de log são omitidos
- **Exportação Completa/Técnica**: mantém o formato anterior, com uma aba por tabela técnica para uso da equipe de TI

Cobertura do Relatório Simplificado:
`lawsuits`, `publicationxml`, `publicationxml_extra` (classificação incluída), `hearingcontrol`, `pedidos2lawsuit`, `clients`, `persons` e `client_publication_search_terms` (termos de busca).

Se a busca encontrar outras tabelas, elas continuam disponíveis na exportação técnica e também aparecem na aba de resumo como próximas candidatas para simplificação futura.

> **Correção da busca global (2026-08-18):**
> - os cards da busca não usam mais `search_term`/termo correspondido como resumo principal quando existir dado real do registro;
> - o termo encontrado continua visível apenas como contexto em **Correspondência**;
> - cada card da busca global (modo simples e avançado) agora tem botão explícito **Expandir detalhes / Ocultar detalhes** para revelar todos os campos não-nulos do registro inline.

### 🌐 Traduzindo códigos e ENUMs
Algumas colunas podem guardar códigos curtos, como `nature: "p"` ou campos
numéricos binários (`0` / `1`). Para exibir nomes mais legíveis, copie o
arquivo `dicionarios.yaml` na raiz do projeto e edite os significados:

```yaml
publicationxml:
  nature:
    p: "Publicação"
    m: "Manifestação"
```

Ao recarregar a página, o visualizador relê o arquivo automaticamente. Não é
necessário reiniciar o servidor.

### 🧾 Auditoria completa de traduções (MySQL real)
Para mapear colunas/valores ainda pendentes de tradução no banco real, execute
localmente (ex.: `D:\SaidJur`), com o MySQL já configurado no `config.yaml`:

```bash
python auditar_traducoes.py
```

O script usa `src.config.CONFIG` para conectar ao banco em modo **somente
leitura** e gera `relatorio_auditoria_traducoes.yaml` na raiz do projeto com os
itens pendentes por tabela/coluna (nomes de coluna parciais/não traduzidos e
pendências de ENUM/códigos). Use esse relatório para complementar manualmente
`src/traducoes_colunas.py` e `dicionarios.yaml`.

Para tabelas colossais (por exemplo, `publicationxml`, com milhões de linhas),
o script pode registrar apenas a auditoria dos nomes de coluna e pular a
amostragem de valores de ENUM. Isso é esperado quando a coleta de valores tende
a estourar timeout mesmo com amostragem limitada.

### 🕵️ Investigação assistida de pendências ambíguas (ENUM/códigos)
Depois da auditoria, use a investigação assistida para reduzir o trabalho manual
de descobrir o significado real dos códigos curtos/ambíguos no banco real:

```bash
python investigar_pendencias.py
```

Esse script lê `relatorio_auditoria_traducoes.yaml`, consulta exemplos reais no
banco (somente leitura) e gera `relatorio_investigacao_pendencias.yaml` com:
- tabela/coluna/valor pendente
- busca prioritária de **tabelas de referência/catálogo** detectadas via schema
  (quando houver uma `hearingtypes`, `contracttypes`, etc. compatível com a coluna investigada)
- colunas vizinhas candidatas a pista textual (ex.: nome/descrição)
- linhas de exemplo relevantes
- sugestão de tradução em **alta confiança** quando houver padrão consistente *em coluna com nome semanticamente relacionado* (ex: `name`, `desc`, `title`) — pista forte
- sugestão com **pista única (baixa confiança / pista fraca)** quando a coluna-pista for booleana (`0`/`1`) ou sem nome semântico relacionado; o `aplicar_sugestoes_investigacao.py` exibe um aviso nesse caso
- marcação explícita de **sem pista encontrada** quando não houver evidência clara
- preferência automática por **coluna em português** quando existir uma coluna irmã
  em outro idioma no mesmo schema (ex.: `name`/`name_pt` antes de `name_en`)
- agregação de pistas concordantes de múltiplas colunas e linhas, correlação entre
  tabelas irmãs conhecidas e estatística do domínio do código como sinais auxiliares
- agrupamento final por confiança e tabela para facilitar revisão em lote

> **Nota sobre pistas fortes vs fracas**: uma coluna booleana com valor `0` constante em
> 5/5 linhas de amostra *não* revela o significado do código investigado — é apenas o padrão
> de qualquer tabela com muitos campos opcionais zerados. Somente colunas com nome sugestivo
> (ex: `typename`, `descricao`, `hearing_title`) e valor textual variável são evidência confiável.
>
> **Salvaguarda adicional (Rodada 5)**: pistas que parecem **texto livre longo/específico**
> (por exemplo, frases extensas com data/hora de um caso concreto) são descartadas da sugestão
> automática para evitar vazamento de conteúdo de registros reais para o `dicionarios.yaml`.
>
> **Salvaguarda adicional (Rodada 6)**: sugestões curtas que pareçam **nome próprio
> específico** (por exemplo, `JAC BH Barão`) passam a aparecer com um alerta
> separado de possível dado específico/sensível na revisão interativa antes da aplicação.

Parâmetros úteis:

```bash
python investigar_pendencias.py --relatorio-auditoria relatorio_auditoria_traducoes.yaml --saida relatorio_investigacao_pendencias.yaml --limite-linhas 5
```

Para reinvestigar itens ambíguos com amostragem maior, o mesmo `--limite-linhas`
também funciona no modo direcionado `--colunas`:

```bash
python investigar_pendencias.py --colunas hearingcontrol.hearingtype:11 prazo2publication.pzphase:4 --limite-linhas 50
```

Para investigar todas as pendências documentadas sem recriar a auditoria removida,
e também descobrir códigos curtos ainda ausentes no schema, execute:

```bash
python investigar_pendencias.py --lote --limite-linhas 50
```

O modo de lote continua somente leitura e não altera `dicionarios.yaml`. Para
aprovar explicitamente em lote apenas sugestões de alta confiança vindas de uma
fonte específica (sem alertas de conteúdo sensível), use por exemplo:

```bash
python aplicar_sugestoes_investigacao.py --aprovar-fonte tabela_referencia --dry-run
```

### ✅ Aplicação assistida das sugestões no `dicionarios.yaml`
Para revisar e aplicar sugestões aprovadas sem editar YAML manualmente:

```bash
python aplicar_sugestoes_investigacao.py
```

Modo não-interativo (gerar decisões, revisar arquivo e aplicar depois):

```bash
python aplicar_sugestoes_investigacao.py --gerar-template-decisoes decisoes_investigacao.yaml
python aplicar_sugestoes_investigacao.py --aplicar-decisoes decisoes_investigacao.yaml --dry-run
python aplicar_sugestoes_investigacao.py --aplicar-decisoes decisoes_investigacao.yaml
```

> Observação: o fluxo é separado de propósito. A investigação **não altera**
> `dicionarios.yaml` automaticamente; ela apenas sugere. A decisão final continua
> sendo revisada por humano.
>
> Na revisão interativa, há dois avisos independentes:
> - **Pista fraca**: a evidência existe, mas não é semanticamente forte;
> - **Possível dado específico/sensível**: o texto sugerido pode ser nome de caso,
>   agência, unidade, empresa ou outra entidade real, exigindo validação humana extra.

### 🏷️ Investigação assistida de nomes de coluna (schema)

Além do fluxo de investigação de ENUMs/códigos, há um fluxo dedicado a **nomes de coluna** (metadado de schema), permitindo auditar e sugerir traduções para colunas sem entrada manual em `TRADUCOES_COLUNAS`.

**Investigar todas as colunas de uma tabela:**
```bash
python investigar_colunas.py --tabela prazos_log
```

**Investigar colunas específicas:**
```bash
python investigar_colunas.py --colunas prazos_log.pzphase prazos_log.prazoobs
```

O script é somente leitura e gera `relatorio_investigacao_colunas.yaml` com:
- estado de cada coluna (`traduzida_manual` / `traduzida_heuristica` / `nao_traduzida`)
- pistas coletadas do schema: `COLUMN_COMMENT` do MySQL (alta confiança), tipo de dado, colunas irmãs já traduzidas e referências FK
- sugestão candidata com nível de confiança da **tradução do nome** (`nivel_confianca` e `nivel_confianca_nome`)
- classificação de valores separada e independente:
  - `provavel_booleano: true/false`
  - `classificacao_valores: provavel_booleano` quando:
    - a coluna **não** for PK da própria tabela, nem FK (declarada no banco ou
      detectada pela heurística de nome de `src/db.py` — qualquer `*_id` que
      referencie uma tabela existente no schema é excluída), nem auditoria de
      usuário (`*_userid`, `created_at_userid`, `updated_at_userid`, `updateduserid`);
    - houver checagem negativa de domínio sem encontrar valor fora de `0`/`1`;
    - a amostra de distintos (limite maior) continuar restrita a `0`/`1`/`NULL` com tipo compatível.
- seção `colunas_booleanas_provaveis` agrupada por tabela para futura revisão/promoção a metadado confirmado
- se existir `colunas_booleanas_confirmadas.yaml`, o relatório também anota
  decisões manuais de revisão com campos aditivos como
  `confirmado_manualmente`, `rejeitado_manualmente` e
  `revisao_booleano_manual`

> **Importante:** tradução do **nome** da coluna e classificação do **domínio de valores**
> são dimensões independentes. Uma mesma coluna pode aparecer simultaneamente como
> `traduzida_manual` e `provavel_booleano`.
>
> Para reduzir falso positivo por amostragem enviesada, a detecção booleana não depende
> só de `SELECT DISTINCT ... LIMIT N`: ela também faz uma verificação explícita para
> rejeitar colunas onde exista qualquer valor não nulo fora de `0`/`1`.

**Investigar booleanos primeiro nas tabelas mais usadas:**
```bash
python investigar_colunas.py --tabela lawsuits
python investigar_colunas.py --tabela persons
python investigar_colunas.py --tabela hearingcontrol
python investigar_colunas.py --tabela prazos_log
python investigar_colunas.py --tabela employees
python investigar_colunas.py --tabela users
```

> ⚠️ **Neste ambiente de desenvolvimento/teste os exemplos usam SQLite em memória.**
> A classificação final de booleanos precisa ser confirmada por você no **MySQL real**
> rodando o comando acima a partir da **raiz do projeto** (`python investigar_colunas.py ...`).
> Evite executar `src/investigacao_colunas.py` diretamente, porque o entrypoint
> suportado/documentado é o script da raiz.

**Revisar interativamente as colunas `provavel_booleano`:**
```bash
python revisar_booleanos.py
python revisar_booleanos.py --tabela prazos_log
```

O script lê `relatorio_investigacao_colunas.yaml` e apresenta uma coluna por vez
com:
- `tabela.coluna`
- tipo SQL da coluna
- valores observados na amostra (incluindo `NULL` quando detectado)
- contexto adicional já presente nas pistas da investigação (ex.: comentário do
  schema, referência inferida, colunas irmãs)

Durante a revisão, use:
- `s` → confirma que a coluna é booleana
- `n` → rejeita a coluna como booleana
- `p` → pula por agora; a coluna reaparece na próxima execução
- `q` → sai imediatamente e salva o progresso já feito

As decisões são persistidas automaticamente em
`colunas_booleanas_confirmadas.yaml`:
- `confirmadas` guardam as colunas aprovadas e timestamp de confirmação
- `rejeitadas` guardam as colunas recusadas e timestamp de rejeição

Além disso, o próprio `relatorio_investigacao_colunas.yaml` é anotado com flags
aditivas para refletir o estado manual da revisão. Em execuções futuras de
`investigar_colunas.py`, colunas rejeitadas deixam de ser classificadas como
`provavel_booleano`, evitando regressão mesmo que a amostra continue em `{0,1}`.

**Aplicar sugestões aprovadas em `src/traducoes_colunas.py`:**
```bash
python aplicar_sugestoes_colunas.py
python aplicar_sugestoes_colunas.py --dry-run   # prévia sem alterar o arquivo
```

A aplicação é interativa (`s/n/e` por sugestão) e **nunca sobrescreve** traduções manuais já confirmadas em `TRADUCOES_COLUNAS` sem confirmação explícita.

> **Decisão de design:** as novas entradas são inseridas diretamente em `src/traducoes_colunas.py` (a única fonte canônica), em vez de um arquivo de overrides separado, para manter a unicidade da fonte de verdade. O script usa manipulação segura do arquivo Python (sem eval/exec).

### 🧽 Auditoria ampla de corrupção em `dicionarios.yaml` (Rodada 5)

Na rodada de 2026-08-11, foi feita uma limpeza ampla para remover mapeamentos
claramente corrompidos (código→código), entradas com vazamento de conteúdo
específico de casos reais e traduções em inglês inconsistentes no contexto
jurídico em português.

Resumo operacional:
- entradas sem semântica confiável foram removidas e documentadas em
  `PENDENCIAS_TRADUCAO_HUMANA.md`;
- traduções óbvias de baixo risco foram corrigidas diretamente (ex.: `varas.code`,
  capitalização de `accounts.code`);
- `activitynature.nature` permanece como pendência de reconstrução com validação
  no banco real.
- a investigação assistida passou a priorizar catálogos detectados via schema,
  preferir pistas em português sobre colunas `_en`/`_english` e destacar
  possíveis dados específicos/sensíveis antes da aplicação.

## 🃏 Visualização em cards expansíveis

Por padrão, os registros são exibidos como **cards verticais** que podem ser expandidos com um clique. Isso torna a navegação mais amigável do que tabelas densas com rolagem horizontal.

**Como funciona:**
- Cada card mostra um resumo com 2–3 campos identificadores do registro.
- O resumo usa fallback em cascata: **label principal da tabela → próximo campo textual preenchido da própria linha → `Registro #ID`**.
- Clique no card para **expandir inline** e revelar todos os campos não-nulos em um grid horizontal dentro do próprio fluxo da lista.
- Na **busca global**, o campo que bateu com o termo pesquisado pode aparecer como badge de **Correspondência**, mas não substitui o resumo principal se houver dados reais do processo/publicação.
- Múltiplos cards podem estar expandidos ao mesmo tempo — o estado não é um acordeon exclusivo.
- Campos com valor nulo/vazio são automaticamente ocultados na visualização expandida, mantendo a tela limpa.
- Isso evita cards “em branco” em tabelas de associação ou em linhas cujo campo de destaque veio nulo.

**Alternando entre Cards e Tabela:**
Use o botão **🃏 Cards / 📋 Tabela** que aparece no cabeçalho da tabela selecionada ou nos resultados de busca. A preferência é salva automaticamente no navegador.

- **Cards** (padrão): visualização expansível por registro, com toda a lógica de tradução de colunas, resolução de FKs (labels) e dicionário de ENUM aplicada.
- **Tabela**: visualização densa tradicional, indicada para usuários avançados e inspeção técnica. O Console SQL sempre usa a visualização em tabela, independente do toggle.

---

## 🧹 Ocultando colunas vazias automaticamente

Por padrão, o visualizador **remove automaticamente colunas que só têm valores NULL ou vazios** no contexto exibido (página atual ou resultado de busca). Isso torna a interface muito mais limpa, especialmente em buscas ou tabelas com muitos campos opcionais.

**Escopo da ocultação:** os campos são avaliados por registro individualmente — se um campo específico de um registro é nulo, ele não aparece na visualização expandida daquele card. Isso garante que a ocultação funciona de forma útil na prática, sem exigir varredura de toda a tabela.

**Fallback de segurança:** se todos os campos textuais relevantes estiverem vazios,
o sistema passa a mostrar um identificador genérico (`Registro #123`) em vez de
renderizar um card totalmente vazio.

**Exemplo:** Se você busca por "Sila do Brasil", o sistema vai:
- ✅ Mostrar todos os campos com dados relevantes para cada registro encontrado
- ❌ Ocultar automaticamente os campos que estão vazios naquele registro específico

---

## ⚙️ Modo Avançado: comportamento ao reiniciar o servidor

**Decisão de design:** o Modo Avançado sempre começa **desligado** a cada carregamento da página, independente de qualquer preferência salva anteriormente no navegador.

Isso garante comportamento consistente após reinicialização do servidor ou ao abrir uma nova aba: a interface sempre inicia no modo simples, voltado ao usuário não técnico.

**Motivação:** o Modo Avançado exibe nomes técnicos de tabelas/colunas, o Console SQL e recursos de filtro/estatísticas que podem confundir usuários não técnicos. Fazer com que ele sempre inicie desligado evita que um usuário acidentalmente deixe o modo ativado para o próximo usuário em um ambiente compartilhado.

Se você quiser usar o Modo Avançado, basta clicar no botão **⚙️ Modo Avançado** no cabeçalho. Ele permanece ativo enquanto a aba estiver aberta, mas não persiste entre recarregamentos.

---

## 🌐 Compartilhando com colegas da rede (Acesso remoto)

Por padrão, o programa só funciona no seu computador (`127.0.0.1`). Para permitir que outros computadores da rede acessem:

### ✅ Passo 1 — Configurar o servidor para aceitar conexões remotas

O programa **já vem pronto** para aceitar conexões remotas. Não precisa fazer nada!

### ✅ Passo 2 — Liberar a porta no Firewall do Windows

1. Abra o **PowerShell como Administrador** (clique direito em PowerShell → "Executar como administrador")
2. Cole este comando:

```powershell
New-NetFirewallRule -DisplayName "Visualizador SaidJur" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

## ⚡ Dicas para importação mais rápida (opcional)

Antes de importar, você pode otimizar o MySQL editando o arquivo `my.ini`
(geralmente em `C:\ProgramData\MySQL\MySQL Server 8.0\`):

```ini
[mysqld]
innodb_buffer_pool_size = 4G
innodb_log_file_size = 1G
innodb_flush_log_at_trx_commit = 2
unique_checks = 0
foreign_key_checks = 0
```

Reinicie o MySQL após salvar. Essas configurações podem **reduzir o tempo de
importação pela metade** em arquivos grandes.

---

## ❓ Perguntas frequentes

**Vai travar meu computador?**
Não. O programa lê os dados aos poucos (nunca mais de 500 registros por vez),
então não sobrecarrega a memória do computador.

**Quanto tempo demora a importação?**
Entre 2 e 12 horas, dependendo do tamanho do arquivo e do seu computador.
Um arquivo de 50 GB pode levar de 3 a 6 horas num PC moderno.

**Posso fechar a janela durante a importação?**
Não. Se fechar, a importação será interrompida e você terá que começar do zero.
Mantenha a janela aberta e minimize-a se precisar usar o computador.

**Posso usar o visualizador enquanto importa?**
Sim, mas o computador vai ficar mais lento. Recomendamos aguardar a importação
concluir antes de usar o visualizador.

**O programa acessa a internet?**
Não. Tudo roda localmente no seu computador. As únicas conexões externas são
para carregar o visual da interface (Tailwind CSS e Alpine.js via CDN na primeira abertura).

**Por que algumas colunas mostram nome e outras só o número?**
Colunas que referenciam outras tabelas (chaves estrangeiras) mostram automaticamente o nome
correspondente no formato `Nome (ID)` — por exemplo, `Rio de Janeiro (3665)` em vez de apenas `3665`.
Isso funciona quando a tabela referenciada possui uma coluna de nome reconhecível (`name`, `nome`,
`descricao`, etc.). Quando não há coluna de nome na tabela referenciada, ou quando a FK não é
detectada, o ID puro é exibido. Você pode alternar entre "nomes" e "IDs puros" clicando no botão
**🏷️ Mostrar IDs / Mostrar nomes** no topo da tabela.

---

## 🔧 Problemas comuns

### ❌ `'mysql' não é reconhecido como um comando interno`
O MySQL não está no PATH do Windows.

**Solução:**
1. Abra "Editar variáveis de ambiente do sistema" (pesquise no menu Iniciar)
2. Clique em "Variáveis de Ambiente..."
3. Em "Variáveis do sistema", selecione "Path" e clique em "Editar"
4. Clique em "Novo" e adicione: `C:\Program Files\MySQL\MySQL Server 8.0\bin`
5. Clique OK em todas as janelas e feche o terminal

### ❌ `Acesso negado` ou `Access denied`
A senha do MySQL está incorreta.

**Solução:** Abra `config.yaml` e verifique se a senha está correta no campo `senha:`.

### ❌ `Porta 8000 em uso`
Outro programa já está usando a porta 8000.

**Solução:** Edite `config.yaml` e mude `porta: 8000` para outro número (ex: `8080`).

### ❌ `Não foi possível conectar ao banco de dados`
O MySQL não está rodando.

**Solução:** Abra o "MySQL Workbench" ou os "Serviços do Windows" e verifique se
o serviço "MySQL80" está iniciado.

---

## 📁 Estrutura dos arquivos

```
├── instalar.bat        ← Execute primeiro
├── importar.bat        ← Para importar o arquivo .sql
├── iniciar.bat         ← Para abrir o visualizador
├── config.yaml         ← Suas configurações (criado pelo instalar.bat)
├── dados/              ← Coloque aqui o arquivo .sql
└── logs/               ← Registros de tudo que aconteceu
```

---

*Feito com ❤️ para facilitar o acesso aos dados do SaidJur.*
