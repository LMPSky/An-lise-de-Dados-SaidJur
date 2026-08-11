"""Aplica traduções aprovadas do relatório de investigação em dicionarios.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.investigacao_pendencias import (
    ARQUIVO_DICIONARIOS_PADRAO,
    ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO,
    aplicar_decisoes_em_dicionario,
    carregar_yaml,
    gerar_template_decisoes,
    salvar_yaml,
)



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Revisa/aplica sugestões do relatório de investigação para atualizar o dicionarios.yaml."
        )
    )
    parser.add_argument(
        "--relatorio-investigacao",
        default=ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO,
        help="Relatório de investigação gerado pelo investigar_pendencias.py",
    )
    parser.add_argument(
        "--dicionarios",
        default=ARQUIVO_DICIONARIOS_PADRAO,
        help="Arquivo dicionarios.yaml a ser atualizado",
    )
    parser.add_argument(
        "--gerar-template-decisoes",
        help="Gera um arquivo YAML de decisões e encerra (modo não-interativo)",
    )
    parser.add_argument(
        "--aplicar-decisoes",
        help="Aplica decisões de um arquivo YAML (modo não-interativo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria aplicado sem alterar dicionarios.yaml",
    )
    return parser



def _revisar_interativo(relatorio: dict[str, Any]) -> list[dict[str, Any]]:
    decisoes: list[dict[str, Any]] = []

    for item in relatorio.get("investigacoes", []):
        sugestao = item.get("sugestao", {})
        status = sugestao.get("status")
        traducao_sugerida = sugestao.get("traducao_sugerida")

        print("\n" + "-" * 72)
        print(f"Pendência: {item.get('tabela')}.{item.get('coluna')} = {item.get('valor')}")
        print(f"Status da sugestão: {status}")
        print(f"Sugestão: {traducao_sugerida!r}")
        print(f"Justificativa: {sugestao.get('justificativa')}")

        if status == "pista_unica":
            print(
                "\n⚠️  ATENÇÃO — Pista fraca: esta sugestão veio de uma coluna booleana ou sem "
                "relação semântica clara com o código investigado. Confirme manualmente o "
                "significado do código antes de aplicar. Diferença entre pistas:\n"
                "  • Pista FORTE: coluna com nome sugestivo (name, desc, title…) + valor textual variável.\n"
                "  • Pista FRACA: coluna booleana (0/1) ou nome técnico — valor constante não indica significado."
            )

        for alerta in sugestao.get("alertas", []):
            if alerta.get("tipo") == "possivel_dado_especifico":
                print(f"\n{alerta.get('mensagem')}")

        if not traducao_sugerida:
            print("Sem sugestão aplicável. Marcando como pular.")
            decisao = "pular"
            traducao_final = None
        else:
            while True:
                resposta = input("Aplicar? [s/n/e] ").strip().lower()
                if resposta == "s":
                    decisao = "aplicar"
                    traducao_final = traducao_sugerida
                    break
                if resposta == "e":
                    decisao = "aplicar"
                    traducao_editada = input("Informe a tradução final: ").strip()
                    if not traducao_editada:
                        print("Tradução vazia não é válida. Informe um texto ou escolha 'n'.")
                        continue
                    traducao_final = traducao_editada
                    break
                if resposta == "n":
                    decisao = "pular"
                    traducao_final = None
                    break
                print("Resposta inválida. Use 's' (sim), 'n' (não) ou 'e' (editar).")

        decisoes.append(
            {
                "tabela": item.get("tabela"),
                "coluna": item.get("coluna"),
                "valor": item.get("valor"),
                "status_sugestao": status,
                "traducao_sugerida": traducao_sugerida,
                "decisao": decisao,
                "traducao_final": traducao_final,
            }
        )

    return decisoes



def main() -> None:
    args = _parser().parse_args()

    relatorio = carregar_yaml(args.relatorio_investigacao)

    if args.gerar_template_decisoes:
        template = gerar_template_decisoes(relatorio)
        salvar_yaml(template, args.gerar_template_decisoes)
        print(f"✅ Template de decisões gerado em: {args.gerar_template_decisoes}")
        return

    if args.aplicar_decisoes:
        arquivo_decisoes = carregar_yaml(args.aplicar_decisoes)
        decisoes = arquivo_decisoes.get("decisoes", [])
    else:
        decisoes = _revisar_interativo(relatorio)

    caminho_dicionarios = Path(args.dicionarios)
    base = carregar_yaml(caminho_dicionarios) if caminho_dicionarios.exists() else {}
    atualizados, aplicadas = aplicar_decisoes_em_dicionario(base, decisoes)

    if args.dry_run:
        print("\n🧪 Dry-run: nenhuma alteração foi gravada.")
    else:
        salvar_yaml(atualizados, caminho_dicionarios)
        print(f"\n✅ dicionários atualizados em: {caminho_dicionarios}")

    print(f"📌 Traduções aplicadas: {len(aplicadas)}")
    for item in aplicadas:
        print(f" - {item['tabela']}.{item['coluna']}[{item['valor']}] = {item['traducao']}")


if __name__ == "__main__":
    main()
