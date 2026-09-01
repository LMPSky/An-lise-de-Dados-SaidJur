import os
import re
from pathlib import Path

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================

PROJECT_DIR = "./"

# Tamanho máximo de arquivo para analisar (em Bytes) -> 2 Megabytes
MAX_FILE_SIZE = 2 * 1024 * 1024 

IGNORED_DIRS = {
    ".git", "node_modules", "vendor", "storage", "dist", "build",
    ".idea", ".vscode", "__pycache__", "tmp", "logs", "public/uploads"
}

# Apenas arquivos de código-fonte leve
ALLOWED_EXTENSIONS = {
    ".php", ".js", ".ts", ".vue", ".json", ".py", ".html", 
    ".blade.php", ".rb", ".cs", ".java", ".phtml", ".tpl"
}

TARGETS = {
    "finishtype": ["pje", "adm", "n", "f"],
    "link_type": ["t", "s"],
    "finalpayment_type": ["1", "3"],
    "prazophase": ["2", "3", "4", "f"],
    "pzphase": ["1", "2", "3", "4"],
    "hearingtype": ["7", "8", "9", "10", "12", "13", "14", "15", "17", "18", "19", "20", "21", "22", "23"],
    "hearingstatus": ["0", "1"]
}

# ==============================================================================
# EXECUÇÃO DO SCANNER
# ==============================================================================

def scan_project(root_dir):
    results = {key: [] for key in TARGETS.keys()}
    files_scanned = 0

    print(f"🔍 Iniciando busca em: {os.path.abspath(root_dir)}...\n", flush=True)

    for root, dirs, files in os.walk(root_dir):
        # Ignora pastas pesadas
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        # Mostra a pasta atual para você acompanhar o progresso em tempo real
        print(f"📁 Lendo pasta: {root}", end="\r", flush=True)

        for file in files:
            file_path = Path(root) / file
            
            # Filtra por extensão
            if not any(file.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                continue

            try:
                # IGNORA arquivos maiores que 2MB (Evita travar em logs/dumps)
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    continue

                files_scanned += 1

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        line_clean = line.strip()
                        if not line_clean:
                            continue

                        for term in TARGETS.keys():
                            if re.search(r'\b' + re.escape(term) + r'\b', line_clean, re.IGNORECASE):
                                results[term].append({
                                    "file": str(file_path),
                                    "line": line_num,
                                    "content": line_clean[:120]
                                })
            except Exception:
                pass

    print(f"\n\n✅ Escaneamento concluído! {files_scanned} arquivos leves analisados.\n", flush=True)
    return results

def print_report(results):
    print("=" * 80)
    print(" RELATÓRIO DE OCORRÊNCIAS ENCONTRADAS NO CÓDIGO ")
    print("=" * 80)

    total_found = 0
    for term, matches in results.items():
        print(f"\n📌 CHAVE: [{term}] - {len(matches)} ocorrências encontradas")
        print("-" * 80)

        if not matches:
            print("   (Nenhuma linha diretamente referenciando este termo)")
            continue

        total_found += len(matches)
        for m in matches[:15]:
            print(f"  📄 {m['file']}:{m['line']}")
            print(f"     💬 {m['content']}\n")

        if len(matches) > 15:
            print(f"   ... e mais {len(matches) - 15} ocorrências omitidas.")

    print("\n" + "=" * 80)
    print(f"Total de referências mapeadas: {total_found}")
    print("=" * 80)

if __name__ == "__main__":
    results = scan_project(PROJECT_DIR)
    print_report(results)