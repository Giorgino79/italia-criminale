import base64

from django.test import override_settings


@override_settings(ACCESSO_PASSWORD="segreta", ACCESSO_UTENTE="demo")
def test_demo_protetta(client, db):
    assert client.get("/metodologia/").status_code == 401
    buono = "Basic " + base64.b64encode(b"demo:segreta").decode()
    sbagliato = "Basic " + base64.b64encode(b"demo:no").decode()
    assert client.get("/metodologia/", HTTP_AUTHORIZATION=sbagliato).status_code == 401
    assert client.get("/metodologia/", HTTP_AUTHORIZATION=buono).status_code == 200
    assert client.get("/admin/login/").status_code == 200


def test_senza_password_sito_aperto(client, db):
    assert client.get("/metodologia/").status_code == 200
