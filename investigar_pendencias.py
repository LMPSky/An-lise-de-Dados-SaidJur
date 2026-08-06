"""Investiga pendências de tradução de códigos/ENUM usando dados reais do banco."""

from __future__ import annotations

import argparse

from src.investigacao_pendencias import (
    ARQUIVO_AUDITORIA_PADRAO,
    ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO,
    executar_investigacao,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Investiga pendências de ENUM/código do relatório de auditoria "
            "e gera um relatório com contexto e sugestões."
        )
    )
    parser.add_argument(
        "--relatorio-auditoria",
        default=ARQUIVO_AUDITORIA_PADRAO,
        help="Arquivo YAML de auditoria com pendências (padrão: relatorio_auditoria_traducoes.yaml)",
    )
    parser.add_argument(
        "--saida",
        default=ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO,
        help="Arquivo YAML de saída da investigação",
    )
    parser.add_argument(
        "--limite-linhas",
        type=int,
        default=5,
        help="Quantidade máxima de linhas de exemplo por pendência",
    )
    return parser



def main() -> None:
    args = _parser().parse_args()

    print("🔎 Iniciando investigação assistida de pendências...")
    print("ℹ️  Modo somente leitura (queries SELECT).")

    relatorio = executar_investigacao(
        caminho_relatorio_auditoria=args.relatorio_auditoria,
        caminho_saida=args.saida,
        limite_linhas=max(1, args.limite_linhas),
    )

    resumo = relatorio["resumo"]
    print("\n✅ Investigação concluída")
    print(f"🧩 Pendências investigadas: {resumo['total_pendencias']}")
    print(f"🎯 Sugestões de alta confiança: {resumo['alta_confianca']}")
    print(f"❓ Sem pista clara: {resumo['sem_pista_encontrada']}")
    print(f"📭 Sem registros: {resumo['sem_registros']}")
    print(f"⚠️  Erros: {resumo['erros']}")
    print(f"📝 Relatório: {args.saida}")


if __name__ == "__main__":
    main()
