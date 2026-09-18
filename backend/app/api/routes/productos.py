"""Endpoints de productos (modulo C)."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    cupo_de_exportacion,
    cupo_de_importacion,
    exigir_gestion,
    obtener_usuario_actual,
)
from app.db.session import get_db
from app.models import Producto, Usuario
from app.schemas.auth import MensajeSalida
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.producto import (
    FilaImportadaSalida,
    ImportacionSalida,
    ProductoEntrada,
    ProductoSalida,
)
from app.services import archivos, exportacion, importacion
from app.services import productos as servicio

router = APIRouter(prefix="/productos", tags=["productos"])

# Un archivo puede traer mas filas que una pantalla, pero no puede
# ser ilimitado: el PDF se arma entero en memoria.
MAX_FILAS_EXPORTACION = 5000


def exportacion_maxima() -> int:
    """Tope de filas que entra en un archivo exportado."""
    return MAX_FILAS_EXPORTACION


def _error(excepcion: servicio.ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, servicio.NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


def _a_salida(producto: Producto, usuario: Usuario) -> ProductoSalida:
    """Arma la respuesta segun lo que el rol puede ver.

    El costo y el margen son informacion del negocio: quien atiende el
    mostrador no tiene por que saber cuanto se gana con cada articulo
    (RF-H06 y la matriz de permisos).
    """
    salida = ProductoSalida.model_validate(producto)
    if not usuario.puede_administrar:
        salida.precio_costo = None
        salida.margen = None
    else:
        salida.margen = producto.margen
    return salida


@router.get("", response_model=Pagina[ProductoSalida])
def listar(
    busqueda: str | None = Query(default=None, max_length=120),
    id_categoria: int | None = None,
    solo_bajo_minimo: bool = False,
    incluir_inactivos: bool = False,
    orden: str = Query(default="nombre", pattern="^(nombre|precio|stock)$"),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Pagina[ProductoSalida]:
    """Listado con busqueda, filtros y paginado (RF-C08)."""
    items, total = servicio.listar_productos(
        db,
        busqueda=busqueda,
        id_categoria=id_categoria,
        solo_bajo_minimo=solo_bajo_minimo,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
        orden=orden,
        id_sesion_demo=usuario.id_sesion_demo,
    )
    return Pagina[ProductoSalida](
        items=[_a_salida(p, usuario) for p in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.get("/codigo/{codigo}", response_model=ProductoSalida)
def por_codigo(
    codigo: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> ProductoSalida:
    """Busqueda por codigo de barras, para el lector (RF-E02)."""
    try:
        producto = servicio.buscar_por_codigo(
            db, codigo, usuario.id_sesion_demo
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    return _a_salida(producto, usuario)


# --- exportacion (RF-C11) ------------------------------------------------

ENCABEZADOS_EXPORTACION = [
    "id",
    "codigo_barra",
    "nombre",
    "categoria",
    "precio_venta",
    "stock_actual",
    "stock_minimo",
    "estado_stock",
    "vencimiento",
    "activo",
]


@router.get("/exportar", dependencies=[Depends(cupo_de_exportacion)])
def exportar(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    busqueda: str | None = Query(default=None, max_length=120),
    id_categoria: int | None = None,
    solo_bajo_minimo: bool = False,
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga el listado filtrado en CSV o PDF (RF-C11).

    Respeta los mismos filtros que el listado, para que lo que se
    descarga sea lo que se esta viendo.
    """
    items, _ = servicio.listar_productos(
        db,
        busqueda=busqueda,
        id_categoria=id_categoria,
        solo_bajo_minimo=solo_bajo_minimo,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=0,
        limite=exportacion_maxima(),
        id_sesion_demo=usuario.id_sesion_demo,
    )

    encabezados = list(ENCABEZADOS_EXPORTACION)
    filas: list[list[object]] = []
    for p in items:
        fila: list[object] = [
            p.id,
            p.codigo_barra,
            p.nombre,
            p.categoria.nombre if p.categoria else None,
            p.precio_venta,
            p.stock_actual,
            p.stock_minimo,
            p.estado_stock,
            p.fecha_vencimiento,
            p.activo,
        ]
        filas.append(fila)

    # El costo solo viaja en el archivo del propietario, igual que en la
    # pantalla.
    if usuario.puede_administrar:
        encabezados.extend(["precio_costo", "margen"])
        for fila, p in zip(filas, items, strict=True):
            fila.extend([p.precio_costo, p.margen])

    if formato == "pdf":
        cuerpo = exportacion.a_pdf("Productos", encabezados, filas)
        tipo = "application/pdf"
        nombre = exportacion.nombre_de_archivo("productos", "pdf")
    else:
        cuerpo = exportacion.a_csv(encabezados, filas)
        tipo = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo("productos", "csv")

    return Response(
        content=cuerpo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


# Las rutas de segmento literal van ANTES de las variables: FastAPI
# resuelve en orden de declaracion, y "/{id_producto}" captura
# cualquier segmento, incluido "exportar", que luego no puede
# convertir a entero y responde 422.
@router.get("/{id_producto}", response_model=ProductoSalida)
def obtener(
    id_producto: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> ProductoSalida:
    """Ficha de un producto."""
    try:
        producto = servicio.obtener_producto(
            db, id_producto, usuario.id_sesion_demo
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    return _a_salida(producto, usuario)


@router.post(
    "", response_model=ProductoSalida, status_code=status.HTTP_201_CREATED
)
def crear(
    datos: ProductoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProductoSalida:
    """Alta de producto. Propietario o encargado (RF-C01)."""
    try:
        producto = servicio.crear_producto(
            db, datos.model_dump(), id_sesion_demo=usuario.id_sesion_demo
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return _a_salida(producto, usuario)


@router.put("/{id_producto}", response_model=ProductoSalida)
def actualizar(
    id_producto: int,
    datos: ProductoEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProductoSalida:
    """Edicion de producto. Propietario o encargado (RF-C01)."""
    cambios = datos.model_dump()
    if (
        not usuario.puede_administrar
        or "precio_costo" not in datos.model_fields_set
    ):
        # El costo solo lo cambia quien puede verlo, y solo si lo mando:
        # si no, el valor por defecto del esquema (cero) lo borraria.
        cambios.pop("precio_costo")
    try:
        producto = servicio.actualizar_producto(
            db,
            id_producto,
            cambios,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return _a_salida(producto, usuario)


@router.delete("/{id_producto}", response_model=MensajeSalida)
def eliminar(
    id_producto: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MensajeSalida:
    """Baja de producto. Propietario o encargado (RF-C09)."""
    try:
        _, borrado = servicio.eliminar_producto(
            db, id_producto, usuario.id_sesion_demo
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    if borrado:
        return MensajeSalida(mensaje="El producto se elimino.")
    return MensajeSalida(
        mensaje=(
            "El producto se desactivo. Tiene ventas o movimientos "
            "registrados, asi que su historial se conserva."
        )
    )


@router.post("/{id_producto}/reactivar", response_model=ProductoSalida)
def reactivar(
    id_producto: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProductoSalida:
    """Vuelve a poner en circulacion un producto dado de baja."""
    try:
        producto = servicio.reactivar_producto(
            db, id_producto, usuario.id_sesion_demo
        )
    except servicio.ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return _a_salida(producto, usuario)


# --- importacion masiva (RF-C10) -----------------------------------------


def _leer_archivo(archivo: UploadFile) -> list[dict[str, str]]:
    """Lee el CSV subido y devuelve sus filas, o corta la peticion."""
    contenido = archivo.file.read(archivos.LIMITE_BYTES + 1)
    try:
        encabezados, filas = archivos.leer_csv(contenido)
    except archivos.ArchivoInvalido as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    faltantes = importacion.columnas_faltantes(encabezados)
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Faltan columnas obligatorias: "
                + ", ".join(sorted(faltantes))
                + "."
            ),
        )
    return filas


def _a_salida_importacion(
    resultado: importacion.ResultadoImportacion,
) -> ImportacionSalida:
    """Arma la respuesta de una importacion."""
    return ImportacionSalida(
        aplicada=resultado.aplicada,
        a_crear=resultado.a_crear,
        a_actualizar=resultado.a_actualizar,
        con_error=resultado.con_error,
        filas=[
            FilaImportadaSalida(
                numero=f.numero,
                accion=f.accion,
                nombre=f.nombre,
                codigo_barra=f.codigo_barra,
                errores=f.errores,
            )
            for f in resultado.filas
        ],
    )


@router.post(
    "/importar/previsualizar",
    response_model=ImportacionSalida,
    dependencies=[Depends(cupo_de_importacion)],
)
def previsualizar_importacion(
    archivo: UploadFile = File(...),
    crear_categorias: bool = Form(default=False),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Dice que pasaria con cada fila, sin escribir nada (RF-C10)."""
    filas = _leer_archivo(archivo)
    resultado = importacion.analizar(
        db,
        filas,
        crear_categorias=crear_categorias,
        id_sesion_demo=usuario.id_sesion_demo,
    )
    # Nada que deshacer: analizar no escribe. El rollback esta por si
    # alguna lectura abrio una transaccion.
    db.rollback()
    return _a_salida_importacion(resultado)


@router.post(
    "/importar",
    response_model=ImportacionSalida,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(cupo_de_importacion)],
)
def importar(
    archivo: UploadFile = File(...),
    crear_categorias: bool = Form(default=False),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Aplica la importacion y saltea las filas con error (RF-C10)."""
    filas = _leer_archivo(archivo)
    try:
        resultado = importacion.aplicar(
            db,
            filas,
            usuario,
            crear_categorias=crear_categorias,
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except servicio.ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _a_salida_importacion(resultado)
