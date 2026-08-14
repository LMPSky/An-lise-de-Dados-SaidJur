"""CLI para investigar nomes de coluna usando introspecção do schema."""

from __future__ import annotations

import argparse

from src.investigacao_colunas import (
    ARQUIVO_RELATORIO_COLUNAS_PADRAO,
    executar_investigacao_colunas,
)



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Investiga nomes de coluna e sugere traduções com base no schema."
    )
    parser.add_argument(
        "--tabela",
        help="Investiga todas as colunas da tabela informada.",
    )
    parser.add_argument(
        "--colunas",
        nargs="+",
        metavar="TABELA.COLUNA",
        default=None,
        help="Modo direcionado: investiga apenas as colunas especificadas.",
    )
    parser.add_argument(
        "--saida",
        default=ARQUIVO_RELATORIO_COLUNAS_PADRAO,
        help="Arquivo YAML de saída da investigação.",
    )
    return parser



def main() -> None:
    args = _parser().parse_args()

    if args.colunas:
        print("🔎 Iniciando investigação direcionada de nomes de coluna...")
        print(f"📌 Colunas: {', '.join(args.colunas)}")
    elif args.tabela:
        print("🔎 Iniciando investigação de nomes de coluna por tabela...")
        print(f"🗂️  Tabela: {args.tabela}")
    else:
        print("🔎 Iniciando investigação de nomes de coluna...")
    print("ℹ️  Modo somente leitura.")

    relatorio = executar_investigacao_colunas(
        tabela=args.tabela,
        colunas_diretas=args.colunas,
        caminho_saida=args.saida,
    )

    resumo = relatorio["resumo"]
    print("\n✅ Investigação concluída")
    print(f"🏷️  Colunas investigadas: {resumo['total_investigadas']}")
    print(f"🎯 Alta confiança: {resumo['alta_confianca']}")
    print(f"🟡 Pista parcial: {resumo['pista_parcial']}")
    print(f"❓ Sem pista: {resumo['sem_pista']}")
    print(f"✅ Já traduzidas manualmente: {resumo['traduzidas_manual']}")
    print(f"📝 Relatório: {args.saida}")


if __name__ == "__main__":
    main()
