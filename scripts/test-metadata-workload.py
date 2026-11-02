#!/usr/bin/env python3
"""Check population, connection, burst and SLO semantics without network fixtures."""

from collections import Counter
import unittest

from metadata_workload import (
    Workload,
    Latency,
    socket_allocation,
    expected_copies,
    verify_envelope,
)


class WorkloadTests(unittest.TestCase):
    def test_real_signatures_reject_wrong_wire_sender_sequence_and_chain(self):
        import base64
        from copy import deepcopy
        import hashlib
        import rfc8785
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.exceptions import InvalidSignature

        key = Ed25519PrivateKey.generate()
        wire = b"synthetic opaque wire: native MLS is checked by integration"
        header = {
            "sender_device": "synthetic-sender",
            "client_message_id": "synthetic-event",
            "previous_hash": "prior",
            "ciphertext_hash": hashlib.sha256(wire).hexdigest(),
        }
        signature = base64.b64encode(key.sign(rfc8785.dumps(header))).decode()
        head = hashlib.sha256(
            rfc8785.dumps({"header": header, "signature": signature})
        ).hexdigest()
        event = {"header": header, "signature": signature, "head": head}
        env = {
            "header": header,
            "seq": 1,
            "sender_device": header["sender_device"],
            "client_message_id": header["client_message_id"],
            "signature": signature,
            "chain_hash": head,
            "ciphertext": base64.b64encode(wire).decode(),
        }
        public = key.public_key().public_bytes_raw()
        self.assertEqual(verify_envelope(env, event, 0, "prior", public), wire)
        mutations = [
            {"seq": 2},
            {"seq": True},
            {"sender_device": "other"},
            {"chain_hash": "other"},
            {"ciphertext": base64.b64encode(b"changed").decode()},
            {"ciphertext": env["ciphertext"] + "!"},
            {"signature": base64.b64encode(bytes(64)).decode()},
        ]
        for mutation in mutations:
            bad = deepcopy(env)
            bad.update(mutation)
            with self.assertRaises((ValueError, InvalidSignature)):
                verify_envelope(bad, event, 0, "prior", public)
        with self.assertRaises(InvalidSignature):
            verify_envelope(
                env,
                event,
                0,
                "prior",
                Ed25519PrivateKey.generate().public_key().public_bytes_raw(),
            )

    def test_author_cycle_is_person_fair_despite_second_online_device(self):
        from metadata_workload import AuthorCycle

        eligible = [
            (u, s) for u in range(100) for s in range(2) if s == 0 or u % 5 == 0
        ]
        first, second = AuthorCycle(100), AuthorCycle(100)
        chosen = [first.choose(eligible) for _ in range(200)]
        self.assertEqual(
            chosen, [second.choose(list(reversed(eligible))) for _ in range(200)]
        )
        self.assertEqual(
            Counter(u for u, _ in chosen), Counter({u: 2 for u in range(100)})
        )
        for user in range(100):
            self.assertEqual(
                [slot for u, slot in chosen if u == user],
                [0, 1] if user % 5 == 0 else [0, 0],
            )
        self.assertNotEqual([u for u, _ in chosen[:100]], list(range(100)))

    def test_author_cycle_excludes_offline_or_cold_devices_without_losing_intents(self):
        from metadata_workload import AuthorCycle

        cycle = AuthorCycle(100)
        eligible = [(u, 1) for u in range(30, 100)]
        chosen = [cycle.choose(eligible) for _ in range(140)]
        self.assertEqual(
            Counter(u for u, _ in chosen), Counter({u: 2 for u in range(30, 100)})
        )
        self.assertTrue(all(slot == 1 for _, slot in chosen))
        with self.assertRaises(ValueError):
            cycle.choose([])
        self.assertEqual(cycle.offered, 140)

    def test_intermittent_population_retains_online_senders_in_affected_chats(self):
        from metadata_workload import intermittent_accounts

        population = Workload().population()
        selected = set(intermittent_accounts(population))
        self.assertEqual(len(selected), 30)
        self.assertEqual(selected, set(intermittent_accounts(population)))
        affected_sizes = set()
        for group in population:
            self.assertTrue(set(group) - selected)
            if set(group) & selected:
                affected_sizes.add(len(group))
        self.assertEqual(affected_sizes, {2, 5})
        self.assertEqual(len(intermittent_accounts(Workload(users=20).population())), 6)

    def test_failure_summary_exports_only_known_labels_and_no_arbitrary_text(self):
        from metadata_workload import safe_failure

        private = "SYNTHETIC-PRIVATE-VALUE-MUST-NOT-APPEAR"
        for error in (
            RuntimeError(private),
            KeyError(private),
            RuntimeError("HTTP 503 on POST conversations " + private),
        ):
            value = safe_failure(error)
            self.assertEqual(value["code"], "UNCLASSIFIED")
            self.assertNotIn(private, str(value))
        self.assertEqual(
            safe_failure(RuntimeError("HTTP 503 on POST conversations"))["status"], 503
        )
        self.assertEqual(
            safe_failure(RuntimeError("Native worker rejected command"))["code"],
            "Native worker rejected command",
        )

    def test_natural_outage_closes_tabs_without_redistributing_them(self):
        from metadata_workload import (
            fixed_socket_allocation,
            default_duration,
            default_rate,
        )

        plan = socket_allocation(range(120), 500)
        during = fixed_socket_allocation(plan, range(85))
        self.assertLess(sum(during.values()), 500)
        self.assertEqual(during, {key: plan[key] for key in range(85)})
        self.assertEqual(fixed_socket_allocation(plan, range(120)), plan)
        with self.assertRaises(ValueError):
            fixed_socket_allocation(plan, range(121))
        natural = Workload(profile="combined-natural", seconds=60, rate=20, files=5)
        self.assertEqual(
            natural.phases(),
            Workload(profile="combined", seconds=60, rate=20, files=5).phases(),
        )
        self.assertEqual(natural.socket_target(120), 500)
        self.assertEqual(
            (default_duration("combined-natural"), default_rate("combined-natural")),
            (60, 20),
        )

    def test_normal_population_is_people_not_connections(self):
        groups = Workload().population()
        self.assertEqual(Counter(map(len, groups)), {2: 40, 5: 4})
        self.assertEqual(sorted(n for group in groups for n in group), list(range(100)))
        self.assertEqual(sum(len(g) * 2 for g in groups), 200)

    def test_burst_is_explicitly_between_warmup_and_recovery(self):
        self.assertEqual(
            Workload(profile="burst", seconds=60, rate=20).phases(),
            [("warmup", 20, 2), ("burst", 60, 20), ("recovery", 30, 2)],
        )
        self.assertEqual(Workload().phases(), [("steady", 7200, 2)])

    def test_combined_preserves_burst_population_and_socket_stress_during_disconnect(
        self,
    ):
        from metadata_workload import default_duration, default_rate

        combined = Workload(profile="combined", seconds=60, rate=20, files=5)
        self.assertEqual(combined.population(), Workload().population())
        self.assertEqual(
            combined.phases(), Workload(profile="burst", seconds=60, rate=20).phases()
        )
        self.assertEqual(
            (default_duration("combined"), default_rate("combined")), (60, 20)
        )
        for online in (120, 84):
            self.assertEqual(
                sum(
                    socket_allocation(
                        range(online), combined.socket_target(online)
                    ).values()
                ),
                500,
            )

    def test_five_hundred_sockets_do_not_create_device_identities(self):
        allocation = socket_allocation(range(120), 500)
        self.assertEqual(len(allocation), 120)
        self.assertEqual(sum(allocation.values()), 500)
        self.assertEqual(set(allocation.values()), {4, 5})
        self.assertEqual(Workload(profile="connections").socket_target(120), 500)

    def test_fanout_varies_with_people_and_members_not_active_sockets(self):
        for size in [5, 10, 25]:
            groups = Workload(profile="group", group_size=size).population()
            self.assertEqual(len(groups), 100 // size)
            events = [{"members": range(size * 2)} for _ in range(20)]
            self.assertEqual(expected_copies(events), 20 * (size * 2 - 1))

    def test_slo_uses_counts_not_averaged_percentiles_or_rounded_means(self):
        sample = Latency(750)
        for _ in range(19):
            sample.add(740)
        sample.add(3000)
        self.assertTrue(sample.snapshot()["p95_budget_pass"])
        self.assertEqual(sample.snapshot()["p95_upper_ms"], 750)
        sample.add(3000)
        self.assertFalse(sample.snapshot()["p95_budget_pass"])

    def test_invalid_population_and_uncovered_connections_fail_closed(self):
        for values in [
            {"users": 101},
            {"users": 11},
            {"rate": 21},
            {"files": 6},
            {"seconds": 0},
            {"sender_workers": 3},
            {"hold_first_ack": "true"},
        ]:
            with self.assertRaises(ValueError):
                Workload(**values)
        for active, target in [(range(120), 100), ([], 500), (range(120), 501)]:
            with self.assertRaises(ValueError):
                socket_allocation(active, target)


if __name__ == "__main__":
    unittest.main()
