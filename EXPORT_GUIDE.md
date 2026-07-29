# 📥 Guia de Exportação de Resultados de Busca

## 🎯 Visão Geral

A funcionalidade de exportação de resultados de busca permite que você baixe dados encontrados em buscas globais em múltiplos formatos (Excel e CSV). Os dados podem ser exportados de forma consolidada (todas as tabelas) ou por tabela individual.

---

## 🚀 Como Usar

### 1️⃣ **Realizar uma Busca Global**

1. Acesse a barra de pesquisa no topo da interface
2. Digite um termo de busca (ex: "ATIVO", "publicação", "2024")
3. Clique em **"Buscar"** ou pressione Enter
4. A aplicação buscará em todas as tabelas do banco de dados

### 2️⃣ **Exportar Resultados**

Após a busca ser concluída, você verá uma seção de **"Exportar resultados:"** com as seguintes opções:

#### **📊 Opção 1: Baixar Tudo em Excel**
- Exporta TODOS os resultados encontrados em um único arquivo Excel
- Cada tabela encontrada fica em uma aba separada
- Ideal para análises consolidadas

#### **📄 Opção 2: Baixar Tudo em CSV**
- Exporta TODOS os resultados em um único arquivo CSV
- Útil para importar em ferramentas de análise ou bancos de dados
- Combina todos os resultados em um único arquivo

#### **📊/📄 Opção 3: Exportar por Tabela Individual**
- Aparece quando há mais de uma tabela nos resultados
- Permite escolher qual tabela exportar
- Disponível em ambos os formatos (Excel e CSV)
- Útil quando você quer dados de uma tabela específica

---

## 📊 Exemplos de Uso

### Exemplo 1: Exportar Todos os Resultados em Excel
```
1. Busque por: "publicação"
2. Aguarde a busca concluir
3. Clique em "Baixar Tudo (Excel)"
4. Um arquivo será baixado com todos os resultados encontrados
```

### Exemplo 2: Exportar Tabela Específica em CSV
```
1. Busque por: "2024"
2. Aguarde a busca concluir
3. Vá até a seção "Ou exportar tabela específica:"
4. Clique em "processos (CSV)" para baixar apenas a tabela de processos
```

---

## 🎨 Interface de Exportação

A interface de exportação apresenta:

- **Ícones visuais**: 📊 (Excel), 📄 (CSV)
- **Indicador de carregamento**: ⏳ mostra quando o arquivo está sendo processado
- **Resumo dos resultados**: Mostra quantas tabelas e grupos foram encontrados
- **Status em tempo real**: Desabilita botões durante o processamento

### Estados dos Botões

| Estado | Aparência | Significado |
|--------|-----------|-------------|
| ✅ Pronto | Cores vibrantes (verde/azul) | Clique para iniciar o download |
| ⏳ Processando | Cinza com ícone de espera | Aguarde o arquivo ser preparado |
| 🚫 Desabilitado | Cinza claro com opacidade | Desabilitado durante processamento |

---

## 📋 Formatos Suportados

### **Excel (.xlsx)**
- ✅ Múltiplas abas (uma por tabela)
- ✅ Formatação automática de cabeçalhos
- ✅ Colunas traduzidas para português
- ✅ Suporta até 1.048.576 linhas por aba
- ✅ Ideal para análises no Excel/Sheets

### **CSV (.csv)**
- ✅ Formato universal
- ✅ Compatível com qualquer ferramenta
- ✅ Fácil de importar em bancos de dados
- ✅ Arquivo consolidado com todas as tabelas
- ✅ Separador: vírgula (,)
- ✅ Codificação: UTF-8

---

## ⚙️ Detalhes Técnicos

### Estrutura do Arquivo Excel
```
Livro: resultados_busca_[TERMO]_[DATA].xlsx
├── Aba 1: processos
│   ├── Coluna A: id
│   ├── Coluna B: Número do Processo
│   ├── Coluna C: Status
│   └── ...
├── Aba 2: partes
│   ├── Coluna A: id
│   ├── Coluna B: Nome
│   └── ...
└── Aba 3: audiencias
    └── ...
```

### Estrutura do Arquivo CSV
```
tabela,id,Número do Processo,Status,...
processos,1234,0001234-56.78.9012.3.45,ATIVO,...
processos,1235,0001235-56.78.9012.3.45,INATIVO,...
partes,5001,João da Silva,Autor,...
...
```

---

## 🔒 Segurança e Privacidade

- ✅ Downloads ocorrem **apenas no cliente** (navegador)
- ✅ Nenhum dado é armazenado no servidor
- ✅ Sem limite de tamanho para downloads
- ✅ Sem registro de quem fez o download
- ✅ Dados respeitam permissões do usuário

---

## 🛠️ Resolução de Problemas

### Problema: "Arquivo não está sendo baixado"
**Solução:**
- Verifique se o navegador permite downloads automáticos
- Desabilite bloqueadores de pop-ups e downloads
- Tente em outro navegador

### Problema: "Excel abre vazio ou corrupto"
**Solução:**
- Tente baixar em CSV e abrir no Excel
- Atualize seu Microsoft Office
- Verifique se há espaço em disco disponível

### Problema: "A busca demora muito"
**Solução:**
- Use termos de busca mais específicos
- Tente procurar em colunas específicas (seção de filtros)
- Se a busca ficar muito lenta, clique em "Cancelar" e refine os critérios

### Problema: "Botões de exportação desabilitados"
**Solução:**
- Aguarde a busca ser concluída
- Verifique se há resultados encontrados
- Recarregue a página e tente novamente

---

## 📊 Limitações

- **Máximo de linhas**: Não há limite técnico, mas buscas muito grandes podem demorar
- **Memória do navegador**: Para conjuntos muito grandes (>50k linhas), considere exportar por tabela
- **Timeout**: Buscas muito lentas podem ser canceladas automaticamente após ~5 minutos

---

## 💡 Dicas Úteis

1. **Busca eficiente**: Use termos específicos para obter resultados mais rápidos
2. **Combinações**: Faça múltiplas buscas para comparar dados
3. **CSV para análise**: Use CSV se precisar trabalhar com SQL ou Python
4. **Excel para compartilhamento**: Use Excel para enviar para colegas
5. **Backups**: Baixe regularmente para manter cópias de dados importantes

---

## 📞 Suporte

Se encontrar problemas:
1. Verifique a seção de **Resolução de Problemas** acima
2. Verifique se o navegador está atualizado
3. Contate o administrador do sistema se o problema persistir

---

## 🔄 Rotas da API

As funcionalidades de exportação utilizam as seguintes rotas:

| Rota | Método | Descrição |
|------|--------|-----------|
| `/api/exportar/busca` | POST | Exporta resultados de busca em Excel |
| `/api/exportar/busca/csv` | POST | Exporta resultados de busca em CSV |
| `/api/exportar/busca/tabela` | POST | Exporta tabela específica em Excel |
| `/api/exportar/busca/tabela/csv` | POST | Exporta tabela específica em CSV |

---

**Última atualização:** 2026-07-29
