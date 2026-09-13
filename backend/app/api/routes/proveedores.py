"""Endpoints de proveedores y compras (modulo G)."""

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import exigir_gestion
from app.db.session import get_db
from app.models import Usuario
from app.schemas.auth import MensajeSalida
from app.schemas.compra import (
    AnulacionCompraEntrada,
    CompraEntrada,
    CompraResumenSalida,
    CompraSalida,
    ProveedorEntrada,
    ProveedorSalida,
    ResumenProveedorSalida,
)
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.producto import (
    FilaImportadaSalida,
    ImportacionSalida,
    ProductoSalida,
)
from app.services import archivos, exportacion, importacion
from app.services import compras as servicio_compras
from app.services import proveedores as servicio
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(tags=["proveedores"])


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


# --- proveedores (RF-G01, RF-G02, RF-G05) --------------------------------


@router.get("/proveedores", response_model=Pagina[ProveedorSalida])
def listar(
    busqueda: str | None = Query(default=None, max_length=120),
    incluir_inactivos: bool = False,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Pagina[ProveedorSalida]:
    """Listado con busqueda y paginado (RF-G05)."""
    items, total = servicio.listar(
        db,
        busqueda=busqueda,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
    )
    return Pagina[ProveedorSalida](
        items=[ProveedorSalida.model_validate(p) for p in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.post(
    "/proveedores",
    response_model=ProveedorSalida,
    status_code=status.HTTP_201_CREATED,
)
def crear(
    datos: ProveedorEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProveedorSalida:
    """Alta de proveedor (RF-G01)."""
    try:
        proveedor = servicio.crear(db, datos.model_dump(mode="json"))
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return ProveedorSalida.model_validate(proveedor)


# --- importacion y exportacion (RF-G05) ----------------------------------
#
# "/proveedores/exportar" va antes de "/proveedores/{id_proveedor}":
# FastAPI resuelve en orden y la ruta variable se tragaria el literal.


def _leer(archivo: UploadFile) -> list[dict[str, str]]:
    """Lee el CSV subido, o corta la peticion explicando que falta."""
    contenido = archivo.file.read(archivos.LIMITE_BYTES + 1)
    try:
        encabezados, filas = archivos.leer_csv(contenido)
    except archivos.ArchivoInvalido as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    faltantes = importacion.columnas_faltantes_contacto(
        encabezados, "proveedor"
    )
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


def _salida(resultado) -> ImportacionSalida:
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


@router.get("/proveedores/exportar")
def exportar(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    busqueda: str | None = Query(default=None, max_length=120),
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga el listado filtrado en CSV o PDF (RF-G05)."""
    items, _ = servicio.listar(
        db,
        busqueda=busqueda,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=0,
        limite=5000,
    )

    encabezados = [
        "id",
        "razon_social",
        "cuit",
        "contacto",
        "telefono",
        "email",
        "localidad",
        "activo",
    ]
    filas: list[list[object]] = [
        [
            p.id,
            p.razon_social,
            p.cuit,
            p.contacto,
            p.telefono,
            p.email,
            p.localidad,
            p.activo,
        ]
        for p in items
    ]

    if formato == "pdf":
        cuerpo = exportacion.a_pdf("Proveedores", encabezados, filas)
        tipo = "application/pdf"
        nombre = exportacion.nombre_de_archivo("proveedores", "pdf")
    else:
        cuerpo = exportacion.a_csv(encabezados, filas)
        tipo = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo("proveedores", "csv")

    return Response(
        content=cuerpo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post(
    "/proveedores/importar/previsualizar", response_model=ImportacionSalida
)
def previsualizar_importacion(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Dice que pasaria con cada fila, sin escribir nada (RF-G05)."""
    filas = _leer(archivo)
    resultado = importacion.analizar_contactos(db, filas, "proveedor")
    db.rollback()
    return _salida(resultado)


@router.post(
    "/proveedores/importar",
    response_model=ImportacionSalida,
    status_code=status.HTTP_201_CREATED,
)
def importar(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Importa proveedores y saltea las filas con error (RF-G05)."""
    filas = _leer(archivo)
    try:
        resultado = importacion.aplicar_contactos(db, filas, "proveedor")
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _salida(resultado)


@router.get("/proveedores/{id_proveedor}", response_model=ProveedorSalida)
def obtener(
    id_proveedor: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProveedorSalida:
    """Ficha de un proveedor."""
    try:
        proveedor = servicio.obtener(db, id_proveedor)
    except ErrorDeProducto as error:
        raise _error(error) from error
    return ProveedorSalida.model_validate(proveedor)


@router.get(
    "/proveedores/{id_proveedor}/productos",
    response_model=list[ProductoSalida],
)
def productos(
    id_proveedor: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> list[ProductoSalida]:
    """Productos que provee (RF-G02)."""
    try:
        items = servicio.productos_que_provee(db, id_proveedor)
    except ErrorDeProducto as error:
        raise _error(error) from error

    salidas = []
    for producto in items:
        salida = ProductoSalida.model_validate(producto)
        if usuario.puede_administrar:
            salida.margen = producto.margen
        else:
            salida.precio_costo = None
        salidas.append(salida)
    return salidas


@router.get(
    "/proveedores/{id_proveedor}/compras",
    response_model=ResumenProveedorSalida,
)
def resumen(
    id_proveedor: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ResumenProveedorSalida:
    """Cuanto se le compro (RF-G04)."""
    try:
        datos = servicio_compras.resumen_por_proveedor(db, id_proveedor)
    except ErrorDeProducto as error:
        raise _error(error) from error
    return ResumenProveedorSalida(**datos)


@router.put("/proveedores/{id_proveedor}", response_model=ProveedorSalida)
def actualizar(
    id_proveedor: int,
    datos: ProveedorEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ProveedorSalida:
    """Edicion de proveedor (RF-G01)."""
    try:
        proveedor = servicio.actualizar(
            db, id_proveedor, datos.model_dump(mode="json")
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return ProveedorSalida.model_validate(proveedor)


@router.delete("/proveedores/{id_proveedor}", response_model=MensajeSalida)
def eliminar(
    id_proveedor: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MensajeSalida:
    """Baja de proveedor."""
    try:
        _, borrado = servicio.eliminar(db, id_proveedor)
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    if borrado:
        return MensajeSalida(mensaje="El proveedor se elimino.")
    return MensajeSalida(
        mensaje=(
            "El proveedor se desactivo. Tiene compras o productos "
            "asociados, asi que su historial se conserva."
        )
    )


# --- compras (RF-G03, RF-G04) --------------------------------------------


@router.get("/compras", response_model=Pagina[CompraResumenSalida])
def listar_compras(
    id_proveedor: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Pagina[CompraResumenSalida]:
    """Historial de compras (RF-G04)."""
    items, total = servicio_compras.listar(
        db,
        id_proveedor=id_proveedor,
        desde=desde,
        hasta=hasta,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
    )
    return Pagina[CompraResumenSalida](
        items=[CompraResumenSalida.model_validate(c) for c in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


@router.post(
    "/compras",
    response_model=CompraSalida,
    status_code=status.HTTP_201_CREATED,
)
def registrar_compra(
    datos: CompraEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CompraSalida:
    """Registra una compra y da entrada al stock (RF-G03)."""
    lineas = [
        servicio_compras.LineaComprada(
            id_producto=item.id_producto,
            cantidad=item.cantidad,
            costo_unitario=item.costo_unitario,
        )
        for item in datos.items
    ]

    try:
        compra = servicio_compras.registrar(
            db,
            lineas=lineas,
            id_proveedor=datos.id_proveedor,
            usuario=usuario,
            fecha=datos.fecha,
            comprobante=datos.comprobante,
            notas=datos.notas,
            actualizar_costo=datos.actualizar_costo,
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error

    db.commit()
    return CompraSalida.model_validate(compra)


@router.get("/compras/{id_compra}", response_model=CompraSalida)
def obtener_compra(
    id_compra: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CompraSalida:
    """Detalle de una compra."""
    try:
        compra = servicio_compras.obtener(db, id_compra)
    except ErrorDeProducto as error:
        raise _error(error) from error
    return CompraSalida.model_validate(compra)


@router.post("/compras/{id_compra}/anular", response_model=CompraSalida)
def anular_compra(
    id_compra: int,
    datos: AnulacionCompraEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> CompraSalida:
    """Anula una compra y descuenta lo que habia entrado."""
    try:
        compra = servicio_compras.anular(db, id_compra, usuario, datos.motivo)
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return CompraSalida.model_validate(compra)
