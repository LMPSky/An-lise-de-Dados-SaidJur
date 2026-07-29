"""
Script para traduzir automaticamente os valores do dicionário.
VERSÃO WINDOWS - sem signal.alarm (não suportado no Windows)
"""

import sys
from pathlib import Path
from typing import Any, Optional
import yaml
import time
import importlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Tentar importar tradutor
try:
    import deep_translator
    from deep_translator import GoogleTranslator
    TRADUTOR_DISPONIVEL = True
except ImportError:
    TRADUTOR_DISPONIVEL = False
    print("⚠️  deep-translator não instalado. Instalando...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "deep-translator", "-q"])
    print("✅ Instalado!\n")
    
    import deep_translator
    from deep_translator import GoogleTranslator
    TRADUTOR_DISPONIVEL = True


# Mapeamentos MANUAIS
TRADUCOES_MANUAIS = {
    # Códigos contábeis
    "CONT": "Conta",
    "ativo": "Ativo",
    "desp": "Despesa",
    "pass": "Passivo",
    "pl": "Patrimônio Líquido",
    "rec": "Receita",
    "a": "Ativo",
    "d": "Despesa",
    "p": "Passivo",
    "r": "Receita",
    
    # Abreviaturas jurídicas
    "j": "Judicial",
    "n": "Não",
    "y": "Sim",
    "na": "Não Aplicável",
    "o": "Outro",
    
    # Status
    "s": "Sim",
    "all": "Todos",
    "b": "Dia útil",
    "h": "Feriado",
    
    # Tipos de atividade
    "com": "Comercial",
    "con": "Consultoria",
    
    # Publicações
    "m": "Manifestação",
    "api": "API",
    "i": "Intimação",
    "pe": "Perícia",
    "e": "Existe",
    "p": "Publicação",
    "x": "XML",
}

COLUNAS_JA_TRADUZIDAS = {
    "name", "description", "descricao", "natureza",
    "nature_desc", "type_desc", "status_desc",
}

CACHE_TRADUCOES = {}
INTERVALO_TRADUCAO = 0.1
TIMEOUT_TRADUCAO = 10  # segundos


def traduzir_com_timeout(texto: str) -> str:
    """Traduz texto com timeout usando thread."""
    
    if not texto or len(texto.strip()) < 2:
        return texto
    
    # Verificar cache
    if texto in CACHE_TRADUCOES:
        return CACHE_TRADUCOES[texto]
    
    # Verificar mapeamento manual
    if texto in TRADUCOES_MANUAIS:
        resultado = TRADUCOES_MANUAIS[texto]
        CACHE_TRADUCOES[texto] = resultado
        return resultado
    
    # Função para traduzir em thread
    def fazer_traducao():
        try:
            time.sleep(INTERVALO_TRADUCAO)
            from deep_translator import GoogleTranslator
            
            tradutor = GoogleTranslator(source='auto', target='pt')
            resultado = tradutor.translate(text=texto)
            
            if resultado and resultado.lower() != texto.lower():
                return resultado
            else:
                return texto
        except Exception:
            return texto
    
    # Usar thread com timeout
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fazer_traducao)
            resultado = future.result(timeout=TIMEOUT_TRADUCAO)
            CACHE_TRADUCOES[texto] = resultado
            return resultado
    except FuturesTimeoutError:
        print(f"    ⏱️ TIMEOUT ao traduzir '{texto}' (mantendo original)")
        CACHE_TRADUCOES[texto] = texto
        return texto
    except Exception as e:
        print(f"    ❌ ERRO: {e}")
        CACHE_TRADUCOES[texto] = texto
        return texto


def eh_codigo_curto(chave: str) -> bool:
    """Verifica se é um código curto que não precisa tradução."""
    chave_str = str(chave)
    
    if len(chave_str) <= 2 and (chave_str.isdigit() or len(chave_str) == 1):
        return True
    
    if chave_str in {"0", "1", "2", "3", "4", "5"}:
        return True
    
    return False


def processar_coluna(nome_coluna: str, valores: dict) -> dict:
    """Processa uma coluna traduzindo seus valores."""
    
    if any(desc in nome_coluna.lower() for desc in COLUNAS_JA_TRADUZIDAS):
        return valores
    
    valores_traduzidos = {}
    total = len(valores)
    
    for idx, (chave, valor) in enumerate(valores.items(), 1):
        valor_str = str(valor).strip("[]")
        
        # Se já tem tradução (não está em [...]format)
        if not (valor_str == str(chave) or valor == f"[{chave}]"):
            valores_traduzidos[chave] = valor
            continue
        
        # Pular códigos muito curtos
        if eh_codigo_curto(chave):
            valores_traduzidos[chave] = valor_str
            continue
        
        # Pular se chave é muito longa (provavelmente descrição)
        if len(str(chave)) > 100:
            valores_traduzidos[chave] = valor_str
            continue
        
        # Traduzir
        print(f"    [{idx}/{total}] '{chave}' → ", end="", flush=True)
        
        try:
            traducao = traduzir_com_timeout(str(chave))
            valores_traduzidos[chave] = traducao
            print(f"'{traducao}'")
        except Exception as e:
            print(f"❌ ERRO: {e}")
            valores_traduzidos[chave] = valor_str
    
    return valores_traduzidos


def encontrar_arquivo_entrada():
    """Procura pelo arquivo de entrada em várias possibilidades."""
    pasta = Path(__file__).parent
    
    opcoes = [
        "dicionarios_completo_limpo.yaml",
        "dicionarios_completo_limpo.yml",
        "dicionario.yaml",
        "dicionario.yml",
        "dicionarios_completo.yaml",
        "dicionarios_completo.yml",
        "dicionarios.yaml",
        "dicionarios.yml",
    ]
    
    for arquivo in opcoes:
        caminho = pasta / arquivo
        if caminho.exists():
            return caminho
    
    return None


def traduzir_dicionario():
    """Traduz o dicionário completo."""
    
    print("🌐 Tradução automática de dicionário (WINDOWS)")
    print("⏱️  Com timeout de 10 segundos por palavra\n")
    
    # Encontrar arquivo
    arquivo_entrada = encontrar_arquivo_entrada()
    
    if not arquivo_entrada:
        print("❌ Arquivo não encontrado!")
        print("\n   Procurei por:")
        print("   - dicionarios_completo_limpo.yaml")
        print("   - dicionario.yaml")
        print("   - dicionarios_completo.yaml")
        print("   - dicionarios.yaml")
        print("\n   Execute primeiro:")
        print("   1. python limpar_dicionario.py")
        print("   2. OU copie o arquivo para um dos nomes acima")
        return
    
    arquivo_saida = Path(__file__).parent / "dicionarios.yaml"
    
    print(f"📂 Entrada: {arquivo_entrada.name}")
    print(f"📁 Saída: {arquivo_saida.name}\n")
    
    # Carregar
    try:
        with open(arquivo_entrada, "r", encoding="utf-8") as f:
            dicionario = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"❌ Erro ao carregar: {e}")
        return
    
    # Traduzir
    dicionario_traduzido = {}
    total_tabelas = len(dicionario)
    total_colunas = sum(len(v) for v in dicionario.values() if isinstance(v, dict))
    colunas_processadas = 0
    
    print(f"📊 Total: {total_tabelas} tabelas, {total_colunas} colunas\n")
    print("⏳ Isso pode levar alguns minutos...\n")
    
    for idx, (tabela, colunas) in enumerate(sorted(dicionario.items()), 1):
        print(f"[{idx}/{total_tabelas}] {tabela}", flush=True)
        
        if not isinstance(colunas, dict):
            print("  ⏭️  (não é dict)\n")
            continue
        
        tabela_traduzida = {}
        
        for coluna, valores in sorted(colunas.items()):
            if not isinstance(valores, dict):
                continue
            
            print(f"  📝 {coluna}:", flush=True)
            
            try:
                valores_traduzidos = processar_coluna(coluna, valores)
                tabela_traduzida[coluna] = valores_traduzidos
                colunas_processadas += 1
            except KeyboardInterrupt:
                print("\n\n⚠️  Tradução interrompida pelo usuário!")
                print("Salvando progresso...")
                break
            except Exception as e:
                print(f"  ❌ ERRO na coluna {coluna}: {e}\n")
                tabela_traduzida[coluna] = valores  # Manter original
                colunas_processadas += 1
        
        dicionario_traduzido[tabela] = tabela_traduzida
        print()
    
    # Salvar
    try:
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            yaml.dump(dicionario_traduzido, f, allow_unicode=True, sort_keys=True, default_flow_style=False)
        
        print(f"\n{'='*70}")
        print(f"✅ TRADUÇÃO CONCLUÍDA!")
        print(f"{'='*70}")
        print(f"📁 Arquivo salvo em: {arquivo_saida}")
        print(f"📊 Colunas traduzidas: {colunas_processadas}")
        print(f"💾 Cache de traduções: {len(CACHE_TRADUCOES)}")
        print(f"\n💡 Próximas ações:")
        print(f"   1. Verifique: {arquivo_saida.name}")
        print(f"   2. Edite manualmente se necessário")
        print(f"   3. Recarregue a página (Ctrl+Shift+R)")
        
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")


if __name__ == "__main__":
    if not TRADUTOR_DISPONIVEL:
        print("❌ deep-translator não disponível")
        sys.exit(1)
    
    traduzir_dicionario()