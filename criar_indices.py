"""
Script para criar índices na tabela publicationxml de forma segura.
"""

import pymysql
import sys

# Configuração
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Acd9854Yui2026!"
DB_NAME = "saidjur"

# Lista de índices que faltam
INDICES_FALTANDO = [
    ('idx_publicationxml_user_changed_lawsuit', 'user_changed_lawsuit'),
    ('idx_publicationxml_lawyer', 'lawyer'),
    ('idx_publicationxml_plaintiff', 'plaintiff'),
    ('idx_publicationxml_defendant', 'defendant'),
    ('idx_publicationxml_expedientfile', 'expedientfile'),
    ('idx_publicationxml_expedientprotocoldate', 'expedientprotocoldate'),
    ('idx_publicationxml_expedientfileobs', 'expedientfileobs'),
    ('idx_publicationxml_observations_userid', 'observations_userid'),
    ('idx_publicationxml_instructions', 'instructions'),
    ('idx_publicationxml_instructions_resp', 'instructions_resp'),
    ('idx_publicationxml_instructions_respfinish', 'instructions_respfinish'),
    ('idx_publicationxml_instructions_sent', 'instructions_sent'),
    ('idx_publicationxml_instructionsdate', 'instructionsdate'),
    ('idx_publicationxml_instructionsinsertdate', 'instructionsinsertdate'),
    ('idx_publicationxml_instructionsinsertdate_userid', 'instructionsinsertdate_userid'),
    ('idx_publicationxml_instructionstimestamp', 'instructionstimestamp'),
    ('idx_publicationxml_instructionstimestamp_userid', 'instructionstimestamp_userid'),
    ('idx_publicationxml_instructionsstatus', 'instructionsstatus'),
    ('idx_publicationxml_analise_prov_hearingid', 'analise_prov_hearingid'),
    ('idx_publicationxml_sentence', 'sentence'),
    ('idx_publicationxml_objecttype', 'objecttype'),
    ('idx_publicationxml_updated_at', 'updated_at'),
    ('idx_publicationxml_updated_at_userid', 'updated_at_userid'),
]

def criar_indices():
    """Cria os índices faltantes."""
    
    print("🔗 Criando índices na tabela publicationxml\n")
    print(f"📌 Conectando em: {DB_HOST}:{DB_NAME}")
    print(f"👤 Usuário: {DB_USER}\n")
    
    try:
        # Conectar ao banco
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        print("✅ Conectado!\n")
        
        # Criar cada índice
        sucesso = 0
        erro = 0
        
        for idx_name, col_name in INDICES_FALTANDO:
            print(f"🔄 Criando {idx_name}...", end=" ", flush=True)
            
            try:
                sql = f"CREATE INDEX `{idx_name}` ON `publicationxml`(`{col_name}`)"
                cursor.execute(sql)
                print("✅")
                sucesso += 1
            
            except pymysql.err.OperationalError as e:
                if "Duplicate key name" in str(e):
                    print("⏭️  (já existe)")
                else:
                    print(f"❌ ERRO: {e}")
                    erro += 1
            
            except Exception as e:
                print(f"❌ ERRO: {e}")
                erro += 1
        
        # Commit final
        conn.commit()
        cursor.close()
        conn.close()
        
        # Relatório
        print(f"\n{'='*70}")
        print(f"✅ CONCLUÍDO!")
        print(f"{'='*70}")
        print(f"✅ Índices criados: {sucesso}")
        print(f"⏭️  Índices já existentes: {len(INDICES_FALTANDO) - sucesso - erro}")
        print(f"❌ Erros: {erro}\n")
    
    except Exception as e:
        print(f"\n❌ ERRO DE CONEXÃO: {e}")
        print("\n💡 Verifique:")
        print("   1. Se MySQL está rodando")
        print("   2. Se o usuário/senha estão corretos")
        print("   3. Se o banco 'saidjur' existe")
        sys.exit(1)

if __name__ == "__main__":
    criar_indices()