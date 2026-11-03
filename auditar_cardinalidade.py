"""Audita o banco por cardinalidade real de coluna, sem teto fixo de amostra.

Complementa ``investigar_pendencias.py``/``listar_traducoes_faltantes.py`` e
``auditar_traducoes.py``: essas ferramentas descartam qualquer coluna cuja
amostra de valores distintos ultrapasse um teto fixo pequeno (20 valores),
mesmo rodando no modo mais completo. Isso deixa colunas de código/ENUM
legítimas com catálogos maiores (ex: ~40-100 tipos de documento) permanentemente
fora do radar.

Este script usa ``COUNT(DISTINCT coluna)`` para decidir, por cardinalidade
real (não por nome de coluna nem por um teto de amostra), se uma coluna é
categórica. Colunas aprovadas têm **todos** os seus valores comparados ao
``dicionarios.yaml``.

Por padrão, roda apenas sobre a faixa de catálogos grandes (cardinalidade
501–5.000): a faixa 2–500 já foi varrida e revisada manualmente numa rodada
anterior (``relatorio_investigacao_cardinalidade.yaml``), então repeti-la do
zero desperdiçaria tempo nesse banco de ~50GB sem encontrar nada novo. Para
refazer a faixa já revisada (ex: validar o efeito de uma mudança nos
filtros), passe explicitamente ``--cardinalidade-minima 2
--cardinalidade-maxima 500``.

Por varrer o banco inteiro coluna a coluna (``COUNT(DISTINCT)`` em cada uma),
pode demorar bastante num banco de ~50GB — recomendado rodar em segundo
plano, assim como ``listar_traducoes_faltantes.py --completo``.
"""

from __future__ import annotations

import argparse

from src.auditoria_cardinalidade import (
    ARQUIVO_AUDITORIA_CARDINALIDADE_PADRAO,
    CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
    CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
    auditar_cobertura_por_cardinalidade,
)
from src.db import criar_engine
from src.investigacao_pendencias import salvar_yaml


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audita o banco inteiro por cardinalidade real de coluna "
            "(COUNT(DISTINCT)), encontrando colunas de código/ENUM com mais "
            "valores distintos do que o teto fixo (20) usado pelas demais "
            "ferramentas de descoberta. Por padrão, foca em catálogos "
            "grandes (acima da faixa 2-500 já revisada)."
        )
    )
    parser.add_argument(
        "--cardinalidade-minima",
        type=int,
        default=CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
        help=(
            "Cardinalidade mínima para considerar a coluna categórica "
            f"(padrão: {CARDINALIDADE_MINIMA_CATALOGOS_GRANDES}, logo acima da faixa já revisada 2-500)."
        ),
    )
    parser.add_argument(
        "--cardinalidade-maxima",
        type=int,
        default=CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
        help=f"Cardinalidade máxima para considerar a coluna categórica (padrão: {CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES}).",
    )
    parser.add_argument(
        "--saida",
        default=ARQUIVO_AUDITORIA_CARDINALIDADE_PADRAO,
        help="Arquivo YAML de saída do relatório.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()

    print("🔎 Iniciando auditoria de cobertura por cardinalidade real de coluna...")
    print(f"📏 Faixa de cardinalidade categórica: {args.cardinalidade_minima}–{args.cardinalidade_maxima}")
    print("ℹ️  Modo somente leitura (queries SELECT). Isso pode demorar bastante.")

    engine = criar_engine()
    relatorio = auditar_cobertura_por_cardinalidade(
        engine,
        cardinalidade_minima=args.cardinalidade_minima,
        cardinalidade_maxima=args.cardinalidade_maxima,
    )
    salvar_yaml(relatorio, args.saida)

    resumo = relatorio["resumo"]
    print("\n✅ Auditoria concluída")
    print(f"🧩 Colunas auditadas (dentro da faixa de cardinalidade): {resumo['colunas_auditadas']}")
    print(f"📦 Colunas fora da faixa (texto livre ou constante): {resumo['colunas_fora_do_intervalo_cardinalidade']}")
    print(f"🎯 Colunas com pendência de tradução: {resumo['total_colunas_com_pendencia']}")
    print(f"🧮 Total de valores sem tradução: {resumo['total_valores_pendentes']}")
    print(f"⚠️  Colunas com falha ao consultar: {resumo['total_colunas_com_falha']}")
    print(f"\n📝 Relatório salvo em: {args.saida}")


if __name__ == "__main__":
    main()
