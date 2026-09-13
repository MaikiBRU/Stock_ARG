"""Piezas compartidas por los esquemas de la API."""

from pydantic import BaseModel, Field

# Tope duro de pagina (RNF-06): sin el, un solo pedido puede arrastrar
# la tabla entera y tumbar la instancia.
LIMITE_MAXIMO = 100
LIMITE_POR_DEFECTO = 25


class Paginacion(BaseModel):
    """Parametros de paginado de cualquier listado."""

    pagina: int = Field(default=1, ge=1)
    limite: int = Field(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO)

    @property
    def desplazamiento(self) -> int:
        """Filas a saltear para llegar a la pagina pedida."""
        return (self.pagina - 1) * self.limite


class Pagina[T](BaseModel):
    """Una pagina de resultados con su total."""

    items: list[T]
    total: int
    pagina: int
    limite: int

    @property
    def paginas(self) -> int:
        """Cantidad total de paginas."""
        if self.limite <= 0:
            return 0
        return (self.total + self.limite - 1) // self.limite
