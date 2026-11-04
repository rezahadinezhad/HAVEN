"""An installed profile can route TLS without changing its logical identity."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from haven_client.runtime import profile_upstream


class ProfileTransport(unittest.TestCase):
    def test_existing_profiles_keep_their_endpoint(self):
        upstream = profile_upstream(
            {"api_origin": "https://127.0.0.1:8444", "api_ca": None}
        )
        self.assertEqual(
            (upstream.origin, upstream.address, upstream.port),
            ("https://127.0.0.1:8444", "127.0.0.1", 8444),
        )
        self.assertTrue(upstream.context.check_hostname)

    def test_transport_keeps_origin_host_and_certificate_validation(self):
        upstream = profile_upstream(
            {
                "api_origin": "https://127.0.0.1:8444",
                "api_ca": None,
                "upstream_address": "127.0.0.1",
                "upstream_port": 8449,
            }
        )
        self.assertEqual(upstream.origin, "https://127.0.0.1:8444")
        self.assertEqual(upstream.url.hostname, "127.0.0.1")
        self.assertEqual(upstream.port, 8449)
        self.assertTrue(upstream.context.check_hostname)

    def test_invalid_transport_port_fails_closed(self):
        for port in [0, -1, 65536, True, "8449"]:
            with self.subTest(port=port), self.assertRaises(ValueError):
                profile_upstream(
                    {"api_origin": "https://127.0.0.1:8444", "upstream_port": port}
                )

    def test_invalid_transport_address_fails_closed(self):
        for address in ["", "a\nb", "a b", False]:
            with self.subTest(address=address), self.assertRaises(ValueError):
                profile_upstream(
                    {
                        "api_origin": "https://127.0.0.1:8444",
                        "upstream_address": address,
                    }
                )
