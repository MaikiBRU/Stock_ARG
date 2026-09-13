"""Lectura segura de archivos subidos por el usuario (RNF-11).

Nada de lo que llega en la peticion se toma por cierto: ni el nombre, ni
el tipo declarado, ni la extension. Lo unico que decide es el contenido.
"""

import csv
import io
from pathlib import PurePath

# Un CSV de catalogo de kiosco no llega a esto ni de casualidad. El tope
# esta para que un archivo grande no se materialice entero en memoria.
LIMITE_BYTES = 2 * 1024 * 1024
MAX_COLUMNAS = 60
MAX_FILAS = 5000


class ArchivoInvalido(Exception):
    """El archivo no se puede procesar."""

    def __init__(self, mensaje: str, codigo: str = "archivo_invalido") -> None:
        """Guarda el mensaje visible y un codigo para el frontend."""
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def nombre_seguro(nombre: str | None) -> str:
    """Reduce un nombre de archivo a su hoja, sin rutas.

    Cierra el recorrido de rutas: "../../app/main.py" queda en "main.py".
    Se usa solo para mostrarlo y registrarlo, nunca para abrir nada.
    """
    if not nombre:
        return "archivo.csv"

    # PurePath no separa por la barra invertida en Linux, asi que se
    # normaliza antes de tomar la hoja.
    plano = nombre.replace("\\", "/")
    hoja = PurePath(plano).name.strip()

    # Un nombre que era solo separadores o referencias al padre queda
    # vacio o en puntos.
    if not hoja or hoja in {".", ".."}:
        return "archivo.csv"
    return hoja[:120]


def _decodificar(contenido: bytes) -> str:
    """Pasa los bytes a texto, probando las codificaciones usuales.

    Las planillas exportadas desde Excel en español suelen venir en
    latin-1, no en UTF-8, asi que se intentan las dos antes de rendirse.
    """
    if b"\x00" in contenido:
        # Un CSV no tiene bytes nulos. Si aparecen, lo que llego es
        # binario con otra extension.
        raise ArchivoInvalido(
            "El archivo no es un CSV de texto.", "no_es_texto"
        )

    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ArchivoInvalido(
        "No se pudo leer el archivo. Guardelo como CSV UTF-8.",
        "codificacion",
    )


def _detectar_separador(muestra: str) -> str:
    """Elige el separador mirando la primera linea.

    Excel en español escribe punto y coma. Elegir mal deja todo en una
    sola columna y el usuario no entiende por que.
    """
    lineas = muestra.splitlines()
    primera = lineas[0] if lineas else ""
    if primera.count(";") > primera.count(","):
        return ";"
    return ","


def leer_csv(contenido: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Devuelve los encabezados y las filas de un CSV.

    Valida el contenido, no la extension ni el tipo declarado. Entrega
    las filas como texto: la conversion a numeros y fechas la hace quien
    conoce el significado de cada columna.
    """
    if not contenido:
        raise ArchivoInvalido("El archivo esta vacio.", "vacio")

    if len(contenido) > LIMITE_BYTES:
        maximo = LIMITE_BYTES // (1024 * 1024)
        raise ArchivoInvalido(
            f"El archivo supera los {maximo} MB.", "demasiado_grande"
        )

    texto = _decodificar(contenido)
    separador = _detectar_separador(texto)
    lector = csv.DictReader(io.StringIO(texto), delimiter=separador)

    encabezados = [(c or "").strip().lower() for c in lector.fieldnames or []]
    if not encabezados or not any(encabezados):
        raise ArchivoInvalido(
            "El archivo no tiene una fila de encabezados.", "sin_encabezados"
        )

    if len(encabezados) > MAX_COLUMNAS:
        raise ArchivoInvalido(
            f"El archivo tiene mas de {MAX_COLUMNAS} columnas.",
            "demasiadas_columnas",
        )

    filas: list[dict[str, str]] = []
    for cruda in lector:
        if len(filas) >= MAX_FILAS:
            raise ArchivoInvalido(
                f"El archivo tiene mas de {MAX_FILAS} filas. "
                "Partalo en varios.",
                "demasiadas_filas",
            )

        # DictReader deja None en la clave cuando la fila trae mas
        # columnas que el encabezado; esas sobras se descartan.
        fila = {
            (clave or "").strip().lower(): (valor or "").strip()
            for clave, valor in cruda.items()
            if clave is not None
        }
        if any(fila.values()):
            filas.append(fila)

    if not filas:
        raise ArchivoInvalido(
            "El archivo no tiene ninguna fila con datos.", "sin_filas"
        )

    return encabezados, filas
