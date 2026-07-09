"""Rotas para acessar dados das tabelas com paginação, filtros, ordenação e exportação."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func, and_, text, inspect
from sqlalchemy.orm import Session

logger = logging.getLogger("saidjur.routes_data")

router = APIRouter(tags=["Dados"])

# ── Constantes ──────────────────────────────────────────────────────────────

LIMIT_MAXIMO = 5000
LIMIT_PADRAO = 50


def _obter_tabela_dinamica(engine, tabela_nome: str):
    """Retorna a classe da tabela de forma dinâmica."""
    from sqlalchemy import MetaData, Table
    
    metadata = MetaData()
    try:
        table = Table(tabela_nome, metadata, autoload_with=engine)
        return table
    except Exception:
        return None


def _colunas_vazias(session: Session, engine, tabela_nome: str, colunas_nomes: list[str]) -> set[str]:
    """
    Identifica quais colunas têm APENAS valores NULL ou string vazia em toda a tabela.
    Retorna um set com os nomes das colunas vazias.
    """
    try:
        from sqlalchemy import MetaData, Table
        
        metadata = MetaData()
        table = Table(tabela_nome, metadata, autoload_with=engine)
        
        colunas_vazias = set()
        
        for col_nome in colunas_nomes:
            col = table.columns.get(col_nome)
            if col is None:
                continue
            
            # Conta quantos valores NÃO são NULL e NÃO são string vazia
            stmt = select(func.count()).select_from(table).where(
                and_(
                    col.isnot(None),
                    col != '',
                    col != '—',
                    col != '-',
                )
            )
            
            count_nao_vazios = session.execute(stmt).scalar() or 0
            
            # Se NÃO há valores não-vazios, coluna é considerada vazia
            if count_nao_vazios == 0:
                colunas_vazias.add(col_nome)
        
        return colunas_vazias
    
    except Exception as exc:
        logger.warning("Erro ao detectar colunas vazias em %s: %s", tabela_nome, exc)
        return set()


@router.get("/tabelas/{nome}/dados")
async def get_dados(
    nome: str,
    request: Request,
    pagina: int = 1,
    por_pagina: int = LIMIT_PADRAO,
    ordem_coluna: str | None = None,
    ordem_direcao: str = "asc",
    sem_colunas_vazias: bool = False,
    **filtros,
) -> dict[str, Any]:
    """
    Retorna os dados de uma tabela com paginação, filtros e ordenação.
    
    **Parâmetros:**
    - `pagina`: número da página (começa em 1)
    - `por_pagina`: quantidade de linhas por página (padrão: 50, máximo: 5000)
    - `ordem_coluna`: coluna para ordenar
    - `ordem_direcao`: "asc" ou "desc"
    - `sem_colunas_vazias`: se `true`, remove colunas que só têm valores NULL/vazios
    - Qualquer outro parâmetro é tratado como filtro: `?coluna=valor`
    
    **Exemplo:**
    ```
    GET /api/tabelas/usuarios/dados?pagina=1&por_pagina=50&sem_colunas_vazias=true&status=ATIVO
    ```
    """
    engine = request.app.state.engine
    
    # Validações
    if pagina < 1:
        pagina = 1
    if por_pagina < 1:
        por_pagina = LIMIT_PADRAO
    if por_pagina > LIMIT_MAXIMO:
        por_pagina = LIMIT_MAXIMO
    
    ordem_direcao = ordem_direcao.lower()
    if ordem_direcao not in ("asc", "desc"):
        ordem_direcao = "asc"
    
    try:
        from sqlalchemy import MetaData, Table
        
        metadata = MetaData()
        table = Table(nome, metadata, autoload_with=engine)
        
        if table is None:
            raise HTTPException(status_code=404, detail=f"Tabela '{nome}' não encontrada")
        
        with Session(engine) as session:
            # ── Identificar colunas vazias (se solicitado) ──
            colunas_usar = [c.name for c in table.columns]
            colunas_ocultar = set()
            
            if sem_colunas_vazias:
                colunas_ocultar = _colunas_vazias(session, engine, nome, colunas_usar)
                colunas_usar = [c for c in colunas_usar if c not in colunas_ocultar]
            
            # ── Construir query base ──
            stmt = select(table)
            
            # ── Aplicar filtros ──
            condicoes_filtro = []
            for chave, valor in filtros.items():
                if not valor or chave in ("pagina", "por_pagina", "ordem_coluna", "ordem_direcao", "sem_colunas_vazias"):
                    continue
                
                col = table.columns.get(chave)
                if col is not None:
                    condicoes_filtro.append(col.ilike(f"%{valor}%"))
            
            if condicoes_filtro:
                stmt = stmt.where(and_(*condicoes_filtro))
            
            # ── Contar total ──
            total_stmt = select(func.count()).select_from(table)
            if condicoes_filtro:
                total_stmt = total_stmt.where(and_(*condicoes_filtro))
            total_registros = session.execute(total_stmt).scalar() or 0
            
            # ── Ordenação ──
            if ordem_coluna:
                col = table.columns.get(ordem_coluna)
                if col is not None:
                    if ordem_direcao == "desc":
                        stmt = stmt.order_by(col.desc())
                    else:
                        stmt = stmt.order_by(col.asc())
            
            # ── Paginação ──
            offset = (pagina - 1) * por_pagina
            stmt = stmt.offset(offset).limit(por_pagina)
            
            # ── Executar ──
            resultado = session.execute(stmt).fetchall()
            
            # ── Serializar ──
            dados = []
            for row in resultado:
                row_dict = {}
                for col_nome in colunas_usar:
                    valor = row._mapping.get(col_nome)
                    row_dict[col_nome] = valor
                dados.append(row_dict)
            
            # ── Metadados das colunas ──
            colunas_info = [
                {
                    "nome": col.name,
                    "tipo": str(col.type),
                    "vazio": col.name in colunas_ocultar,
                }
                for col in table.columns
                if col.name in colunas_usar
            ]
            
            total_paginas = (total_registros + por_pagina - 1) // por_pagina
            
            return {
                "tabela": nome,
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total_registros": total_registros,
                "total_paginas": total_paginas,
                "colunas": colunas_info,
                "dados": dados,
                "colunas_ocultadas": list(colunas_ocultar),
            }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao buscar dados de %s", nome)
        raise HTTPException(
            status_code=503,
            detail=f"Não foi possível buscar dados: {exc}",
        ) from exc