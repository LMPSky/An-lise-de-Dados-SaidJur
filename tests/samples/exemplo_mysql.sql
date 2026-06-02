-- Dump MySQL de exemplo para testes (compatível com MySQL 8.x / MariaDB 10.x)
-- Gerado para validar importação, busca e exportação com dados em utf8mb4.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8mb4 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;

-- ─────────────────────────────────────────────────────────────────
-- Tabela: clientes
-- ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `clientes`;
CREATE TABLE `clientes` (
  `id`         INT          NOT NULL AUTO_INCREMENT,
  `nome`       VARCHAR(120) NOT NULL,
  `email`      VARCHAR(160) DEFAULT NULL,
  `cidade`     VARCHAR(80)  DEFAULT NULL,
  `cpf`        CHAR(11)     DEFAULT NULL,
  `criado_em`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_nome` (`nome`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

LOCK TABLES `clientes` WRITE;
INSERT INTO `clientes` (`id`, `nome`, `email`, `cidade`, `cpf`, `criado_em`) VALUES
(1,  'João da Silva',        'joao@exemplo.com.br',    'São Paulo',       '12345678901', '2023-01-10 08:30:00'),
(2,  'Maria Aparecida',      'maria@exemplo.com.br',   'Rio de Janeiro',  '23456789012', '2023-02-14 10:15:00'),
(3,  'Carlos Alberto',       'carlos@exemplo.com.br',  'Belo Horizonte',  '34567890123', '2023-03-20 14:00:00'),
(4,  'Ana Beatriz',          'ana.b@exemplo.com.br',   'Curitiba',        '45678901234', '2023-04-05 09:45:00'),
(5,  'Pedro Henrique',       'pedro@exemplo.com.br',   'Porto Alegre',    '56789012345', '2023-05-18 11:30:00'),
(6,  'Fernanda de Oliveira', 'fernanda@exemplo.com.br','Salvador',        '67890123456', '2023-06-22 16:00:00'),
(7,  'Luís Gustavo',         'luis@exemplo.com.br',    'Fortaleza',       '78901234567', '2023-07-30 08:00:00'),
(8,  'Patrícia Souza',       'patricia@exemplo.com.br','Manaus',          '89012345678', '2023-08-11 13:20:00'),
(9,  'Roberto Carlos',       'roberto@exemplo.com.br', 'Recife',          '90123456789', '2023-09-03 15:45:00'),
(10, 'Juliana Mendes',       'juliana@exemplo.com.br', 'Brasília',        '01234567890', '2023-10-25 10:00:00');
UNLOCK TABLES;

-- ─────────────────────────────────────────────────────────────────
-- Tabela: processos
-- ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `processos`;
CREATE TABLE `processos` (
  `id`            INT          NOT NULL AUTO_INCREMENT,
  `numero`        VARCHAR(30)  NOT NULL COMMENT 'Número CNJ do processo',
  `cliente_id`    INT          NOT NULL,
  `status`        VARCHAR(30)  NOT NULL DEFAULT 'em andamento',
  `descricao`     TEXT         DEFAULT NULL,
  `data_abertura` DATE         NOT NULL,
  `data_fechamento` DATE       DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_numero` (`numero`),
  KEY `fk_cliente` (`cliente_id`),
  CONSTRAINT `fk_processo_cliente` FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

LOCK TABLES `processos` WRITE;
INSERT INTO `processos` (`id`, `numero`, `cliente_id`, `status`, `descricao`, `data_abertura`, `data_fechamento`) VALUES
(1,  '0001234-12.2023.8.26.0001', 1,  'em andamento',  'Ação de cobrança referente a dívida de aluguel', '2023-01-15', NULL),
(2,  '0002345-23.2023.8.26.0002', 2,  'concluído',     'Divórcio consensual com partilha de bens',       '2023-02-20', '2023-08-10'),
(3,  '0003456-34.2023.8.26.0003', 3,  'em andamento',  'Pedido de indenização por dano moral',           '2023-03-25', NULL),
(4,  '0004567-45.2023.8.26.0004', 4,  'arquivado',     'Reclamação trabalhista — acordo firmado',        '2023-04-10', '2023-11-30'),
(5,  '0005678-56.2023.8.26.0005', 5,  'em andamento',  'Inventário de bens e herança',                  '2023-05-20', NULL),
(6,  '0006789-67.2023.8.26.0006', 6,  'suspenso',      'Ação civil pública ambiental',                  '2023-06-30', NULL),
(7,  '0007890-78.2023.8.26.0007', 7,  'concluído',     'Execução fiscal — quitação total',              '2023-07-05', '2023-12-15'),
(8,  '0008901-89.2023.8.26.0008', 8,  'em andamento',  'Guarda e pensão alimentícia',                   '2023-08-15', NULL),
(9,  '0009012-90.2023.8.26.0009', 9,  'em andamento',  'Revisão de contrato bancário — juros abusivos', '2023-09-10', NULL),
(10, '0010123-01.2023.8.26.0010', 10, 'arquivado',     'Ação de despejo por falta de pagamento',        '2023-10-28', '2024-01-20');
UNLOCK TABLES;

-- ─────────────────────────────────────────────────────────────────
-- Tabela: documentos
-- ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `documentos`;
CREATE TABLE `documentos` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `processo_id`  INT          NOT NULL,
  `tipo`         VARCHAR(60)  NOT NULL,
  `nome_arquivo` VARCHAR(200) NOT NULL,
  `tamanho_kb`   INT          DEFAULT NULL,
  `enviado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_doc_processo` (`processo_id`),
  CONSTRAINT `fk_documento_processo` FOREIGN KEY (`processo_id`) REFERENCES `processos` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

LOCK TABLES `documentos` WRITE;
INSERT INTO `documentos` (`id`, `processo_id`, `tipo`, `nome_arquivo`, `tamanho_kb`, `enviado_em`) VALUES
(1,  1, 'Petição inicial',    'peticao_inicial_0001234.pdf',  345, '2023-01-15 09:00:00'),
(2,  1, 'Comprovante',        'comprovante_aluguel_jan23.pdf', 89, '2023-01-16 10:30:00'),
(3,  2, 'Certidão casamento', 'certidao_casamento.pdf',       120, '2023-02-20 14:00:00'),
(4,  2, 'Acordo divórcio',    'acordo_divorcio.pdf',          220, '2023-03-01 11:00:00'),
(5,  3, 'Boletim ocorrência', 'bo_dano_moral.pdf',            78,  '2023-03-25 16:00:00'),
(6,  4, 'CTPS',               'carteira_trabalho.pdf',        95,  '2023-04-10 08:30:00'),
(7,  5, 'Certidão óbito',     'certidao_obito.pdf',           60,  '2023-05-20 09:15:00'),
(8,  6, 'Laudo ambiental',    'laudo_ambiental_2023.pdf',     980, '2023-06-30 15:00:00'),
(9,  7, 'DAF',                'daf_execucao_fiscal.pdf',      450, '2023-07-05 10:00:00'),
(10, 8, 'DNA',                'resultado_dna_guarda.pdf',     200, '2023-08-15 13:00:00');
UNLOCK TABLES;

/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
