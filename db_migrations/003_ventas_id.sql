-- Agrega ID único a ventas para permitir editar/eliminar por venta.
ALTER TABLE ventas
  ADD COLUMN venta_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST;

-- Índices útiles
CREATE INDEX idx_ventas_producto ON ventas(id);
CREATE INDEX idx_ventas_fecha ON ventas(fecha);
