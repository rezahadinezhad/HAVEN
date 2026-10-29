#!/usr/bin/env python3
"""Fail-closed structural checks for protected deployment configuration."""

import ipaddress
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


env_file = Path(".env")
require(env_file.is_file(), ".env is missing")
require(stat.S_IMODE(env_file.stat().st_mode) & 0o077 == 0, ".env must have mode 0600")

values: dict[str, str] = {}
for line in env_file.read_text().splitlines():
    if line and not line.startswith("#"):
        key, separator, value = line.partition("=")
        require(bool(separator and key), "Invalid .env line")
        values[key] = value

required = (
    "HAVEN_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "HAVEN_DB_MIGRATION_PASSWORD",
    "HAVEN_DB_RUNTIME_PASSWORD",
    "HAVEN_HOSTS",
    "HAVEN_ORIGINS",
    "HAVEN_TLS_DIR",
)
require(all(key in values for key in required), "Required configuration is missing")
require(len(values["HAVEN_SECRET_KEY"]) >= 48, "Application secret is too short")
passwords = (
    values["POSTGRES_PASSWORD"],
    values["HAVEN_DB_MIGRATION_PASSWORD"],
    values["HAVEN_DB_RUNTIME_PASSWORD"],
)
require(
    all(len(password) >= 32 for password in passwords), "Database password is too short"
)
require(len(set(passwords)) == 3, "Database passwords must be distinct")

hosts = values["HAVEN_HOSTS"].split(",")
optional = values.get("HAVEN_OPTIONAL_HOSTNAME", "")
if optional:
    require(
        optional == optional.lower() and len(optional) <= 253,
        "Invalid optional hostname",
    )
    require(
        all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
            for part in optional.split(".")
        ),
        "Invalid optional hostname",
    )
    require(optional in hosts, "Optional hostname missing from HAVEN_HOSTS")

ip_hosts: list[str] = []
try:
    for host in hosts:
        if optional and host == optional:
            continue
        require(str(ipaddress.IPv4Address(host)) == host, "Noncanonical IPv4 host")
        ip_hosts.append(host)
except ipaddress.AddressValueError:
    raise SystemExit(
        "Only exact IPv4 hosts and the optional hostname are allowed"
    ) from None
require(
    bool(ip_hosts) and len(set(hosts)) == len(hosts),
    "IPv4 host required; duplicates forbidden",
)

origin_hosts: set[str] = set()
for origin in values["HAVEN_ORIGINS"].split(","):
    try:
        parsed = urlsplit(origin)
        require(
            parsed.scheme == "https" and parsed.hostname in hosts,
            "Invalid HTTPS origin",
        )
        require(
            parsed.netloc in (parsed.hostname, f"{parsed.hostname}:{parsed.port}")
            and parsed.port != 0
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
            and not parsed.password,
            "Invalid HTTPS origin",
        )
        origin_hosts.add(parsed.hostname)
    except ValueError:
        raise SystemExit("Invalid HTTPS origin") from None
require(bool(set(ip_hosts) & origin_hosts), "An exact IPv4 HTTPS origin is required")
require(not optional or optional in origin_hosts, "Optional hostname origin is missing")

cert = Path(values["HAVEN_TLS_DIR"])
require(cert.is_absolute(), "HAVEN_TLS_DIR must be absolute")
require(
    (cert / "leaf.crt").is_file() and (cert / "leaf.key").is_file(),
    "TLS leaf/key missing",
)
require(not (cert / "root.key").exists(), "Never mount root CA signing key on server")

for key in ("HAVEN_BRIDGE_TLS_DIR", "HAVEN_DB_TLS_DIR"):
    if values.get(key):
        directory = Path(values[key])
        require(directory.is_absolute(), f"{key} must be absolute")
        require(
            (directory / "leaf.crt").is_file() and (directory / "leaf.key").is_file(),
            f"{key} leaf/key missing",
        )
        require(
            not any(
                (directory / name).exists() for name in ("root.key", "intermediate.key")
            ),
            "Never mount CA signing keys on a server",
        )

print(
    "Basic staging configuration valid; trust-chain and target browser tests still required."
)
