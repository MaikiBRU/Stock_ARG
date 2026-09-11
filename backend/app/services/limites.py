"""Limite de intentos por ventana de tiempo (RNF-05).

Vive en la memoria del proceso. Con una sola instancia de la API, que es
el despliegue previsto, alcanza. Si algun dia hay mas de una, el limite
pasa a ser por instancia: esta anotado como limitacion conocida y no
como descuido.
"""

import threading
import time
from collections import defaultdict

from app.core.security import hash_opaco


class LimitadorDeIntentos:
    """Cuenta intentos por clave dentro de una ventana deslizante."""

    def __init__(self) -> None:
        """Prepara el registro vacio."""
        self._intentos: dict[str, list[float]] = defaultdict(list)
        # Los workers de uvicorn comparten el proceso: sin el candado,
        # dos peticiones simultaneas pueden leer la misma cuenta y dejar
        # pasar un intento de mas.
        self._candado = threading.Lock()

    def _purgar(self, clave: str, ventana: int, ahora: float) -> list[float]:
        vigentes = [
            momento
            for momento in self._intentos[clave]
            if ahora - momento < ventana
        ]
        self._intentos[clave] = vigentes
        return vigentes

    def permitido(self, clave: str, maximo: int, ventana: int) -> bool:
        """Registra un intento y dice si esta dentro del limite."""
        ahora = time.monotonic()
        with self._candado:
            vigentes = self._purgar(clave, ventana, ahora)
            if len(vigentes) >= maximo:
                return False
            vigentes.append(ahora)
            return True

    def restantes(self, clave: str, maximo: int, ventana: int) -> int:
        """Intentos que quedan, sin consumir ninguno."""
        with self._candado:
            usados = len(self._purgar(clave, ventana, time.monotonic()))
        return max(0, maximo - usados)

    def limpiar(self, clave: str) -> None:
        """Olvida los intentos de una clave.

        Se llama tras un ingreso correcto: quien escribio mal la clave
        tres veces y despues acerto no tiene por que arrastrar esas
        marcas.
        """
        with self._candado:
            self._intentos.pop(clave, None)

    def reiniciar(self) -> None:
        """Vacia todo el registro. Para las pruebas."""
        with self._candado:
            self._intentos.clear()


limitador = LimitadorDeIntentos()


def clave_de_ip(ip: str | None, accion: str) -> str:
    """Arma la clave de una IP, sin guardar la direccion en claro."""
    if not ip:
        return f"{accion}:desconocida"
    return f"{accion}:{hash_opaco(ip)}"
