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
        help="Quantidade máxima de linhas de exemplo por pendência (mínimo efetivo: 2)",
    )
    parser.add_argument(
        "--colunas",
        nargs="+",
        metavar="TABELA.COLUNA[:VALOR]",
        default=None,
        help=(
            "Modo direcionado: investiga apenas as colunas/valores especificados, "
            "ignorando o relatório de auditoria. "
            "Formato: 'tabela.coluna' ou 'tabela.coluna:valor'. "
            "Exemplo: --colunas hearingcontrol.hearingtype:11 pedidos2lawsuit.status:6"
        ),
    )
    return parser



def main() -> None:
    args = _parser().parse_args()

    if args.colunas:
        print("🔎 Iniciando investigação direcionada das colunas especificadas...")
        print(f"📌 Colunas: {', '.join(args.colunas)}")
    else:
        print("🔎 Iniciando investigação assistida de pendências...")
    print("ℹ️  Modo somente leitura (queries SELECT).")

    relatorio = executar_investigacao(
        caminho_relatorio_auditoria=args.relatorio_auditoria,
        caminho_saida=args.saida,
        limite_linhas=max(2, args.limite_linhas),
        colunas_diretas=args.colunas,
    )

    resumo = relatorio["resumo"]
    print("\n✅ Investigação concluída")
    print(f"🧩 Pendências investigadas: {resumo['total_pendencias']}")
    print(f"🎯 Sugestões de alta confiança: {resumo['alta_confianca']}")
    print(f"🟡 Sugestões com pista única (baixa confiança): {resumo['pista_unica']}")
    print(f"❓ Sem pista clara: {resumo['sem_pista_encontrada']}")
    print(f"📭 Sem registros: {resumo['sem_registros']}")
    print(f"⚠️  Erros: {resumo['erros']}")
    print(f"📝 Relatório: {args.saida}")


if __name__ == "__main__":
    main()
