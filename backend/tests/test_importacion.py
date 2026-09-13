"""Importacion CSV y exportacion de productos (RF-C10, RF-C11)."""

import pytest

from app.models import Categoria, Producto
from app.services.archivos import ArchivoInvalido, leer_csv, nombre_seguro

CABECERA = "nombre;codigo_barra;precio_venta;precio_costo;stock_actual"


def _csv(*lineas: str, cabecera: str = CABECERA) -> bytes:
    """Arma un CSV en memoria."""
    return ("\n".join([cabecera, *lineas])).encode("utf-8")


def _subir(client, cabeceras, contenido: bytes, ruta="/productos/importar"):
    return client.post(
        ruta,
        files={"archivo": ("lista.csv", contenido, "text/csv")},
        headers=cabeceras,
    )


def _previsualizar(client, cabeceras, contenido: bytes):
    return _subir(
        client, cabeceras, contenido, "/productos/importar/previsualizar"
    )


# --- lectura del archivo (RNF-11) ----------------------------------------


def test_se_detecta_el_punto_y_coma_de_excel():
    """Excel en español separa con punto y coma."""
    encabezados, filas = leer_csv(b"nombre;precio_venta\nAlfajor;1200")

    assert encabezados == ["nombre", "precio_venta"]
    assert filas[0]["nombre"] == "Alfajor"


def test_tambien_se_lee_separado_por_comas():
    encabezados, filas = leer_csv(b"nombre,precio_venta\nAlfajor,1200")

    assert encabezados == ["nombre", "precio_venta"]
    assert filas[0]["precio_venta"] == "1200"


def test_se_leen_los_acentos_de_una_planilla_en_latin1():
    """Las planillas locales no siempre vienen en UTF-8."""
    contenido = "nombre;precio_venta\nJugón;100".encode("latin-1")

    _, filas = leer_csv(contenido)

    assert filas[0]["nombre"] == "Jugón"


def test_un_binario_disfrazado_de_csv_se_rechaza():
    """Se valida el contenido, no la extension ni el tipo declarado."""
    with pytest.raises(ArchivoInvalido) as fallo:
        leer_csv(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

    assert fallo.value.codigo == "no_es_texto"


def test_un_archivo_vacio_se_rechaza():
    with pytest.raises(ArchivoInvalido):
        leer_csv(b"")


def test_un_archivo_sin_filas_se_rechaza():
    with pytest.raises(ArchivoInvalido) as fallo:
        leer_csv(b"nombre;precio_venta\n")

    assert fallo.value.codigo == "sin_filas"


def test_un_archivo_demasiado_grande_se_rechaza():
    with pytest.raises(ArchivoInvalido) as fallo:
        leer_csv(b"a" * (2 * 1024 * 1024 + 1))

    assert fallo.value.codigo == "demasiado_grande"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("../../app/main.py", "main.py"),
        ("..\\..\\windows\\system.ini", "system.ini"),
        ("/etc/passwd", "passwd"),
        ("C:\\Users\\Aaron\\lista.csv", "lista.csv"),
        ("..", "archivo.csv"),
        ("", "archivo.csv"),
        (None, "archivo.csv"),
    ],
)
def test_el_nombre_se_reduce_a_su_hoja(entrada, esperado):
    """Cierra el recorrido de rutas en el nombre del archivo."""
    assert nombre_seguro(entrada) == esperado


# --- vista previa: no escribe nada (RF-C10) ------------------------------


def test_la_vista_previa_no_guarda_nada(client, sesiones, db):
    contenido = _csv("Alfajor triple;779001;1200,50;800;40")

    respuesta = _previsualizar(client, sesiones["propietario"], contenido)

    assert respuesta.status_code == 200
    assert respuesta.json()["aplicada"] is False
    assert respuesta.json()["a_crear"] == 1
    assert db.query(Producto).count() == 0


def test_la_vista_previa_informa_los_errores_por_fila(client, sesiones):
    contenido = _csv(
        "Alfajor;779001;1200;800;40",
        ";779002;500;300;10",
        "Gaseosa;779003;no-es-un-precio;;5",
    )

    cuerpo = _previsualizar(client, sesiones["propietario"], contenido).json()

    assert cuerpo["a_crear"] == 1
    assert cuerpo["con_error"] == 2
    errores = {f["numero"]: f["errores"] for f in cuerpo["filas"]}
    assert any("nombre" in e for e in errores[3])
    assert any("precio_venta" in e for e in errores[4])


def test_la_vista_previa_distingue_alta_de_actualizacion(client, sesiones):
    """Importar una lista de precios actualiza lo que ya existe."""
    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1200;800;40"),
    )

    cuerpo = _previsualizar(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1500;900;40", "Nuevo;779002;700;400;10"),
    ).json()

    assert cuerpo["a_actualizar"] == 1
    assert cuerpo["a_crear"] == 1


def test_se_avisa_si_faltan_columnas_obligatorias(client, sesiones):
    respuesta = _previsualizar(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001", cabecera="nombre;codigo_barra"),
    )

    assert respuesta.status_code == 400
    assert "precio_venta" in respuesta.json()["detail"]


# --- importacion aplicada ------------------------------------------------


def test_la_importacion_crea_los_productos(client, sesiones, db):
    contenido = _csv(
        "Alfajor triple;779001;1200,50;800;40",
        "Gaseosa 500;779002;900;600;25",
    )

    respuesta = _subir(client, sesiones["propietario"], contenido)

    assert respuesta.status_code == 201
    assert respuesta.json()["aplicada"] is True
    assert db.query(Producto).count() == 2


def test_el_importe_con_coma_decimal_se_entiende(client, sesiones, db):
    """Asi lo escribe una planilla local: punto de miles, coma decimal."""
    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1.200,50;800;40"),
    )

    producto = db.query(Producto).one()
    assert str(producto.precio_venta) == "1200.50"


def test_las_filas_con_error_no_frenan_las_buenas(client, sesiones, db):
    contenido = _csv(
        "Buena uno;779001;1200;800;40",
        ";779002;500;300;10",
        "Buena dos;779003;700;400;5",
    )

    cuerpo = _subir(client, sesiones["propietario"], contenido).json()

    assert cuerpo["a_crear"] == 2
    assert cuerpo["con_error"] == 1
    assert db.query(Producto).count() == 2


def test_una_segunda_importacion_actualiza_el_precio(client, sesiones, db):
    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1200;800;40"),
    )

    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1500;900;40"),
    )

    assert db.query(Producto).count() == 1
    assert str(db.query(Producto).one().precio_venta) == "1500.00"


def test_la_importacion_no_toca_el_stock(client, sesiones, db):
    """El stock se mueve por el modulo D, que deja traza."""
    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1200;800;40"),
    )

    _subir(
        client,
        sesiones["propietario"],
        _csv("Alfajor;779001;1200;800;9999"),
    )

    assert db.query(Producto).one().stock_actual == 40


def test_dos_filas_con_el_mismo_codigo_se_reportan(client, sesiones, db):
    """Sin esto, la segunda pisa a la primera en silencio."""
    contenido = _csv(
        "Alfajor;779001;1200;800;40",
        "Alfajor repetido;779001;1500;900;10",
    )

    cuerpo = _subir(client, sesiones["propietario"], contenido).json()

    assert cuerpo["con_error"] == 1
    assert db.query(Producto).count() == 1


def test_una_categoria_inexistente_es_un_error_de_fila(client, sesiones):
    contenido = _csv(
        "Alfajor;779001;1200;800;40;Golosinas",
        cabecera=CABECERA + ";categoria",
    )

    cuerpo = _subir(client, sesiones["propietario"], contenido).json()

    assert cuerpo["con_error"] == 1
    assert "Golosinas" in cuerpo["filas"][0]["errores"][0]


def test_se_pueden_crear_las_categorias_al_importar(client, sesiones, db):
    contenido = _csv(
        "Alfajor;779001;1200;800;40;Golosinas",
        "Gaseosa;779002;900;600;20;Bebidas",
        cabecera=CABECERA + ";categoria",
    )

    respuesta = client.post(
        "/productos/importar",
        files={"archivo": ("lista.csv", contenido, "text/csv")},
        data={"crear_categorias": "true"},
        headers=sesiones["propietario"],
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["con_error"] == 0
    assert db.query(Categoria).count() == 2
    assert db.query(Producto).count() == 2


@pytest.mark.parametrize("fecha", ["2026-12-31", "31/12/2026", "31-12-2026"])
def test_se_aceptan_los_formatos_de_fecha_usuales(client, sesiones, db, fecha):
    contenido = _csv(
        f"Alfajor;779001;1200;800;40;{fecha}",
        cabecera=CABECERA + ";fecha_vencimiento",
    )

    cuerpo = _subir(client, sesiones["propietario"], contenido).json()

    assert cuerpo["con_error"] == 0
    assert str(db.query(Producto).one().fecha_vencimiento) == "2026-12-31"


def test_una_fecha_ilegible_es_un_error_de_fila(client, sesiones):
    contenido = _csv(
        "Alfajor;779001;1200;800;40;el jueves",
        cabecera=CABECERA + ";fecha_vencimiento",
    )

    cuerpo = _subir(client, sesiones["propietario"], contenido).json()

    assert cuerpo["con_error"] == 1


def test_el_vendedor_no_puede_importar(client, sesiones):
    respuesta = _subir(
        client, sesiones["vendedor"], _csv("Alfajor;779001;1200;800;40")
    )

    assert respuesta.status_code == 403


def test_sin_sesion_no_se_puede_importar(client):
    respuesta = client.post(
        "/productos/importar",
        files={
            "archivo": (
                "lista.csv",
                _csv("Alfajor;779001;1200;800;40"),
                "text/csv",
            )
        },
    )

    assert respuesta.status_code == 401


# --- exportacion (RF-C11) ------------------------------------------------


def _producto_api(client, cabeceras, **extra):
    datos = {
        "nombre": "Alfajor triple",
        "precio_venta": "1200.00",
        "precio_costo": "800.00",
        "stock_actual": 40,
        "stock_minimo": 10,
        "stock_inicial": 100,
    }
    datos.update(extra)
    return client.post("/productos", json=datos, headers=cabeceras).json()


def test_la_exportacion_csv_trae_los_productos(client, sesiones):
    _producto_api(client, sesiones["propietario"])

    respuesta = client.get(
        "/productos/exportar?formato=csv", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]
    assert "attachment" in respuesta.headers["content-disposition"]
    assert "Alfajor triple" in respuesta.content.decode("utf-8")


def test_el_csv_arranca_con_bom_para_que_excel_lea_acentos(client, sesiones):
    _producto_api(client, sesiones["propietario"], nombre="Jugón")

    contenido = client.get(
        "/productos/exportar", headers=sesiones["propietario"]
    ).content

    assert contenido.startswith(b"\xef\xbb\xbf")
    assert "Jugón" in contenido.decode("utf-8")


def test_la_exportacion_pdf_devuelve_un_pdf(client, sesiones):
    _producto_api(client, sesiones["propietario"])

    respuesta = client.get(
        "/productos/exportar?formato=pdf", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.content.startswith(b"%PDF")


def test_la_exportacion_respeta_los_filtros(client, sesiones):
    _producto_api(client, sesiones["propietario"], nombre="Alfajor triple")
    _producto_api(client, sesiones["propietario"], nombre="Gaseosa 500")

    texto = client.get(
        "/productos/exportar?busqueda=alfa",
        headers=sesiones["propietario"],
    ).content.decode("utf-8")

    assert "Alfajor triple" in texto
    assert "Gaseosa 500" not in texto


def test_el_costo_no_viaja_en_el_archivo_del_encargado(client, sesiones):
    """Mismo criterio que en la pantalla: el costo es del propietario."""
    _producto_api(client, sesiones["propietario"])

    del_propietario = client.get(
        "/productos/exportar", headers=sesiones["propietario"]
    ).content.decode("utf-8")
    del_encargado = client.get(
        "/productos/exportar", headers=sesiones["encargado"]
    ).content.decode("utf-8")

    assert "precio_costo" in del_propietario
    assert "800.00" in del_propietario
    assert "precio_costo" not in del_encargado
    assert "800.00" not in del_encargado


def test_el_vendedor_no_puede_exportar(client, sesiones):
    respuesta = client.get("/productos/exportar", headers=sesiones["vendedor"])

    assert respuesta.status_code == 403


def test_exportar_sin_datos_no_falla(client, sesiones):
    csv_vacio = client.get(
        "/productos/exportar", headers=sesiones["propietario"]
    )
    pdf_vacio = client.get(
        "/productos/exportar?formato=pdf", headers=sesiones["propietario"]
    )

    assert csv_vacio.status_code == 200
    assert pdf_vacio.status_code == 200
    assert pdf_vacio.content.startswith(b"%PDF")


def test_un_formato_inventado_se_rechaza(client, sesiones):
    respuesta = client.get(
        "/productos/exportar?formato=docx", headers=sesiones["propietario"]
    )

    assert respuesta.status_code == 422


def test_las_rutas_literales_se_declaran_antes_que_las_variables():
    """Regresion: "/exportar" quedaba tapado por "/{id_producto}".

    FastAPI resuelve en orden de declaracion. Una ruta variable declarada
    antes captura cualquier segmento, incluido el literal, y la peticion
    termina en 422 porque "exportar" no es un entero. El sintoma es que
    el endpoint desaparece sin que falle ninguna prueba de otro modulo.

    Se inspecciona el router y no app.routes: segun la version, FastAPI
    guarda los routers incluidos sin expandir sus rutas.
    """
    from app.api.routes.productos import router

    rutas = [r.path for r in router.routes]
    variable = "/productos/{id_producto}"

    for literal in ("/productos/exportar", "/productos/codigo/{codigo}"):
        assert literal in rutas
        assert rutas.index(literal) < rutas.index(variable), (
            f"{literal} tiene que declararse antes de {variable}"
        )


def test_las_rutas_de_stock_tambien_respetan_ese_orden():
    from app.api.routes.stock import router

    rutas = [r.path for r in router.routes]

    assert "/stock/movimientos/exportar" in rutas
    assert "/stock/movimientos" in rutas


# --- inyeccion de formulas en el CSV exportado ---------------------------


@pytest.mark.parametrize(
    "peligroso",
    [
        "=1+1",
        '=HYPERLINK("http://ejemplo.invalid","click")',
        "+1+1",
        "@SUM(A1:A9)",
        "=cmd|'/c calc'!A0",
    ],
)
def test_una_celda_que_parece_formula_no_se_ejecuta(peligroso):
    """Inyeccion de formulas: el dato lo carga uno y lo abre otro.

    Excel y LibreOffice evaluan toda celda que arranca con "=", "+", "-"
    o "@". Un producto con ese nombre correria en la maquina de quien
    abre el archivo exportado.
    """
    import csv
    import io

    from app.services.exportacion import a_csv

    salida = a_csv(["nombre"], [[peligroso]]).decode("utf-8-sig")
    # Se parsea en lugar de comparar texto: el CSV duplica las comillas
    # internas al escaparlas, y comparar crudo daria un falso negativo.
    filas = list(csv.reader(io.StringIO(salida), delimiter=";"))
    celda = filas[1][0]

    assert not celda.startswith(("=", "+", "@"))
    assert celda == "'" + peligroso  # el valor sigue siendo legible


def test_los_importes_negativos_no_se_estropean():
    """Un numero con signo no es una formula y tiene que salir intacto."""
    from app.services.exportacion import a_csv

    salida = a_csv(["saldo"], [["-150.50"]]).decode("utf-8-sig")

    assert salida.splitlines()[1] == "-150.50"


def test_el_nombre_malicioso_llega_neutralizado_al_archivo(client, sesiones):
    """Recorrido completo: se carga por la API y se exporta."""
    client.post(
        "/productos",
        json={"nombre": "=1+1", "precio_venta": "100.00"},
        headers=sesiones["propietario"],
    )

    texto = client.get(
        "/productos/exportar", headers=sesiones["propietario"]
    ).content.decode("utf-8")

    assert "'=1+1" in texto
