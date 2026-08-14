"""Revisa e aplica sugestões de tradução de colunas em src/traducoes_colunas.py."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

from src.investigacao_colunas import (
    ARQUIVO_RELATORIO_COLUNAS_PADRAO,
    classificar_estado_traducao,
)
from src.investigacao_pendencias import carregar_yaml
from src.traducoes_colunas import TRADUCOES_COLUNAS

CAMINHO_TRADUCOES_PADRAO = "src/traducoes_colunas.py"



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Revisa/aplica sugestões do relatório de investigação de colunas."
    )
    parser.add_argument(
        "--relatorio-investigacao",
        default=ARQUIVO_RELATORIO_COLUNAS_PADRAO,
        help="Relatório YAML gerado pelo investigar_colunas.py.",
    )
    parser.add_argument(
        "--arquivo-traducoes",
        default=CAMINHO_TRADUCOES_PADRAO,
        help="Arquivo Python contendo o dicionário TRADUCOES_COLUNAS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria aplicado sem alterar o arquivo Python.",
    )
    return parser



def _confirmar_sobrescrita_manual(coluna: str, traducao_final: str) -> bool:
    """Pede confirmação extra antes de sobrescrever tradução manual existente."""
    if classificar_estado_traducao(coluna) != "traduzida_manual":
        return True

    atual = TRADUCOES_COLUNAS.get(coluna.lower())
    print(
        f"⚠️  A coluna '{coluna}' já possui tradução manual: {atual!r}. "
        f"Nova tradução proposta: {traducao_final!r}."
    )
    return input("Sobrescrever mesmo assim? [s/N] ").strip().lower() == "s"



def _revisar_interativo(relatorio: dict[str, Any]) -> list[dict[str, Any]]:
    """Percorre o relatório e coleta decisões do usuário."""
    decisoes: list[dict[str, Any]] = []

    for item in relatorio.get("investigacoes", []):
        sugestao = item.get("sugestao_candidata")
        nivel = item.get("nivel_confianca")
        estado = item.get("estado")
        coluna = str(item.get("coluna", ""))

        print("\n" + "-" * 72)
        print(f"Coluna: {item.get('tabela')}.{coluna}")
        print(f"Estado atual: {estado}")
        print(f"Tradução atual: {item.get('traducao_atual')!r}")
        print(f"Nível da investigação: {nivel}")
        print(f"Sugestão: {sugestao!r}")
        if item.get("pistas"):
            print("Pistas:")
            for pista in item["pistas"]:
                print(f" - [{pista.get('confianca')}] {pista.get('fonte')}: {pista.get('valor')}")

        if not sugestao:
            print("Sem sugestão aplicável. Marcando como pular.")
            decisao = "pular"
            traducao_final = None
        else:
            decisao = "pular"
            traducao_final = None
            while True:
                resposta = input("Aplicar? [s/n/e] ").strip().lower()
                if resposta == "s":
                    traducao_final = sugestao
                elif resposta == "e":
                    traducao_final = input("Informe a tradução final: ").strip()
                    if not traducao_final:
                        print("Tradução vazia não é válida. Informe um texto ou escolha 'n'.")
                        continue
                elif resposta == "n":
                    decisao = "pular"
                    traducao_final = None
                    break
                else:
                    print("Resposta inválida. Use 's' (sim), 'n' (não) ou 'e' (editar).")
                    continue

                if _confirmar_sobrescrita_manual(coluna, traducao_final):
                    decisao = "aplicar"
                else:
                    decisao = "pular"
                    traducao_final = None
                break

        decisoes.append(
            {
                "tabela": item.get("tabela"),
                "coluna": coluna,
                "estado": estado,
                "nivel_confianca": nivel,
                "traducao_sugerida": sugestao,
                "decisao": decisao,
                "traducao_final": traducao_final,
            }
        )

    return decisoes



def _carregar_dict_existente(caminho_arquivo: Path) -> dict[str, str]:
    """Extrai o literal atual de TRADUCOES_COLUNAS para validação."""
    modulo = ast.parse(caminho_arquivo.read_text(encoding="utf-8"))
    for node in modulo.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TRADUCOES_COLUNAS":
                    return ast.literal_eval(node.value)
    raise ValueError("Não foi possível localizar TRADUCOES_COLUNAS no arquivo informado.")



def _localizar_bloco_traducoes(conteudo: str) -> tuple[int, int]:
    """Localiza os índices do bloco literal de TRADUCOES_COLUNAS."""
    marcador = "TRADUCOES_COLUNAS = {"
    inicio = conteudo.find(marcador)
    if inicio < 0:
        raise ValueError("Bloco TRADUCOES_COLUNAS não encontrado.")

    pos_abertura = conteudo.find("{", inicio)
    profundidade = 0
    for indice in range(pos_abertura, len(conteudo)):
        caractere = conteudo[indice]
        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade -= 1
            if profundidade == 0:
                return pos_abertura, indice
    raise ValueError("Fim do bloco TRADUCOES_COLUNAS não encontrado.")


def _inferir_indentacao_bloco(bloco: str) -> str:
    """Infere a indentação predominante do literal de traduções."""
    for linha in bloco.splitlines():
        linha_limpa = linha.lstrip()
        if linha_limpa.startswith(("'", '"')):
            return linha[: len(linha) - len(linha_limpa)]
    return "    "


def aplicar_traducoes_no_arquivo(
    caminho_arquivo: str | Path,
    decisoes: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    """Aplica as traduções aprovadas diretamente no arquivo Python."""
    caminho = Path(caminho_arquivo)
    conteudo = caminho.read_text(encoding="utf-8")
    existentes = _carregar_dict_existente(caminho)
    bloco_inicio, bloco_fim = _localizar_bloco_traducoes(conteudo)
    bloco = conteudo[bloco_inicio : bloco_fim + 1]
    indentacao = _inferir_indentacao_bloco(bloco)
    aplicadas: list[dict[str, str]] = []
    insercoes: list[str] = []

    for item in decisoes:
        if str(item.get("decisao", "")).lower() != "aplicar":
            continue
        coluna = str(item.get("coluna", "")).strip().lower()
        traducao = item.get("traducao_final") or item.get("traducao_sugerida")
        traducao = str(traducao).strip() if traducao is not None else ""
        if not coluna or not traducao:
            continue

        nova_linha = f"{indentacao}{coluna!r}: {traducao!r},\n"
        chave_literal = f"{coluna!r}:"
        linhas = bloco.splitlines(keepends=True)
        substituiu = False
        for indice, linha in enumerate(linhas):
            if linha.lstrip().startswith(chave_literal):
                linhas[indice] = nova_linha
                substituiu = True
                break

        if substituiu:
            bloco = "".join(linhas)
        else:
            if coluna in existentes:
                raise ValueError(
                    f"Chave '{coluna}' encontrada no AST, mas não localizada textualmente no bloco."
                )
            insercoes.append(nova_linha)

        aplicadas.append({"coluna": coluna, "traducao": traducao})
        existentes[coluna] = traducao

    if insercoes:
        bloco = bloco[:-1] + "".join(insercoes) + "}"

    novo_conteudo = conteudo[:bloco_inicio] + bloco + conteudo[bloco_fim + 1 :]

    if not dry_run and aplicadas:
        caminho.write_text(novo_conteudo, encoding="utf-8")

    return aplicadas



def main() -> None:
    args = _parser().parse_args()
    relatorio = carregar_yaml(args.relatorio_investigacao)
    decisoes = _revisar_interativo(relatorio)
    aplicadas = aplicar_traducoes_no_arquivo(
        args.arquivo_traducoes,
        decisoes,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print("\n🧪 Dry-run: nenhuma alteração foi gravada.")
    else:
        print(f"\n✅ Traduções atualizadas em: {args.arquivo_traducoes}")

    print(f"📌 Traduções aplicadas: {len(aplicadas)}")
    for item in aplicadas:
        print(f" - {item['coluna']} = {item['traducao']}")


if __name__ == "__main__":
    main()
