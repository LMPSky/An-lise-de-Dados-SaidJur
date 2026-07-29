"""
Gera arquivo YAML pronto para tradução.
Versão simplificada - sem JSON.
"""

import sys
from pathlib import Path
import pymysql
import yaml
from decimal import Decimal

DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Acd9854Yui2026!"
DB_NAME = "saidjur"


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
    """Analisa coluna e retorna amostras."""
    
    cursor = conn.cursor()
    
    try:
        # Pegar estatísticas
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT `{coluna}`) as distintos
            FROM `{tabela}`
            WHERE `{coluna}` IS NOT NULL
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if not result or result[0] == 0:
            return None
        
        distintos = int(result[0])
        
        # Pegar amostras (DISTINCT)
        cursor.execute(f"""
            SELECT DISTINCT `{coluna}`
            FROM `{tabela}`
            WHERE `{coluna}` IS NOT NULL
            LIMIT 50
        """)
        
        amostras = []
        for row in cursor.fetchall():
            valor = row[0]
            # Converter para string, ignorar tipos complexos
            if valor is not None:
                try:
                    amostras.append(str(valor).strip())
                except:
                    pass
        
        return amostras if amostras else None
    
    except Exception as e:
        return None
    
    finally:
        cursor.close()


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


def gerar_dicionario():
    """Gera dicionário YAML."""
    
    print("🔍 Gerando dicionário de traduções...")
    print("="*80 + "\n")
    
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
        print(f"📊 Analisando {len(tabelas)} tabelas...\n")
        
        dicionarios = {}
        total_colunas = 0
        
        for idx_tab, tabela in enumerate(tabelas, 1):
            print(f"[{idx_tab}/{len(tabelas)}] {tabela}...", end=" ", flush=True)
            
            # Listar colunas
            cursor.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (DB_NAME, tabela))
            
            colunas = cursor.fetchall()
            tabela_dict = {}
            colunas_ok = 0
            
            for col_name, col_type, data_type in colunas:
                # Pular não traduzíveis
                if eh_nao_traduzivel(col_name, data_type):
                    continue
                
                # Analisar
                amostras = analisar_coluna(conn, tabela, col_name, data_type)
                
                if amostras and len(amostras) > 0:
                    # Criar entrada no dicionário
                    col_dict = {}
                    for amostra in amostras:
                        if amostra:  # Ignorar vazios
                            col_dict[amostra] = f"[{amostra}]"  # Placeholder
                    
                    if col_dict:
                        tabela_dict[col_name] = col_dict
                        colunas_ok += 1
                        total_colunas += 1
            
            if tabela_dict:
                dicionarios[tabela] = tabela_dict
            
            print(f"✅ ({colunas_ok} colunas)")
        
        conn.close()
        
        # Salvar YAML
        arquivo_yaml = Path(__file__).parent / "dicionarios_completo_traduzir.yaml"
        
        with open(arquivo_yaml, "w", encoding="utf-8") as f:
            yaml.dump(dicionarios, f, allow_unicode=True, default_flow_style=False, sort_keys=True)
        
        # Relatório
        print(f"\n{'='*80}")
        print(f"✅ DICIONÁRIO GERADO COM SUCESSO!")
        print(f"{'='*80}")
        print(f"📁 Arquivo: {arquivo_yaml}")
        print(f"📊 Tabelas: {len(dicionarios)}")
        print(f"📋 Total de colunas: {total_colunas}")
        print(f"\n💡 Próximo passo:")
        print(f"   1. Renomear o arquivo para dicionario.yaml")
        print(f"   2. Executar: python traduzir_dicionario_windows.py")
        print(f"\n🚀 Isso vai traduzir TODAS as {total_colunas} colunas!")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    gerar_dicionario()