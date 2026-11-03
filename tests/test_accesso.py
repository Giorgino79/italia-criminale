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


@override_settings(ACCESSO_PASSWORD="segreta")
def test_staff_loggato_entra_senza_seconda_password(client, db):
    from django.contrib.auth.models import User

    User.objects.create_user("giorgio", password="x", is_staff=True)
    client.login(username="giorgio", password="x")
    assert client.get("/metodologia/").status_code == 200


@override_settings(ACCESSO_PASSWORD="segreta")
def test_utente_django_nella_finestra_del_browser(client, db):
    from django.contrib.auth.models import User

    User.objects.create_user("ospite1", password="Pass-123-ok")
    ok = "Basic " + base64.b64encode(b"ospite1:Pass-123-ok").decode()
    no = "Basic " + base64.b64encode(b"ospite1:sbagliata").decode()
    assert client.get("/metodologia/", HTTP_AUTHORIZATION=ok).status_code == 200
    assert client.get("/metodologia/", HTTP_AUTHORIZATION=no).status_code == 401
