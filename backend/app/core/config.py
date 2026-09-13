"""Configuracion de la aplicacion, leida del entorno.

La clave de firma no tiene valor por defecto (RNF-01): si falta, la
aplicacion no arranca. Es preferible a firmar tokens con una cadena que
esta publicada en el repositorio.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cadenas que son claramente relleno y no secretos. Se rechazan aunque
# vengan del entorno: un despliegue con una de estas es equivalente a no
# tener clave.
_SECRETOS_DE_RELLENO = {
    "change-me",
    "changeme",
    "change_me",
    "changethis",
    "secret",
    "secret-key",
    "clave",
    "cambiar",
    "test",
    "todo",
    "stockarg",
}


class Settings(BaseSettings):
    """Parametros de ejecucion del backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "StockARG"
    app_version: str = "2.0.0"

    # "development" o "production". Solo decide que se expone: los
    # controles de seguridad se aplican en ambos, de modo que un valor
    # mal escrito no puede apagar ninguna proteccion.
    environment: str = "development"

    # --- sesion ---------------------------------------------------------
    # 32 caracteres es el piso para una clave HMAC-SHA256: por
    # debajo, la clave tiene menos entropia que el hash que firma.
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 60 * 12

    # --- base de datos --------------------------------------------------
    database_url: str = (
        "postgresql+psycopg://stockarg:stockarg@127.0.0.1:5432/stockarg"
    )

    # --- frontend y CORS ------------------------------------------------
    # Sin comodines (RNF-04): se enumeran los origenes admitidos.
    allowed_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    frontend_url: str = "http://127.0.0.1:3000"

    # --- documentacion de la API ----------------------------------------
    # /docs, /redoc y /openapi.json son un inventario de la API. En
    # produccion quedan cerrados salvo que se abran a proposito (RNF-03).
    expose_api_docs: bool | None = None

    # --- proteccion de fuerza bruta (RF-A05) ----------------------------
    # Los valores replican los de la version de escritorio: cinco
    # intentos y diez minutos de bloqueo.
    login_max_intentos: int = 5
    login_bloqueo_minutos: int = 10
    login_max_intentos_por_ip: int = 40
    login_ventana_ip_segundos: int = 900

    # --- reglas de negocio configurables --------------------------------
    # Ventana de aviso de vencimiento (RF-B04) y umbrales del estado de
    # stock (RF-D01), que en la app de escritorio estan fijos en 30 y 54.
    dias_proximo_vencimiento: int = 30
    stock_umbral_bajo: int = 30
    stock_umbral_medio: int = 54

    # --- limites de caja (modulo E) -------------------------------------
    # Quien atiende el mostrador vende al precio de lista. Sin un tope,
    # un vendedor puede escribir precio 1 o descontar el total y llevarse
    # la mercaderia: el stock se descuenta igual y el inventario cuadra,
    # asi que la perdida no aparece hasta el cierre de caja. Es el fraude
    # de caja mas comun en un comercio.
    descuento_max_vendedor_porcentaje: int = 10
    vendedor_puede_pactar_precio: bool = False

    # --- correo y Google ------------------------------------------------
    sendgrid_api_key: str | None = None
    email_from: str = "no-reply@stockarg.local"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None

    # --- demo publica (modulo J) ----------------------------------------
    demo_enabled: bool = True
    demo_session_ttl_minutes: int = 45
    demo_idle_timeout_minutes: int = 20
    demo_max_active_sessions: int = 200
    demo_rate_limit_per_hour: int = 12
    demo_cleanup_interval_seconds: int = 300
    demo_maintenance_token: str | None = None
    # Cupos por sandbox (RF-J06): acotan lo que un visitante anonimo
    # puede escribir en la base y pedirle al servidor.
    demo_max_productos: int = 300
    demo_max_ventas: int = 800
    demo_max_importaciones: int = 15
    demo_max_exportaciones: int = 40

    @field_validator("secret_key")
    @classmethod
    def _rechazar_relleno(cls, valor: str) -> str:
        """Rechaza claves de relleno conocidas."""
        if valor.strip().lower() in _SECRETOS_DE_RELLENO:
            raise ValueError(
                "secret_key es un valor de relleno. Genere uno con: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return valor

    @model_validator(mode="after")
    def _validar_umbrales_de_stock(self) -> "Settings":
        """Comprueba que los umbrales describan tres tramos reales.

        Invertirlos no rompe nada de forma visible: la aplicacion
        arranca y el panel de stock pinta los colores al reves, o deja
        un estado inalcanzable. Es el tipo de error de configuracion que
        se descubre tarde y mal, asi que se rechaza al arrancar.
        """
        bajo, medio = self.stock_umbral_bajo, self.stock_umbral_medio
        if not 0 <= bajo < medio <= 100:
            raise ValueError(
                "Los umbrales de stock deben cumplir "
                f"0 <= bajo < medio <= 100. Recibido: bajo={bajo}, "
                f"medio={medio}."
            )
        return self

    @model_validator(mode="after")
    def _validar_tope_de_descuento(self) -> "Settings":
        """El tope de descuento es un porcentaje entre 0 y 100."""
        if not 0 <= self.descuento_max_vendedor_porcentaje <= 100:
            raise ValueError(
                "descuento_max_vendedor_porcentaje debe estar entre 0 y 100."
            )
        return self

    @model_validator(mode="after")
    def _validar_ventanas_de_la_demo(self) -> "Settings":
        """Una demo que caduca antes de empezar no sirve a nadie."""
        if self.demo_session_ttl_minutes < 1:
            raise ValueError(
                "demo_session_ttl_minutes debe ser al menos 1 minuto."
            )
        if self.demo_idle_timeout_minutes < 1:
            raise ValueError(
                "demo_idle_timeout_minutes debe ser al menos 1 minuto."
            )
        # Un cupo en cero no apaga la demo: la deja inservible sin
        # decirlo. Para apagarla esta demo_enabled.
        for nombre in (
            "demo_max_active_sessions",
            "demo_rate_limit_per_hour",
            "demo_max_productos",
            "demo_max_ventas",
            "demo_max_importaciones",
            "demo_max_exportaciones",
        ):
            if getattr(self, nombre) < 1:
                raise ValueError(f"{nombre} debe ser al menos 1.")
        return self

    @property
    def es_produccion(self) -> bool:
        """True cuando el entorno declarado es produccion."""
        return self.environment.strip().lower() == "production"

    @property
    def mostrar_documentacion(self) -> bool:
        """Decide si se publican /docs, /redoc y /openapi.json."""
        if self.expose_api_docs is not None:
            return self.expose_api_docs
        return not self.es_produccion

    @property
    def origenes_permitidos(self) -> list[str]:
        """Lista de origenes admitidos por CORS."""
        return [
            origen.strip()
            for origen in self.allowed_origins.split(",")
            if origen.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion, construida una sola vez."""
    return Settings()
