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
