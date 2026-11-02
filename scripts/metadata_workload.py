"""Explicit native workload definitions; no Django, network or fixture side effects."""

from dataclasses import dataclass
from bisect import bisect_left

PROFILES = (
    "realistic",
    "burst",
    "combined",
    "combined-natural",
    "handoff",
    "intermittent",
    "connections",
    "group",
    "legacy-stress",
)


@dataclass(frozen=True)
class Workload:
    profile: str = "realistic"
    users: int = 100
    seconds: int = 7200
    rate: float = 2
    group_size: int = 10
    files: int = 0
    rekey_every: int = 100
    warmup: int = 20
    recovery: int = 30
    sender_workers: int = 2
    hold_first_ack: bool = False

    def __post_init__(self):
        if self.sender_workers not in (1, 2) or type(self.hold_first_ack) is not bool:
            raise ValueError(
                "Use one/two bounded author workers and an explicit boolean ACK probe"
            )
        if self.profile not in PROFILES:
            raise ValueError("Unknown workload profile")
        if not 10 <= self.users <= 100 or self.users % 2:
            raise ValueError("Use an even synthetic population of 10–100 accounts")
        if not 1 <= self.seconds <= 7200 or not 0 < self.rate <= 20:
            raise ValueError("Use 1–7200 seconds and a rate above zero through 20/s")
        if not 2 <= self.group_size <= 50 or not 0 <= self.files <= 5:
            raise ValueError("Use 2–50 users per group and 0–5 files")
        if not 1 <= self.rekey_every <= 1000:
            raise ValueError("Use 1–1000 applications per rekey")
        if not 0 <= self.warmup <= 600 or not 0 <= self.recovery <= 600:
            raise ValueError("Warm-up/recovery must be 0–600 seconds")

    def population(self):
        """Disjoint conversations keep each native device's provider/checkpoint ordered."""
        if self.profile == "group":
            sizes = [self.group_size] * (self.users // self.group_size)
            remainder = self.users % self.group_size
            if remainder == 1:
                raise ValueError("Group profile cannot leave a single user")
            if remainder:
                sizes.append(remainder)
        else:
            direct_users = (self.users * 4 // 5) // 2 * 2
            sizes = [2] * (direct_users // 2)
            left = self.users - direct_users
            while left:
                size = min(5, left)
                if left - size == 1:
                    size -= 1
                sizes.append(size)
                left -= size
        result, offset = [], 0
        for size in sizes:
            result.append(tuple(range(offset, offset + size)))
            offset += size
        assert offset == self.users and all(len(group) >= 2 for group in result)
        return result

    def phases(self):
        if self.profile in ("burst", "group", "combined", "combined-natural"):
            return [
                ("warmup", self.warmup, 2.0),
                ("burst", self.seconds, self.rate),
                ("recovery", self.recovery, 2.0),
            ]
        return [("steady", self.seconds, self.rate)]

    def socket_target(self, online_devices):
        return (
            500
            if self.profile in ("connections", "combined", "combined-natural")
            else online_devices
        )


def default_duration(profile):
    return {
        "realistic": 7200,
        "burst": 60,
        "combined": 60,
        "combined-natural": 60,
        "group": 60,
        "legacy-stress": 120,
    }.get(profile, 300)


def default_rate(profile):
    return (
        20
        if profile
        in ("burst", "group", "combined", "combined-natural", "legacy-stress")
        else 2
    )


AUTHOR_SEED = 20261102


class AuthorCycle:
    """One opportunity per online person, rotating that person's ready devices.

    Fixed seed is not searched/tuned against benchmark outcomes. Keeping a
    second device online must not double the person's application-message rate.
    """

    def __init__(self, users):
        import random

        self.order = list(range(users))
        random.Random(AUTHOR_SEED).shuffle(self.order)
        self.device_turns = {}
        self.offered = 0

    def choose(self, eligible):
        available = {}
        for user, slot in eligible:
            available.setdefault(user, set()).add(slot)
        active = [user for user in self.order if user in available]
        if not active:
            raise ValueError("No online, caught-up author")
        user = active[self.offered % len(active)]
        devices = sorted(available[user])
        turn = self.device_turns.get(user, 0)
        slot = devices[turn % len(devices)]
        self.device_turns[user] = turn + 1
        self.offered += 1
        return user, slot


def intermittent_accounts(population):
    """Thirty percent disconnect, retaining an online peer in every conversation."""
    import random
    from collections import Counter

    group_for = {
        user: index for index, members in enumerate(population) for user in members
    }
    candidates = list(group_for)
    random.Random(AUTHOR_SEED + 1).shuffle(candidates)
    target, counts, selected = len(candidates) * 3 // 10, Counter(), []
    for user in candidates:
        group = group_for[user]
        if counts[group] >= len(population[group]) - 1:
            continue
        selected.append(user)
        counts[group] += 1
        if len(selected) == target:
            return tuple(sorted(selected))
    raise ValueError("Population cannot retain online peers during 30% disconnection")


def socket_allocation(active, target):
    """Several connections may share one device; never fabricate extra MLS recipients."""
    active = tuple(active)
    if not active or not len(active) <= target <= 500:
        raise ValueError("Socket target must cover active devices and remain ≤500")
    count, extra = divmod(target, len(active))
    return {key: count + (index < extra) for index, key in enumerate(active)}


def expected_copies(events):
    return sum(len(event["members"]) - 1 for event in events)


def verify_envelope(env, event, previous_seq, previous_head, public_key):
    """Verify the signed outer wire before passing it to native MLS."""
    import base64
    import hashlib
    import rfc8785
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    header = env["header"]
    if (
        type(env["seq"]) is not int
        or env["seq"] != previous_seq + 1
        or header != event["header"]
        or header["previous_hash"] != previous_head
        or env["signature"] != event["signature"]
        or env["chain_hash"] != event["head"]
        or env["sender_device"] != header["sender_device"]
        or env["client_message_id"] != header["client_message_id"]
    ):
        raise ValueError("Recipient signature/order/chain ledger mismatch")
    wire = base64.b64decode(env["ciphertext"], validate=True)
    if hashlib.sha256(wire).hexdigest() != header["ciphertext_hash"]:
        raise ValueError("Ciphertext binding mismatch")
    actual_head = hashlib.sha256(
        rfc8785.dumps({"header": header, "signature": env["signature"]})
    ).hexdigest()
    if actual_head != env["chain_hash"]:
        raise ValueError("Signed chain mismatch")
    Ed25519PublicKey.from_public_bytes(public_key).verify(
        base64.b64decode(env["signature"], validate=True), rfc8785.dumps(header)
    )
    return wire


class Latency:
    """Constant-space latency/SLO counters; quantiles are explicit upper bounds."""

    bounds = (
        5,
        10,
        25,
        50,
        100,
        250,
        500,
        750,
        1000,
        1500,
        2000,
        3000,
        5000,
        10000,
        30000,
        120000,
    )

    def __init__(self, budget):
        self.budget = budget
        self.count = self.exceeded = 0
        self.total = self.maximum = 0.0
        self.buckets = [0] * (len(self.bounds) + 1)

    def add(self, milliseconds):
        self.count += 1
        self.total += milliseconds
        self.maximum = max(self.maximum, milliseconds)
        self.exceeded += milliseconds > self.budget
        self.buckets[bisect_left(self.bounds, milliseconds)] += 1

    def snapshot(self):
        def quantile(fraction):
            seen = 0
            for index, amount in enumerate(self.buckets):
                seen += amount
                if seen >= max(1, int(self.count * fraction + 0.999999)):
                    return self.bounds[index] if index < len(self.bounds) else None

        return {
            "samples": self.count,
            "mean_ms": self.total / self.count if self.count else None,
            "max_ms": self.maximum,
            "p50_upper_ms": quantile(0.5),
            "p95_upper_ms": quantile(0.95),
            "budget_ms": self.budget,
            "above_budget": self.exceeded,
            "p95_budget_pass": bool(self.count and self.exceeded <= self.count * 0.05),
            "histogram_upper_bounds_ms": [*self.bounds, None],
            "histogram_counts": self.buckets,
        }


def safe_failure(error):
    """Export only finite invariant labels/statuses; arbitrary text stays private."""
    import re

    message = str(error)
    static = {
        "Missing conversation or regressed history",
        "Out-of-order envelope",
        "Sender checkpoint unexpectedly missing",
        "MLS sender/roster/epoch confirmation mismatch",
        "MLS plaintext mismatch",
        "Truncated catch-up page",
        "Cursor acknowledgment mismatch",
        "Discovery head mismatch",
        "Accepted envelope missing from independent ledger",
        "Durable acceptance/chain mismatch",
        "Sender acknowledgment mismatch",
        "Authenticated socket hello rejected",
        "Unexpected socket frame",
        "Recipient signature/order/chain ledger mismatch",
        "Ciphertext binding mismatch",
        "Signed chain mismatch",
        "Native worker response invalid",
        "Native worker rejected command",
        "Transport retry exhausted",
        "Request retry exhausted",
    }
    row = {
        "type": type(error).__name__,
        "code": message if message in static else "UNCLASSIFIED",
    }
    match = re.fullmatch(
        r"HTTP ([1-5][0-9]{2}) on (GET|POST|PUT|DELETE) (conversations|attachments|sync|auth|devices|key-packages)",
        message,
    )
    if match:
        row.update(
            code="HTTP_UNEXPECTED_STATUS",
            status=int(match[1]),
            method=match[2],
            resource=match[3],
        )
    received = getattr(error, "rcvd", None)
    close_code = getattr(received, "code", None)
    if type(close_code) is int:
        row["socket_close_code"] = close_code
    return row


def fixed_socket_allocation(plan, active):
    """An outage closes that device's tabs; other devices retain their own tabs."""
    active = tuple(active)
    if not active or not set(active) <= plan.keys():
        raise ValueError("Natural connection plan cannot introduce new devices")
    return {index: plan[index] for index in active}
