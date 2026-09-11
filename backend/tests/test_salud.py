def test_salud_responde_con_la_base_conectada(client):
    respuesta = client.get("/salud")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ok"] is True
    assert cuerpo["sistema"] == "StockARG"
    assert cuerpo["base_de_datos"] == "conectada"


def test_salud_no_revela_la_cadena_de_conexion(client):
    cuerpo = client.get("/salud").json()

    assert "://" not in str(cuerpo)
