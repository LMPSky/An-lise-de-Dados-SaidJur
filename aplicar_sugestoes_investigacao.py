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
    parser.add_argument(
        "--aprovar-fonte",
        choices=("fk_declarada", "fk_inferida", "tabela_referencia", "tabela_irma", "multiplas_pistas"),
        help=(
            "Aprova explicitamente, em lote, sugestões de alta confiança desta fonte. "
            "'fk_declarada' (chave estrangeira real do schema) e 'fk_inferida' (FK "
            "detectada por convenção de nome, mesma heurística já usada na interface "
            "web) são as fontes mais confiáveis, pois a tabela/coluna de referência "
            "não é adivinhada por radical de nome como em 'tabela_referencia'."
        ),
    )
    parser.add_argument(
        "--excluir-coluna",
        action="append",
        default=[],
        metavar="tabela.coluna",
        help=(
            "Exclui explicitamente uma coluna (formato 'tabela.coluna') do lote aprovado "
            "por --aprovar-fonte, mesmo que ela tenha sugestões de alta confiança. Útil "
            "para deixar de fora colunas que você já identificou manualmente como "
            "problemáticas. Pode ser repetido para excluir várias colunas."
        ),
    )
    parser.add_argument(
        "--incluir-colunas-inconsistentes",
        action="store_true",
        help=(
            "Por padrão, quando a fonte 'tabela_referencia' resolve a MESMA coluna para "
            "tabelas de referência diferentes em valores distintos (sinal de colisão por "
            "coincidência, não uma FK real), essa coluna é excluída automaticamente do lote "
            "e um aviso é exibido. Use esta flag para incluir essas colunas mesmo assim."
        ),
    )
    return parser



def _detectar_colunas_referencia_inconsistente(itens: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Detecta colunas cujos itens resolveram para tabela_referencia divergentes.

    Uma coluna ENUM legítima deve mapear consistentemente para um único
    catálogo/tabela de referência em todos os seus valores. Quando valores
    diferentes da mesma coluna (tabela.coluna) resolvem para tabelas de
    referência diferentes, é sinal de que ao menos uma delas bateu por
    coincidência de id, não por uma relação semântica real — ver o caso de
    'lawsuitdocs.doctype' resolvendo ora para 'correspondent_document_types',
    ora para 'otherdocs'.
    """
    tabelas_por_coluna: dict[str, set[str]] = {}
    for item in itens:
        chave = f"{item.get('tabela')}.{item.get('coluna')}"
        tabela_ref = item.get("tabela_referencia")
        if tabela_ref:
            tabelas_por_coluna.setdefault(chave, set()).add(tabela_ref)
    return {chave: tabelas for chave, tabelas in tabelas_por_coluna.items() if len(tabelas) > 1}



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

        contexto_obs = item.get("contexto_obs")
        if contexto_obs:
            print(
                f"\n📝 Contexto adicional — coluna de observação '{contexto_obs.get('coluna_obs')}' "
                f"({contexto_obs.get('valores_distintos', 0)} valor(es) distinto(s), "
                f"{contexto_obs.get('total_ocorrencias', 0)} ocorrência(s) total):"
            )
            for amostra in contexto_obs.get("amostras", []):
                print(f"   [{amostra.get('ocorrencias', 0)}x] {amostra.get('valor', '')!r}")

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
    elif args.aprovar_fonte:
        itens_elegiveis = [
            item
            for item in relatorio.get("investigacoes", [])
            if item.get("sugestao", {}).get("status") == "alta_confianca"
            and item.get("sugestao", {}).get("fonte") == args.aprovar_fonte
            and not item.get("sugestao", {}).get("alertas")
        ]

        colunas_inconsistentes = (
            _detectar_colunas_referencia_inconsistente(itens_elegiveis)
            if args.aprovar_fonte == "tabela_referencia"
            else {}
        )
        excluidas_manualmente = set(args.excluir_coluna)
        excluidas_por_inconsistencia = (
            set(colunas_inconsistentes) if not args.incluir_colunas_inconsistentes else set()
        )
        colunas_excluidas = excluidas_manualmente | excluidas_por_inconsistencia

        itens_aprovados = [
            item
            for item in itens_elegiveis
            if f"{item.get('tabela')}.{item.get('coluna')}" not in colunas_excluidas
        ]

        decisoes = [
            {
                "tabela": item.get("tabela"),
                "coluna": item.get("coluna"),
                "valor": item.get("valor"),
                "status_sugestao": item.get("sugestao", {}).get("status"),
                "traducao_sugerida": item.get("sugestao", {}).get("traducao_sugerida"),
                "decisao": "aplicar",
            }
            for item in itens_aprovados
        ]
        print(f"⚠️ Aprovação explícita em lote: fonte {args.aprovar_fonte} ({len(decisoes)} sugestão(ões)).")

        if colunas_inconsistentes:
            print(
                "\n🚫 Colunas excluídas automaticamente por tabela_referencia inconsistente "
                "(a mesma coluna resolveu para tabelas de referência diferentes em valores "
                "distintos — sinal de colisão por coincidência, não FK real). Use "
                "--incluir-colunas-inconsistentes para incluí-las mesmo assim, ou revise "
                "manualmente com --aplicar-decisoes:"
            )
            for chave, tabelas in sorted(colunas_inconsistentes.items()):
                marcador = " (incluída via --incluir-colunas-inconsistentes)" if args.incluir_colunas_inconsistentes else ""
                print(f"   - {chave}: {', '.join(sorted(tabelas))}{marcador}")

        if excluidas_manualmente:
            presentes = excluidas_manualmente & {
                f"{item.get('tabela')}.{item.get('coluna')}" for item in itens_elegiveis
            }
            if presentes:
                print(f"\n🚫 Colunas excluídas manualmente via --excluir-coluna: {', '.join(sorted(presentes))}")

        if args.aprovar_fonte == "tabela_referencia":
            print(
                "\n⚠️  ATENÇÃO: esta fonte usa lookup por id em outra tabela detectada por "
                "heurística de nome — pode colidir por coincidência com uma tabela sem "
                "relação semântica real. Revise a coluna 'tabela_referencia' de cada item "
                "abaixo antes de aplicar; se o nome da tabela não fizer sentido para a "
                "coluna original, use --aplicar-decisoes com decisao=pular para esse item."
            )
            for item in itens_aprovados:
                print(
                    f"   - {item.get('tabela')}.{item.get('coluna')}[{item.get('valor')}] "
                    f"= {item.get('sugestao', {}).get('traducao_sugerida')!r} "
                    f"(via tabela_referencia={item.get('tabela_referencia')})"
                )
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
