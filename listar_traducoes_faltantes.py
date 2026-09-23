"""Gera, num único comando, a lista completa de itens ainda sem tradução.

Combina em um só passo o que antes exigia dois comandos separados:

1. ``investigar_pendencias.py --lote --completo`` — varredura exaustiva do
   banco inteiro (mesma lógica: descoberta via schema com elegibilidade
   ampliada + Markdown de pendências humanas + amostra inicial maior em
   tabelas colossais).
2. ``aplicar_sugestoes_investigacao.py --gerar-template-decisoes`` (sem
   filtros de status/tabela) — achata o relatório estruturado numa lista
   plana, uma linha por item, pronta para revisão manual item a item.

Diferença importante em relação ao ``--lote`` padrão: usa por padrão um
``--limite-linhas`` bem maior (30 em vez de 5). Mais linhas de exemplo por
pendência aumenta a chance das heurísticas de ``_analisar_pistas`` (pista
única com >= 2 ocorrências, ou múltiplas pistas concordando) encontrarem
confirmação suficiente — potencialmente promovendo itens hoje classificados
como ``sem_pista_encontrada``/``pista_unica`` para uma sugestão mais forte.

Como é uma varredura completa do banco de ~50GB, pode demorar muito (o
próprio ``--completo`` já é recomendado para rodar durante a noite);
aumentar ``--limite-linhas`` tende a aumentar ainda mais o tempo total, pois
mais linhas de exemplo são lidas por pendência. Recomendado deixar rodando
em segundo plano.
"""

from __future__ import annotations

import argparse

from src.investigacao_pendencias import (
    ARQUIVO_PENDENCIAS_MARKDOWN_PADRAO,
    executar_investigacao,
    gerar_template_decisoes,
    salvar_yaml,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Roda uma investigação completa (equivalente a --lote --completo) e "
            "gera, num só passo, a lista plana de todos os itens que ainda não "
            "têm tradução no dicionarios.yaml atual."
        )
    )
    parser.add_argument(
        "--limite-linhas",
        type=int,
        default=30,
        help=(
            "Quantidade máxima de linhas de exemplo por pendência (mínimo "
            "efetivo: 2; padrão: 30 — bem acima do padrão de "
            "investigar_pendencias.py, para dar mais chance às heurísticas de "
            "confirmarem sugestões com mais evidência)."
        ),
    )
    parser.add_argument(
        "--saida-relatorio",
        default="relatorio_traducoes_faltantes.yaml",
        help="Arquivo YAML de saída do relatório completo e estruturado da investigação.",
    )
    parser.add_argument(
        "--saida-lista",
        default="lista_traducoes_faltantes.yaml",
        help=(
            "Arquivo YAML de saída com a lista plana de todos os itens ainda "
            "sem tradução (mesmo formato de --gerar-template-decisoes, pronto "
            "para revisão manual item a item)."
        ),
    )
    parser.add_argument(
        "--intervalo-checkpoint",
        type=int,
        default=25,
        help=(
            "Salva um checkpoint parcial em --saida-relatorio a cada N "
            "pendências processadas (padrão: 25; use 0 para desativar)."
        ),
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    limite_linhas = max(2, args.limite_linhas)

    print("🔎 Iniciando varredura completa do banco (equivalente a --lote --completo)...")
    print(f"📏 Limite de linhas por item: {limite_linhas}")
    print("ℹ️  Modo somente leitura (queries SELECT). Isso pode demorar bastante.")

    try:
        relatorio = executar_investigacao(
            caminho_saida=args.saida_relatorio,
            limite_linhas=limite_linhas,
            caminho_pendencias_markdown=ARQUIVO_PENDENCIAS_MARKDOWN_PADRAO,
            descobrir_schema=True,
            intervalo_checkpoint=args.intervalo_checkpoint,
            modo_completo=True,
        )
    except KeyboardInterrupt:
        print("\n⏹️  Investigação interrompida pelo usuário (Ctrl+C).")
        if args.intervalo_checkpoint > 0:
            print(
                f"💾 O progresso até o último checkpoint foi salvo em: {args.saida_relatorio}\n"
                "   Rode o script de novo para recomeçar do zero, ou revise o "
                "relatório parcial ('em_andamento: true') manualmente."
            )
        else:
            print("⚠️  Checkpoint incremental estava desativado (--intervalo-checkpoint 0); nada foi salvo.")
        return

    resumo = relatorio["resumo"]
    print("\n✅ Investigação concluída")
    print(f"🧩 Total de itens ainda sem tradução: {resumo['total_pendencias']}")
    print(f"🎯 Alta confiança: {resumo['alta_confianca']}")
    print(f"🟡 Pista única (baixa confiança): {resumo['pista_unica']}")
    print(f"❓ Sem pista clara: {resumo['sem_pista_encontrada']}")
    print(f"📭 Sem registros: {resumo['sem_registros']}")
    print(f"⚠️  Erros: {resumo['erros']}")

    template = gerar_template_decisoes(relatorio)
    itens = sorted(
        template["decisoes"],
        key=lambda item: (
            str(item.get("tabela") or ""),
            str(item.get("coluna") or ""),
            str(item.get("valor") or ""),
        ),
    )
    salvar_yaml({"decisoes": itens}, args.saida_lista)

    print(f"\n📝 Relatório completo (estruturado): {args.saida_relatorio}")
    print(f"📋 Lista plana de itens ainda sem tradução ({len(itens)} itens): {args.saida_lista}")


if __name__ == "__main__":
    main()
