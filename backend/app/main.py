"""Construccion de la aplicacion FastAPI.

La app se arma en una funcion aparte del arranque del servidor para que
las pruebas la monten sin abrir un puerto.
"""

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    administracion,
    auth,
    categorias,
    clientes,
    demo,
    medios_pago,
    productos,
    proveedores,
    reportes,
    salud,
    stock,
    ventas,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import demo as servicio_demo

registro = logging.getLogger("stockarg")


def _limpiar_demo_una_vez() -> int:
    """Borra los sandboxes vencidos con una sesion propia del sistema."""
    with SessionLocal() as sesion:
        return servicio_demo.purgar_vencidas(sesion)


async def _limpiar_demo_periodicamente(intervalo: int) -> None:
    """Limpieza en segundo plano de la demo (RF-J09).

    Si este bucle se cae, la demo sigue siendo correcta: cada peticion
    rechaza por su cuenta las sesiones vencidas. Solo se acumularian
    filas hasta la proxima limpieza.
    """
    while True:
        await asyncio.sleep(intervalo)
        try:
            await run_in_threadpool(_limpiar_demo_una_vez)
        except Exception:
            registro.exception("Fallo la limpieza periodica de la demo.")


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    """Arranca y detiene las tareas de fondo."""
    ajustes = get_settings()
    tarea = None
    if ajustes.demo_enabled and ajustes.demo_cleanup_interval_seconds > 0:
        tarea = asyncio.create_task(
            _limpiar_demo_periodicamente(ajustes.demo_cleanup_interval_seconds)
        )
    try:
        yield
    finally:
        if tarea is not None:
            tarea.cancel()
            with suppress(asyncio.CancelledError):
                await tarea


async def _cupo_agotado(_request: Request, error: Exception) -> JSONResponse:
    """Un cupo de la demo agotado es un 429, no un error del servidor.

    Los topes de filas se controlan al escribir, en cualquier endpoint,
    asi que la excepcion puede venir de cualquier lado.
    """
    detalle = (
        error.detalle()
        if isinstance(error, servicio_demo.CupoAgotado)
        else {"mensaje": str(error)}
    )
    return JSONResponse(status_code=429, content={"detail": detalle})


def _anotar_error(request: Request, error: Exception, referencia: str) -> None:
    """Deja el error en la auditoria, en una sesion propia (RF-I05).

    La sesion de la peticion puede estar rota, justamente por el error,
    asi que se abre una nueva. Se guarda que paso y donde, nunca el
    mensaje: puede traer datos de la operacion que fallo. El detalle
    completo va al log del servidor con la misma referencia.
    """
    from app.api.deps import ip_del_cliente
    from app.services import auditoria

    fabrica = getattr(request.app.state, "sesion_de_sistema", SessionLocal)
    try:
        sesion = fabrica()
        try:
            auditoria.registrar(
                sesion,
                usuario=None,
                accion="error.no_controlado",
                entidad="sistema",
                id_entidad=referencia,
                detalle={
                    "metodo": request.method,
                    "ruta": request.url.path,
                    "tipo": type(error).__name__,
                },
                ip=ip_del_cliente(request),
            )
            sesion.commit()
        finally:
            sesion.close()
    except Exception:
        # Anotar el error no puede provocar otro error.
        registro.exception("No se pudo anotar el error en la auditoria.")


async def _error_no_controlado(
    request: Request, error: Exception
) -> JSONResponse:
    """Responde 500 sin detalles y deja constancia (RF-I05)."""
    referencia = secrets.token_hex(8)
    registro.exception(
        "[%s] Error no controlado en %s %s",
        referencia,
        request.method,
        request.url.path,
    )
    _anotar_error(request, error, referencia)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "mensaje": "Hubo un error inesperado. Ya quedo registrado.",
                "codigo": "error_no_controlado",
                "referencia": referencia,
            }
        },
    )


def crear_app() -> FastAPI:
    """Arma la aplicacion con su configuracion y sus rutas."""
    ajustes = get_settings()
    mostrar_docs = ajustes.mostrar_documentacion

    app = FastAPI(
        title=ajustes.app_name,
        version=ajustes.app_version,
        description=(
            "Gestion de stock, ventas, clientes y proveedores para un comercio."
        ),
        # En produccion los tres quedan en None y FastAPI responde 404
        # a las tres rutas (RNF-03).
        docs_url="/docs" if mostrar_docs else None,
        redoc_url="/redoc" if mostrar_docs else None,
        openapi_url="/openapi.json" if mostrar_docs else None,
        lifespan=_ciclo_de_vida,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.origenes_permitidos,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(servicio_demo.CupoAgotado, _cupo_agotado)
    app.add_exception_handler(Exception, _error_no_controlado)
    # La fabrica de sesiones del sistema se guarda en la app para que las
    # pruebas puedan apuntarla a su propia base.
    app.state.sesion_de_sistema = SessionLocal

    app.include_router(salud.router)
    app.include_router(auth.router)
    app.include_router(categorias.router)
    app.include_router(productos.router)
    app.include_router(stock.router)
    app.include_router(clientes.router)
    app.include_router(medios_pago.router)
    app.include_router(ventas.router)
    app.include_router(proveedores.router)
    app.include_router(reportes.router)
    app.include_router(administracion.router)
    app.include_router(demo.router)

    return app


app = crear_app()
