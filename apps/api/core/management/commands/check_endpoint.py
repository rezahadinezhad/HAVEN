"""Record an operator-selected IP endpoint only after a real locally trusted TLS/health probe."""

import http.client
import ipaddress
import json
import ssl
from urllib.parse import urlsplit
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.models import BootstrapEndpoint


class Command(BaseCommand):
    help = "Verify an exact HTTPS IPv4 endpoint with an explicitly trusted CA and record operational metadata"

    def add_arguments(self, parser):
        parser.add_argument("url")
        parser.add_argument("--ca-file", required=True)
        parser.add_argument(
            "--tls-profile", choices=["PUBLIC_IP_TLS", "EMERGENCY_PRIVATE_PKI"], required=True
        )
        parser.add_argument("--priority", type=int, default=0)

    def handle(self, *args, **options):
        connection = None
        try:
            parsed = urlsplit(options["url"])
            ipaddress.IPv4Address(parsed.hostname)
            if (
                parsed.scheme != "https"
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port == 0
                or not 0 <= options["priority"] <= 100
            ):
                raise ValueError()
            context = ssl.create_default_context(cafile=options["ca_file"])
            connection = http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443, context=context, timeout=5
            )
            connection.request("GET", "/api/v1/health")
            response = connection.getresponse()
            body = response.read(4097)
            payload = json.loads(body)
            if (
                response.status != 200
                or len(body) > 4096
                or not isinstance(payload, dict)
                or payload.get("status") != "available"
            ):
                raise ValueError()
        except (OSError, ValueError, TypeError, http.client.HTTPException):
            raise CommandError(
                "Endpoint probe rejected. Check exact IPv4 HTTPS URL, trusted CA, certificate validity and service health."
            ) from None
        finally:
            if connection:
                connection.close()
        BootstrapEndpoint.objects.update_or_create(
            url=options["url"],
            defaults={
                "tls_profile": options["tls_profile"],
                "priority": options["priority"],
                "last_validated": timezone.now(),
            },
        )
        self.stdout.write(
            "PASS configured endpoint TLS/health probe. This is not independent identity, phone, carrier, failover or cryptographic qualification."
        )
