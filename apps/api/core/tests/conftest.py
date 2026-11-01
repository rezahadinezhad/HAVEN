import secrets
import pytest
from django.core.cache import cache
from core.models import User
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def reset_cache():
    cache.clear()


@pytest.fixture
def credentials(db):
    pw = secrets.token_urlsafe(28)
    user = User.objects.create_user(username="owner", password=pw, display_name="Owner", role="superadmin")
    return user, pw


@pytest.fixture
def client():
    c = APIClient(enforce_csrf_checks=True)
    c.defaults.update(HTTP_HOST="127.0.0.1:8443", HTTP_ORIGIN="https://127.0.0.1:8443")
    return c


def csrf(c):
    return c.get("/api/v1/auth/csrf", secure=True).json()["csrf"]


def post(c, path, value):
    return c.post("/api/v1/" + path, value, format="json", secure=True, HTTP_X_CSRFTOKEN=csrf(c))


def login(c, credentials):
    u, pw = credentials
    return post(c, "auth/login", {"username": u.username, "password": pw})


@pytest.fixture
def migration_database(transactional_db):
    """Forward-only migration tests use a fresh synthetic DB, never reverse data loss."""
    import psycopg
    from psycopg import sql
    from django.db import connection

    config = connection.settings_dict
    original = config["NAME"]
    assert original.startswith("test_") and config["HOST"] == "127.0.0.1"
    name = "test_haven_migration_" + secrets.token_hex(8)
    with psycopg.connect(
        dbname=original,
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
        autocommit=True,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        connection.close()
        config["NAME"] = name
        try:
            yield
        finally:
            connection.close()
            config["NAME"] = original
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
