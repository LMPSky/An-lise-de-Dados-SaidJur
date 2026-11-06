"""Acesso a documentos externos de um processo (fora do banco de dados).

O sistema legado SaidJur não armazena os arquivos digitalizados (PDFs,
imagens etc.) como BLOB no MySQL: as tabelas guardam apenas *caminhos*
(colunas como ``filepath``, ``path``, ``relativepath``) para arquivos que
vivem em um diretório externo, organizado em uma subpasta por processo
(nome da subpasta = número do processo no formato CNJ, ex:
``0000003-16.2025.5.07.0015``).

Este módulo resolve, de forma segura, o caminho desses arquivos a partir do
``diretorio_base`` configurado em ``config.yaml`` (seção ``documentos``),
sem nunca deixar o chamador escapar dessa pasta (proteção contra path
traversal).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import CONFIG


class DocumentosDesabilitadosError(Exception):
    """Levantada quando a funcionalidade de documentos não está configurada."""


class NumeroProcessoInvalidoError(Exception):
    """Levantada quando o número de processo contém caracteres não permitidos."""


class NomeArquivoInvalidoError(Exception):
    """Levantada quando o nome de arquivo contém caracteres não permitidos."""


@dataclass
class ArquivoDocumento:
    """Metadados de um arquivo encontrado na pasta de um processo."""

    nome: str
    tamanho_bytes: int
    modificado_em: float
    extensao: str


def diretorio_base_configurado() -> Path | None:
    """Retorna o diretório base configurado, ou ``None`` se desabilitado."""
    cfg = CONFIG.get("documentos", {}) or {}
    if not cfg.get("habilitado"):
        return None
    caminho = cfg.get("diretorio_base") or ""
    if not caminho:
        return None
    return Path(caminho)


# Caracteres aceitos em um número de processo (formato CNJ: dígitos, pontos
# e hífens, ex: "0000003-16.2025.5.07.0015") ou em nomes de pasta legados
# equivalentes. Qualquer outro caractere (incluindo barras e "..") é rejeitado.
_CARACTERES_PERMITIDOS_PROCESSO = set("0123456789.-")


def _validar_numero_processo(numero_processo: str) -> str:
    """Valida que ``numero_processo`` é seguro para uso como nome de pasta."""
    numero = (numero_processo or "").strip()
    if not numero or numero in {".", ".."}:
        raise NumeroProcessoInvalidoError("Número de processo vazio ou inválido.")
    if any(c not in _CARACTERES_PERMITIDOS_PROCESSO for c in numero):
        raise NumeroProcessoInvalidoError(
            f"Número de processo contém caracteres não permitidos: '{numero_processo}'"
        )
    return numero


def _validar_nome_arquivo(nome_arquivo: str) -> str:
    """Valida que ``nome_arquivo`` é seguro (sem separadores de caminho)."""
    nome = (nome_arquivo or "").strip()
    if not nome or nome in {".", ".."}:
        raise NomeArquivoInvalidoError("Nome de arquivo vazio ou inválido.")
    if "/" in nome or "\\" in nome:
        raise NomeArquivoInvalidoError(
            f"Nome de arquivo não pode conter separadores de caminho: '{nome_arquivo}'"
        )
    return nome


def _resolver_dentro_da_base(base: Path, *partes: str) -> Path:
    """Resolve ``base/partes`` garantindo que o resultado não escape de ``base``."""
    base_resolvida = base.resolve()
    alvo_resolvido = base_resolvida.joinpath(*partes).resolve()
    if alvo_resolvido != base_resolvida and base_resolvida not in alvo_resolvido.parents:
        raise NumeroProcessoInvalidoError("Caminho resolvido fica fora do diretório base permitido.")
    return alvo_resolvido


def pasta_do_processo(numero_processo: str) -> Path:
    """Retorna o caminho (validado) da pasta de um processo, sem verificar existência."""
    base = diretorio_base_configurado()
    if base is None:
        raise DocumentosDesabilitadosError("Acesso a documentos não está configurado/habilitado.")
    numero = _validar_numero_processo(numero_processo)
    return _resolver_dentro_da_base(base, numero)


def listar_documentos_processo(numero_processo: str) -> list[ArquivoDocumento]:
    """Lista os arquivos disponíveis para um processo.

    Retorna lista vazia se o processo não tiver pasta de documentos
    (situação esperada para a maioria dos processos até que todo o acervo
    seja migrado para o diretório de documentos).
    """
    pasta = pasta_do_processo(numero_processo)
    if not pasta.is_dir():
        return []

    arquivos: list[ArquivoDocumento] = []
    for item in sorted(pasta.iterdir()):
        if not item.is_file():
            continue
        stat = item.stat()
        arquivos.append(
            ArquivoDocumento(
                nome=item.name,
                tamanho_bytes=stat.st_size,
                modificado_em=stat.st_mtime,
                extensao=item.suffix.lower().lstrip("."),
            )
        )
    return arquivos


def resolver_caminho_arquivo(numero_processo: str, nome_arquivo: str) -> Path:
    """Resolve o caminho de um arquivo específico de um processo, com validação completa.

    Levanta ``FileNotFoundError`` se o arquivo não existir.
    """
    base = diretorio_base_configurado()
    if base is None:
        raise DocumentosDesabilitadosError("Acesso a documentos não está configurado/habilitado.")

    numero = _validar_numero_processo(numero_processo)
    nome = _validar_nome_arquivo(nome_arquivo)
    caminho = _resolver_dentro_da_base(base, numero, nome)

    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {numero_processo}/{nome_arquivo}")

    return caminho
