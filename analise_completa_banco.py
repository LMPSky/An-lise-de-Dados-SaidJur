"""
Análise COMPLETA do banco para encontrar TODAS as possibilidades de tradução.
VERSÃO 2 - Corrigido o erro de Decimal JSON
"""

import sys
from pathlib import Path
from collections import Counter
import pymysql
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time
from decimal import Decimal

DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Acd9854Yui2026!"
DB_NAME = "saidjur"


class DecimalEncoder(json.JSONEncoder):
    """Encoder customizado para Decimal."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def conectar():
    """Conecta ao banco."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )


def analisar_coluna(conn, tabela, coluna, tipo_dado):
    """Analisa se uma coluna é traduzível."""
    
    cursor = conn.cursor()
    
    try:
        # Pegar estatísticas
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT `{coluna}`) as distintos,
                COUNT(*) as total,
                ROUND(100.0 * COUNT(DISTINCT `{coluna}`) / COUNT(*), 2) as percentual,
                MIN(LENGTH(CAST(`{coluna}` AS CHAR))) as min_len,
                MAX(LENGTH(CAST(`{coluna}` AS CHAR))) as max_len,
                AVG(LENGTH(CAST(`{coluna}` AS CHAR))) as avg_len
            FROM `{tabela}`
            WHERE `{coluna}` IS NOT NULL
            LIMIT 1
        """)
        
        stats = cursor.fetchone()
        
        if not stats or stats[0] == 0:
            return None
        
        distintos, total, percentual, min_len, max_len, avg_len = stats
        
        # Converter Decimal para float
        distintos = int(distintos) if distintos else 0
        total = int(total) if total else 0
        percentual = float(percentual) if percentual else 0.0
        min_len = int(min_len) if min_len else 0
        max_len = int(max_len) if max_len else 0
        avg_len = float(avg_len) if avg_len else 0.0
        
        # Pegar amostras
        cursor.execute(f"""
            SELECT DISTINCT `{coluna}`
            FROM `{tabela}`
            WHERE `{coluna}` IS NOT NULL
            LIMIT 10
        """)
        
        amostras = [row[0] for row in cursor.fetchall()]
        
        # Calcular score de traduzibilidade
        score = calcular_score_traduzibilidade(
            tipo_dado, distintos, total, percentual, min_len, max_len, amostras
        )
        
        return {
            'tabela': tabela,
            'coluna': coluna,
            'tipo': tipo_dado,
            'distintos': distintos,
            'total': total,
            'percentual_distintos': percentual,
            'tamanho_min': min_len,
            'tamanho_max': max_len,
            'tamanho_medio': round(avg_len, 2),
            'amostras': amostras[:5],
            'score_traduzibilidade': score,
            'recomendacao': gerar_recomendacao(score, tipo_dado, distintos, min_len, max_len)
        }
    
    except Exception as e:
        return None
    
    finally:
        cursor.close()


def calcular_score_traduzibilidade(tipo_dado, distintos, total, percentual, min_len, max_len, amostras):
    """Calcula score de 0-100 de traduzibilidade."""
    
    score = 0
    
    # 1. Tipo de dado
    if tipo_dado in ('enum', 'set'):
        score += 50
    elif tipo_dado in ('varchar', 'char'):
        score += 20
    elif tipo_dado in ('int', 'bigint', 'tinyint'):
        score += 15
    
    # 2. Quantidade de distintos
    if distintos < 10:
        score += 40
    elif distintos < 50:
        score += 25
    elif distintos < 100:
        score += 15
    elif distintos < 500:
        score += 8
    
    # 3. Tamanho dos valores
    if max_len <= 20:
        score += 15
    elif max_len <= 50:
        score += 10
    elif max_len <= 100:
        score += 5
    
    # 4. Padrão de valores (parece código?)
    if eh_codigo(amostras):
        score += 15
    
    # 5. Percentual de repetição
    if percentual < 1:
        score += 10
    
    return min(100, score)


def eh_codigo(amostras):
    """Verifica se valores parecem ser códigos."""
    
    if not amostras:
        return False
    
    caracteristicas = 0
    
    for amostra in amostras:
        s = str(amostra).strip()
        
        if len(s) <= 10:
            caracteristicas += 1
        if any(c.isdigit() for c in s):
            caracteristicas += 1
        if '_' in s or '-' in s:
            caracteristicas += 1
        if '  ' not in s:
            caracteristicas += 1
        if s and s[0].isalpha():
            caracteristicas += 1
    
    return caracteristicas >= 3


def gerar_recomendacao(score, tipo_dado, distintos, min_len, max_len):
    """Gera recomendação."""
    
    if score >= 80:
        return "🔴 MUST TRANSLATE"
    elif score >= 60:
        return "🟠 SHOULD TRANSLATE"
    elif score >= 40:
        return "🟡 MAYBE TRANSLATE"
    else:
        return "🟢 SKIP"


def processar_banco_completo():
    """Analisa TODO o banco."""
    
    print("🔍 ANÁLISE COMPLETA DO BANCO DE DADOS")
    print("   Encontrando TODAS as possibilidades de tradução...\n")
    print("="*80)
    
    conn = conectar()
    cursor = conn.cursor()
    
    try:
        # Listar tabelas
        cursor.execute("""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """, (DB_NAME,))
        
        tabelas = [row[0] for row in cursor.fetchall()]
        print(f"📊 Encontradas {len(tabelas)} tabelas\n")
        
        resultados = []
        
        for idx_tab, tabela in enumerate(tabelas, 1):
            print(f"[{idx_tab}/{len(tabelas)}] {tabela}...", end="", flush=True)
            
            cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (DB_NAME, tabela))
            
            colunas = cursor.fetchall()
            colunas_ok = 0
            
            for col_name, col_type, data_type in colunas:
                if eh_nao_traduzivel(col_name, data_type):
                    continue
                
                resultado = analisar_coluna(conn, tabela, col_name, data_type)
                
                if resultado and resultado['score_traduzibilidade'] >= 30:
                    resultados.append(resultado)
                    colunas_ok += 1
            
            print(f" ✅ ({colunas_ok} candidatas)")
        
        conn.close()
        
        # Ordenar por score
        resultados.sort(key=lambda x: x['score_traduzibilidade'], reverse=True)
        
        # Exibir e salvar
        exibir_resultados(resultados)
        salvar_relatorio(resultados)
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


def eh_nao_traduzivel(col_name, data_type):
    """Retorna True se não é traduzível."""
    
    nao_traduzivel = {
        'id', 'ids', 'pk', 'fk', 'user_id', 'lawsuit_id',
        'timestamp', 'created_at', 'updated_at', 'deleted_at',
        'email', 'password', 'hash', 'token',
    }
    
    col_lower = col_name.lower()
    
    for padrao in nao_traduzivel:
        if padrao in col_lower:
            return True
    
    if data_type in ('longtext', 'text', 'mediumtext', 'blob', 'longblob', 'mediumblob'):
        return True
    
    return False


def exibir_resultados(resultados):
    """Exibe resultados."""
    
    print("\n" + "="*80)
    print("🔴 MUST TRANSLATE (Score >= 80)")
    print("="*80)
    
    must = [r for r in resultados if r['score_traduzibilidade'] >= 80]
    print(f"Total: {len(must)} colunas\n")
    
    for r in must[:30]:
        print(f"  {r['tabela']}.{r['coluna']}")
        print(f"    Score: {r['score_traduzibilidade']}/100 | Distintos: {r['distintos']}")
        print(f"    Amostras: {r['amostras']}\n")
    
    print("\n" + "="*80)
    print("🟠 SHOULD TRANSLATE (Score 60-79)")
    print("="*80)
    print(f"Total: {len([r for r in resultados if 60 <= r['score_traduzibilidade'] < 80])} colunas\n")
    
    print("\n" + "="*80)
    print("🟡 MAYBE TRANSLATE (Score 40-59)")
    print("="*80)
    print(f"Total: {len([r for r in resultados if 40 <= r['score_traduzibilidade'] < 60])} colunas\n")
    
    print("\n" + "="*80)
    print(f"📊 RESUMO TOTAL: {len(resultados)} colunas analisadas")
    print("="*80)


def salvar_relatorio(resultados):
    """Salva em JSON e YAML."""
    
    # JSON
    arquivo_json = Path(__file__).parent / "analise_banco_completo.json"
    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
    print(f"\n✅ JSON salvo: {arquivo_json}")
    
    # YAML para tradução
    arquivo_yaml = Path(__file__).parent / "dicionarios_a_traduzir_completo.yaml"
    
    import yaml
    
    dicionarios = {}
    
    for r in resultados:
        if r['score_traduzibilidade'] >= 60:
            tabela = r['tabela']
            coluna = r['coluna']
            
            if tabela not in dicionarios:
                dicionarios[tabela] = {}
            
            # Criar entrada com amostras
            dicionarios[tabela][coluna] = {
                str(amostra): f"[{amostra}]" for amostra in r['amostras'] if amostra
            }
    
    with open(arquivo_yaml, "w", encoding="utf-8") as f:
        yaml.dump(dicionarios, f, allow_unicode=True, default_flow_style=False)
    
    print(f"✅ YAML salvo: {arquivo_yaml}")
    print(f"\n💡 Próximo comando:")
    print(f"   python traduzir_dicionario_windows.py")


if __name__ == "__main__":
    processar_banco_completo()