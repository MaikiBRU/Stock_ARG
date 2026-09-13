"""Endpoints de clientes (modulo F)."""

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

from app.api.deps import (
    cupo_de_exportacion,
    cupo_de_importacion,
    exigir_gestion,
    obtener_usuario_actual,
)
from app.db.session import get_db
from app.models import Usuario
from app.schemas.auth import MensajeSalida
from app.schemas.comunes import LIMITE_MAXIMO, LIMITE_POR_DEFECTO, Pagina
from app.schemas.producto import FilaImportadaSalida, ImportacionSalida
from app.schemas.venta import (
    ClienteEntrada,
    ClienteSalida,
    ResumenComprasSalida,
)
from app.services import archivos, exportacion, importacion
from app.services import clientes as servicio
from app.services.productos import ErrorDeProducto, NoEncontrado

router = APIRouter(prefix="/clientes", tags=["clientes"])


def _error(excepcion: ErrorDeProducto) -> HTTPException:
    """Traduce una falla del servicio a una respuesta HTTP."""
    codigo = (
        status.HTTP_404_NOT_FOUND
        if isinstance(excepcion, NoEncontrado)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=codigo, detail=excepcion.mensaje)


@router.get("", response_model=Pagina[ClienteSalida])
def listar(
    busqueda: str | None = Query(default=None, max_length=120),
    incluir_inactivos: bool = False,
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> Pagina[ClienteSalida]:
    """Listado con busqueda y paginado (RF-F04).

    Lo puede consultar cualquier rol: quien cobra necesita buscar al
    cliente para asociarlo al ticket (RF-E07).
    """
    items, total = servicio.listar(
        db,
        busqueda=busqueda,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=(pagina - 1) * limite,
        limite=limite,
        id_sesion_demo=usuario.id_sesion_demo,
    )
    return Pagina[ClienteSalida](
        items=[ClienteSalida.model_validate(c) for c in items],
        total=total,
        pagina=pagina,
        limite=limite,
    )


# --- importacion y exportacion (RF-F05) ----------------------------------
#
# "/exportar" se declara antes de "/{id_cliente}": FastAPI resuelve en
# orden y la ruta variable se tragaria el segmento literal.


def _leer(archivo: UploadFile, tipo: str) -> list[dict[str, str]]:
    """Lee el CSV subido, o corta la peticion explicando que falta."""
    contenido = archivo.file.read(archivos.LIMITE_BYTES + 1)
    try:
        encabezados, filas = archivos.leer_csv(contenido)
    except archivos.ArchivoInvalido as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error.mensaje
        ) from error

    faltantes = importacion.columnas_faltantes_contacto(encabezados, tipo)
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


@router.get("/exportar", dependencies=[Depends(cupo_de_exportacion)])
def exportar(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    busqueda: str | None = Query(default=None, max_length=120),
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> Response:
    """Descarga el listado filtrado en CSV o PDF (RF-F05)."""
    items, _ = servicio.listar(
        db,
        busqueda=busqueda,
        incluir_inactivos=incluir_inactivos,
        desplazamiento=0,
        limite=5000,
        id_sesion_demo=usuario.id_sesion_demo,
    )

    encabezados = [
        "id",
        "nombre",
        "apellido",
        "documento",
        "cuit",
        "telefono",
        "email",
        "localidad",
        "activo",
    ]
    filas: list[list[object]] = [
        [
            c.id,
            c.nombre,
            c.apellido,
            c.documento,
            c.cuit,
            c.telefono,
            c.email,
            c.localidad,
            c.activo,
        ]
        for c in items
    ]

    if formato == "pdf":
        cuerpo = exportacion.a_pdf("Clientes", encabezados, filas)
        tipo = "application/pdf"
        nombre = exportacion.nombre_de_archivo("clientes", "pdf")
    else:
        cuerpo = exportacion.a_csv(encabezados, filas)
        tipo = "text/csv; charset=utf-8"
        nombre = exportacion.nombre_de_archivo("clientes", "csv")

    return Response(
        content=cuerpo,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post(
    "/importar/previsualizar",
    response_model=ImportacionSalida,
    dependencies=[Depends(cupo_de_importacion)],
)
def previsualizar_importacion(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Dice que pasaria con cada fila, sin escribir nada (RF-F05)."""
    filas = _leer(archivo, "cliente")
    resultado = importacion.analizar_contactos(
        db, filas, "cliente", id_sesion_demo=usuario.id_sesion_demo
    )
    db.rollback()
    return _salida(resultado)


@router.post(
    "/importar",
    response_model=ImportacionSalida,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(cupo_de_importacion)],
)
def importar(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ImportacionSalida:
    """Importa clientes y saltea las filas con error (RF-F05)."""
    filas = _leer(archivo, "cliente")
    try:
        resultado = importacion.aplicar_contactos(
            db, filas, "cliente", id_sesion_demo=usuario.id_sesion_demo
        )
    except ErrorDeProducto as error:
        db.rollback()
        raise _error(error) from error
    db.commit()
    return _salida(resultado)


@router.get("/{id_cliente}", response_model=ClienteSalida)
def obtener(
    id_cliente: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual),
) -> ClienteSalida:
    """Ficha de un cliente."""
    try:
        cliente = servicio.obtener(db, id_cliente, usuario.id_sesion_demo)
    except ErrorDeProducto as error:
        raise _error(error) from error
    return ClienteSalida.model_validate(cliente)


@router.get("/{id_cliente}/compras", response_model=ResumenComprasSalida)
def compras(
    id_cliente: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ResumenComprasSalida:
    """Cuanto y cuando compro un cliente (RF-F03)."""
    try:
        resumen = servicio.resumen_de_compras(
            db, id_cliente, usuario.id_sesion_demo
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    return ResumenComprasSalida(**resumen)


@router.post(
    "", response_model=ClienteSalida, status_code=status.HTTP_201_CREATED
)
def crear(
    datos: ClienteEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ClienteSalida:
    """Alta de cliente. Propietario o encargado (RF-F01)."""
    try:
        cliente = servicio.crear(
            db, datos.model_dump(mode="json"), usuario.id_sesion_demo
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return ClienteSalida.model_validate(cliente)


@router.put("/{id_cliente}", response_model=ClienteSalida)
def actualizar(
    id_cliente: int,
    datos: ClienteEntrada,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> ClienteSalida:
    """Edicion de cliente. Propietario o encargado (RF-F01)."""
    try:
        cliente = servicio.actualizar(
            db,
            id_cliente,
            datos.model_dump(mode="json"),
            id_sesion_demo=usuario.id_sesion_demo,
        )
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    return ClienteSalida.model_validate(cliente)


@router.delete("/{id_cliente}", response_model=MensajeSalida)
def eliminar(
    id_cliente: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_gestion),
) -> MensajeSalida:
    """Baja de cliente. Propietario o encargado."""
    try:
        _, borrado = servicio.eliminar(db, id_cliente, usuario.id_sesion_demo)
    except ErrorDeProducto as error:
        raise _error(error) from error
    db.commit()
    if borrado:
        return MensajeSalida(mensaje="El cliente se elimino.")
    return MensajeSalida(
        mensaje=(
            "El cliente se desactivo. Tiene compras registradas, asi que "
            "su historial se conserva."
        )
    )
