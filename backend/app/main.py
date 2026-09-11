"""Construccion de la aplicacion FastAPI.

La app se arma en una funcion aparte del arranque del servidor para que
las pruebas la monten sin abrir un puerto.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import salud
from app.core.config import get_settings


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
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.origenes_permitidos,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(salud.router)

    return app


app = crear_app()
