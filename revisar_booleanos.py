"""Revisa interativamente colunas marcadas como provável booleano."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from src.investigacao_colunas import (
    ARQUIVO_DECISOES_BOOLEANOS_PADRAO,
    ARQUIVO_RELATORIO_COLUNAS_PADRAO,
    _chave_tabela_coluna,
    carregar_decisoes_booleanos,
    carregar_yaml,
    registrar_decisao_booleana,
    salvar_decisoes_booleanos,
    salvar_yaml,
    sincronizar_decisoes_booleanos_relatorio,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Revisa interativamente colunas marcadas como provável booleano."
    )
    parser.add_argument(
        "--relatorio-investigacao",
        default=ARQUIVO_RELATORIO_COLUNAS_PADRAO,
        help="Relatório YAML gerado pelo investigar_colunas.py.",
    )
    parser.add_argument(
        "--arquivo-decisoes",
        default=ARQUIVO_DECISOES_BOOLEANOS_PADRAO,
        help="Arquivo YAML onde as confirmações/rejeições serão persistidas.",
    )
    parser.add_argument(
        "--tabela",
        help="Revisa apenas colunas da tabela informada.",
    )
    return parser


def _formatar_valores_observados(item: dict[str, Any]) -> str:
    """Formata os valores observados na amostra para exibição no terminal."""
    pista_booleana = next(
        (p for p in item.get("pistas", []) if p.get("categoria") == "provavel_booleano"),
        None,
    )
    valores = list(pista_booleana.get("valores_observados", [])) if pista_booleana else []
    if pista_booleana and pista_booleana.get("nulos_observados"):
        valores.append("NULL")
    return "{" + ", ".join(valores) + "}" if valores else "{sem amostra}"


def _linhas_contexto(item: dict[str, Any]) -> list[str]:
    """Extrai pistas textuais adicionais úteis para decisão humana."""
    linhas: list[str] = []
    for pista in item.get("pistas", []):
        fonte = str(pista.get("fonte", ""))
        if fonte == "column_comment":
            linhas.append(f"Comentário do schema: {pista.get('valor')}")
        elif fonte == "fk_referencia":
            linhas.append(f"Referência inferida: {pista.get('valor')}")
        elif fonte == "colunas_irmas":
            linhas.append(f"Coluna irmã: {pista.get('valor')}")
        elif fonte == "tipo_dado":
            linhas.append(f"Leitura do tipo: {pista.get('valor')}")
    return linhas


def _filtrar_colunas_pendentes(
    relatorio: dict[str, Any],
    decisoes: dict[str, Any],
    *,
    tabela: str | None = None,
) -> list[dict[str, Any]]:
    """Retorna apenas colunas prováveis booleanas ainda sem decisão manual."""
    tabela_filtro = tabela.lower() if tabela else None
    confirmadas = set((decisoes.get("confirmadas") or {}).keys())
    rejeitadas = set((decisoes.get("rejeitadas") or {}).keys())
    pendentes: list[dict[str, Any]] = []

    for item in relatorio.get("investigacoes", []):
        if not item.get("provavel_booleano"):
            continue
        if tabela_filtro and str(item.get("tabela", "")).lower() != tabela_filtro:
            continue
        chave = _chave_tabela_coluna(str(item.get("tabela", "")), str(item.get("coluna", "")))
        if chave in confirmadas or chave in rejeitadas:
            continue
        pendentes.append(item)

    return pendentes


def _contar_status(
    relatorio: dict[str, Any],
    decisoes: dict[str, Any],
    *,
    tabela: str | None = None,
) -> dict[str, int]:
    """Conta confirmadas, rejeitadas e pendentes dentro do escopo informado."""
    tabela_filtro = tabela.lower() if tabela else None
    confirmadas = 0
    rejeitadas = 0
    pendentes = 0

    for item in relatorio.get("investigacoes", []):
        if tabela_filtro and str(item.get("tabela", "")).lower() != tabela_filtro:
            continue
        chave = _chave_tabela_coluna(str(item.get("tabela", "")), str(item.get("coluna", "")))
        if chave in (decisoes.get("confirmadas") or {}):
            confirmadas += 1
        elif chave in (decisoes.get("rejeitadas") or {}):
            rejeitadas += 1
        elif item.get("provavel_booleano"):
            pendentes += 1

    return {
        "confirmadas": confirmadas,
        "rejeitadas": rejeitadas,
        "pendentes": pendentes,
    }


def _salvar_estado(
    caminho_relatorio: str | Path,
    caminho_decisoes: str | Path,
    relatorio: dict[str, Any],
    decisoes: dict[str, Any],
) -> None:
    """Persiste relatório anotado e arquivo de decisões."""
    sincronizar_decisoes_booleanos_relatorio(relatorio, decisoes)
    salvar_decisoes_booleanos(decisoes, caminho_decisoes)
    salvar_yaml(relatorio, caminho_relatorio)


def revisar_booleanos_interativamente(
    caminho_relatorio: str | Path = ARQUIVO_RELATORIO_COLUNAS_PADRAO,
    *,
    caminho_decisoes: str | Path = ARQUIVO_DECISOES_BOOLEANOS_PADRAO,
    tabela: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict[str, int]:
    """Executa a revisão interativa e persiste decisões automaticamente."""
    relatorio = carregar_yaml(caminho_relatorio)
    if not relatorio:
        raise FileNotFoundError(f"Relatório não encontrado ou vazio: {caminho_relatorio}")

    decisoes = carregar_decisoes_booleanos(caminho_decisoes)
    _salvar_estado(caminho_relatorio, caminho_decisoes, relatorio, decisoes)

    pendentes = _filtrar_colunas_pendentes(relatorio, decisoes, tabela=tabela)
    interrompido = False

    for indice, item in enumerate(pendentes, start=1):
        output_fn("\n" + "-" * 72)
        output_fn(f"[{indice}/{len(pendentes)}] Coluna: {item.get('tabela')}.{item.get('coluna')}")
        output_fn(f"Tipo: {item.get('tipo')}")
        output_fn(f"Valores observados: {_formatar_valores_observados(item)}")
        for linha in _linhas_contexto(item):
            output_fn(f"- {linha}")

        while True:
            resposta = input_fn(
                "Ação [s=confirmar booleano / n=rejeitar / p=pular / q=sair e salvar]: "
            ).strip().lower()
            if resposta in {"s", "n", "p", "q"}:
                break
            output_fn("Resposta inválida. Use s, n, p ou q.")

        if resposta == "q":
            interrompido = True
            break
        if resposta == "p":
            continue

        decisao = "confirmado" if resposta == "s" else "rejeitado"
        registrar_decisao_booleana(
            decisoes,
            str(item.get("tabela", "")),
            str(item.get("coluna", "")),
            decisao,
        )
        _salvar_estado(caminho_relatorio, caminho_decisoes, relatorio, decisoes)

    resumo = _contar_status(relatorio, decisoes, tabela=tabela)
    output_fn("\n✅ Revisão de booleanos finalizada")
    if interrompido:
        output_fn("ℹ️  Revisão interrompida pelo usuário; progresso salvo.")
    output_fn(f"Confirmadas: {resumo['confirmadas']}")
    output_fn(f"Rejeitadas: {resumo['rejeitadas']}")
    output_fn(f"Pendentes: {resumo['pendentes']}")
    return resumo


def main() -> None:
    args = _parser().parse_args()
    if args.tabela:
        print("🔎 Iniciando revisão interativa de colunas booleanas por tabela...")
        print(f"🗂️  Tabela: {args.tabela}")
    else:
        print("🔎 Iniciando revisão interativa de colunas booleanas...")
    print(f"📝 Relatório: {args.relatorio_investigacao}")
    print(f"💾 Decisões: {args.arquivo_decisoes}")

    revisar_booleanos_interativamente(
        args.relatorio_investigacao,
        caminho_decisoes=args.arquivo_decisoes,
        tabela=args.tabela,
    )


if __name__ == "__main__":
    main()
