"""Salida de tablas a CSV y PDF (RF-C11, RF-D09).

Se genera en el backend y no en el navegador: asi el archivo sale igual
desde cualquier equipo, y el PDF no depende de como imprime cada uno.
"""

import csv
import io

from app.core import tiempo

# Excel en español espera punto y coma, y sin el BOM abre los acentos
# mal. Las dos cosas juntas hacen que el archivo se abra de un doble
# clic sin pasar por el asistente de importacion.
SEPARADOR = ";"
BOM = "﻿"


# Excel y LibreOffice evaluan como formula toda celda que arranque con
# uno de estos. Un producto llamado '=1+1' sale como formula, y uno
# llamado '=HYPERLINK(...)' o '=cmd|...' corre en la maquina de quien
# abre el archivo. El dato lo carga una persona del comercio y lo abre
# otra, asi que el archivo cruza de usuario.
INICIOS_DE_FORMULA = ("=", "+", "-", "@")


def _celda(valor: object) -> str:
    """Pasa un valor a texto para una celda, neutralizando formulas.

    Al texto que arranca como formula se le antepone un apostrofe, que es
    la marca que usan las planillas para decir "esto es texto". Se ve el
    valor original y no se ejecuta nada.
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "si" if valor else "no"

    texto = str(valor)
    # Los numeros propios (importes, cantidades) no pasan por aca como
    # texto, asi que un "-5" escrito por el sistema no se toca: solo se
    # protege lo que vino de un campo de texto.
    if texto.startswith(INICIOS_DE_FORMULA) and not _es_numero(texto):
        return "'" + texto
    return texto


def _es_numero(texto: str) -> bool:
    """True si el texto es un numero y no una formula disfrazada."""
    try:
        float(texto)
    except ValueError:
        return False
    return True


def a_csv(encabezados: list[str], filas: list[list[object]]) -> bytes:
    """Arma un CSV listo para abrir con Excel."""
    buffer = io.StringIO()
    escritor = csv.writer(
        buffer, delimiter=SEPARADOR, quoting=csv.QUOTE_MINIMAL
    )
    escritor.writerow(encabezados)
    for fila in filas:
        escritor.writerow([_celda(v) for v in fila])
    return (BOM + buffer.getvalue()).encode("utf-8")


def a_pdf(
    titulo: str, encabezados: list[str], filas: list[list[object]]
) -> bytes:
    """Arma un PDF apaisado con la tabla.

    reportlab se importa aca y no arriba: es la unica parte del sistema
    que lo necesita, y asi el resto funciona aunque no este instalado.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=titulo,
    )

    estilos = getSampleStyleSheet()
    partes = [
        Paragraph(titulo, estilos["Title"]),
        Paragraph(
            "StockARG &mdash; "
            + tiempo.en_zona(tiempo.ahora()).strftime("%d/%m/%Y %H:%M"),
            estilos["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]

    datos = [encabezados] + [[_celda(v) for v in fila] for fila in filas]
    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f3f4f6")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    partes.append(tabla)

    if not filas:
        partes.append(Spacer(1, 4 * mm))
        partes.append(
            Paragraph(
                "No hay datos para el filtro aplicado.", estilos["Italic"]
            )
        )

    documento.build(partes)
    return buffer.getvalue()


def nombre_de_archivo(base: str, extension: str) -> str:
    """Nombre con la fecha, para que no se pisen las descargas."""
    marca = tiempo.en_zona(tiempo.ahora()).strftime("%Y%m%d-%H%M")
    return f"{base}-{marca}.{extension}"
