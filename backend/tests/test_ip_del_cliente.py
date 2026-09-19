"""De donde sale la IP que cuenta los intentos."""

from starlette.requests import Request

from app.api.deps import ip_del_cliente


def _pedido(reenviada: str | None = None) -> Request:
    cabeceras = []
    if reenviada is not None:
        cabeceras.append((b"x-forwarded-for", reenviada.encode()))
    return Request(
        {
            "type": "http",
            "headers": cabeceras,
            "client": ("172.17.0.1", 5000),
        }
    )


def test_sin_proxy_es_la_conexion():
    assert ip_del_cliente(_pedido()) == "172.17.0.1"


def test_detras_del_proxy_es_la_que_agrega_el_proxy():
    assert ip_del_cliente(_pedido("203.0.113.7")) == "203.0.113.7"


def test_una_ip_inventada_por_el_cliente_no_cuenta():
    """El cliente escribe la primera; la ultima la agrega el proxy."""
    assert ip_del_cliente(_pedido("1.2.3.4, 203.0.113.7")) == "203.0.113.7"


def test_una_cabecera_vacia_cae_en_la_conexion():
    assert ip_del_cliente(_pedido("  ")) == "172.17.0.1"
