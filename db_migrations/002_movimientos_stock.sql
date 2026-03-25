CREATE TABLE IF NOT EXISTS movimientos_stock (
    id INT NOT NULL AUTO_INCREMENT,
    producto_id VARCHAR(50) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    cantidad INT NOT NULL,
    nota VARCHAR(255) DEFAULT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_mov_producto (producto_id),
    INDEX idx_mov_tipo (tipo),
    INDEX idx_mov_creado (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
