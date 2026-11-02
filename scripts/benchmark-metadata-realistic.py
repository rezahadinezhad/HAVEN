#!/usr/bin/env python3
"""Native workload v2: independent devices, queued offline copies and real burst phases.

Only the owning isolated orchestrator may run this driver. No production imports,
authentication verdicts, cryptography, HTTP responses or storage are mocked.
"""

import asyncio
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import uuid

from metadata_workload import (
    Workload,
    Latency,
    socket_allocation,
    fixed_socket_allocation,
    verify_envelope,
    AuthorCycle,
    intermittent_accounts,
    safe_failure,
    AUTHOR_SEED,
)
from metadata_load_instruments import WaitSampler, process_usage

if os.environ.get("HAVEN_ISOLATED_LOAD") != "synthetic-only":
    raise SystemExit("Use the isolated orchestrator")

spec = importlib.util.spec_from_file_location(
    "metadata_native", Path(__file__).with_name("benchmark-metadata-load.py")
)
N = importlib.util.module_from_spec(spec)
spec.loader.exec_module(N)
CONFIG = Workload(**json.loads(os.environ["HAVEN_WORKLOAD_DEFINITION"]))


def interrupted(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, interrupted)


def task_stage(task, name):
    if task is None:
        return
    now = time.monotonic()
    elapsed = now - task["stage_started"]
    durations = task["stage_seconds"]
    durations[task["stage"]] = durations.get(task["stage"], 0) + elapsed
    task["stage"], task["stage_started"] = name, now


def task_times(task):
    durations = dict(task["stage_seconds"])
    durations[task["stage"]] = durations.get(task["stage"], 0) + (
        time.monotonic() - task["stage_started"]
    )
    return durations


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.lifecycle_stop = threading.Event()
        self.receivers, self.conversations = [], []
        self.latencies, self.counts = {}, Counter()
        self.failures, self.lifecycle, self.series = [], [], []
        self.online_pending = defaultdict(deque)
        self.offering = False
        self.phase = "setup"
        self.stop_details = {}
        self.planned_offline_devices = set()
        self.offline_expected_conversations = set()
        self.offline_backlog_conversations = set()
        self.start = 0

    def add_latency(self, name, value, budget):
        with self.lock:
            self.latencies.setdefault(name, Latency(budget)).add(value)

    def fail(self, component, error):
        with self.lock:
            row = {"component": component, **safe_failure(error)}
            self.failures.append(row)
            # Persist failures before teardown; otherwise a later drain error
            # obscures the original cause. No arbitrary exception text exported.
            try:
                import traceback

                (
                    N.PRIVATE / ("failure-detail-" + str(len(self.failures)) + ".txt")
                ).write_text("".join(traceback.format_exception(error)))
                target = N.PRIVATE / "failure-summary.json"
                temporary = N.PRIVATE / "failure-summary.pending"
                temporary.write_text(
                    json.dumps(
                        {
                            "failures": self.failures,
                            "phase": self.phase,
                            "elapsed_seconds": time.monotonic() - self.start,
                            "counts": dict(self.counts),
                        }
                    )
                )
                temporary.replace(target)
            except OSError:
                pass  # Failure remains in memory; unavailable diagnostics never create a pass.

    def pending_age(self):
        now = time.monotonic()
        with self.lock:
            ages = []
            for index, queue in self.online_pending.items():
                r = self.receivers[index]
                while queue and (
                    queue[0][0] <= r.acked
                    or not r.online.is_set()
                    or queue[0][2] != r.generation
                ):
                    queue.popleft()
                if queue:
                    ages.append(now - queue[0][1])
            return max(ages, default=0)

    def pending_details(self):
        # Read-only diagnostics for the actual oldest recipients, rather than
        # inferring a receive stall from the oldest sender's unrelated device.
        now = time.monotonic()
        with self.lock:
            details = []
            for index, queue in self.online_pending.items():
                r = self.receivers[index]
                if queue:
                    details.append(
                        {
                            "receiver_index": index,
                            "age_seconds": now - queue[0][1],
                            "stage": r.receive_stage,
                            "pending_events": max(0, r.observed_target - r.seq),
                            "ready_to_send": r.allow_send,
                        }
                    )
            return sorted(details, key=lambda d: d["age_seconds"], reverse=True)[:5]

    def progress(self):
        with self.lock, N.metrics_lock:
            return {
                "elapsed_seconds": time.monotonic() - self.start,
                "phase": self.phase,
                **dict(self.counts),
                "connected_sockets": N.metrics["ws_connected"],
                "online_devices": sum(r.online.is_set() for r in self.receivers),
                "ready_sender_devices": sum(
                    r.online.is_set() and r.allow_send for r in self.receivers
                ),
                "unexpected_socket_errors": N.metrics["ws_errors"],
                "oldest_continuously_online_pending_seconds": self.pending_age(),
            }


S = State()


class Receiver:
    def __init__(self, client, user_index, slot):
        self.client, self.user_index, self.slot = client, user_index, slot
        self.index = len(S.receivers)
        self.online, self.dirty = threading.Event(), threading.Event()
        self.lock = threading.RLock()
        self.generation, self.pending_sends = 0, 0
        self.allow_send = True
        self.ready_target = 0
        self.ready_started = None
        self.ready_label = None
        self.receive_stage = "idle"
        self.observed_target = 0
        self.next_poll = 0.0
        self.future = None
        self.conversation = None
        self.seq = self.acked = 0
        self.head = ""
        S.receivers.append(self)

    def set_online(self, value, ready_label=None):
        with self.lock:
            self.generation += 1
            self.allow_send = bool(value and ready_label is None)
            self.ready_label = ready_label if value else None
            self.ready_started = time.monotonic() if value and ready_label else None
            self.ready_target = (
                self.conversation.base.seq if value and ready_label else self.seq
            )
            if value:
                self.online.set()
                self.dirty.set()
                self.next_poll = 0
            else:
                self.online.clear()

    def record_acks(self, entries):
        now = time.monotonic()
        with S.lock:
            for event in entries:
                if event["author"] is self:
                    S.counts["sender_checkpoints"] += event["kind"] == "application"
                    continue
                if event["kind"] != "application":
                    S.counts["control_recipient_copies"] += 1
                    continue
                S.counts["durable_recipient_copies"] += 1
                generation = event["online"].get(self.index)
                continuous = (
                    generation is not None
                    and self.online.is_set()
                    and generation == self.generation
                )
                category = (
                    "online"
                    if continuous
                    else "interrupted"
                    if generation is not None
                    else "deferred"
                )
                S.counts[category + "_copies"] += 1
                if self.index in event["planned_offline"]:
                    S.counts["planned_offline_copies_durably_received"] += 1
                    S.add_latency(
                        "planned_offline_recovery:" + event["phase"],
                        (now - event["accepted_at"]) * 1000,
                        180000,
                    )
                if self.index in event["pending_online"]:
                    event["pending_online"].remove(self.index)
                    event["online_interrupted"] |= not continuous
                    if not event["pending_online"]:
                        key = (
                            "interrupted_online_messages"
                            if event["online_interrupted"]
                            else "complete_online_messages"
                        )
                        S.counts[key] += 1
                        S.counts[key + ":" + event["phase"]] += 1
                        if not event["online_interrupted"]:
                            # Distinct messages, completed only after every device
                            # online at acceptance durably ACKs without a gap.
                            # Diagnostic: the existing per-copy SLO stays fixed.
                            S.add_latency(
                                "complete_online_message:" + event["phase"],
                                (now - event["accepted_at"]) * 1000,
                                3000,
                            )
                S.add_latency(
                    category + ":" + event["phase"],
                    (now - event["accepted_at"]) * 1000,
                    3000 if continuous else 180000,
                )

    def sync_locked(self):
        if not self.online.is_set():
            return
        conv = self.conversation
        self.receive_stage = "discovery"
        listing = self.client.request("sync")
        detail = next(
            (c for c in listing["conversations"] if c["id"] == conv.base.id), None
        )
        if detail is None or detail["last_seq"] < self.seq:
            raise RuntimeError("Missing conversation or regressed history")
        target = detail["last_seq"]
        self.observed_target = target
        entries = []
        while self.seq < target:
            self.receive_stage = "fetch"
            page = self.client.request(
                f"conversations/{conv.base.id}/messages?after_seq={self.seq}&limit=100"
            )
            with S.lock:
                S.counts["fetch_pages"] += 1
            before = self.seq
            for env in page["messages"]:
                if env["seq"] > target:
                    break
                if env["seq"] != self.seq + 1:
                    raise RuntimeError("Out-of-order envelope")
                event = conv.event(env["seq"])
                verify_envelope(
                    env,
                    event,
                    self.seq,
                    self.head,
                    N.base64.b64decode(event["author"].client.public_key),
                )
                if event["author"] is self:
                    raise RuntimeError("Sender checkpoint unexpectedly missing")
                self.receive_stage = "native_process"
                processed = N.native(
                    self.client,
                    "process",
                    group_id=conv.base.gid,
                    ciphertext=env["ciphertext"],
                )
                members = sorted(
                    (member["identity"], member["public_key"])
                    for member in processed["members"]
                )
                if (
                    members != conv.members
                    or processed["epoch"] != event["epoch_after"]
                    or processed["state_hash"] != event["state_hash"]
                    or processed["sender"] != event["author"].client.identity
                ):
                    raise RuntimeError("MLS sender/roster/epoch confirmation mismatch")
                if (
                    event["kind"] == "application"
                    and N.fingerprint(processed["plaintext"].encode())
                    != event["plaintext_hash"]
                ):
                    raise RuntimeError("MLS plaintext mismatch")
                # Match the browser's per-event durable state, then cumulatively ACK.
                self.receive_stage = "checkpoint"
                self.client.checkpoint(conv.base.id, env["seq"], env["chain_hash"])
                self.seq, self.head = env["seq"], env["chain_hash"]
                entries.append(event)
            if self.seq == before:
                raise RuntimeError("Truncated catch-up page")
        if self.seq > self.acked:
            self.receive_stage = "ack"
            ack = self.client.request(
                f"conversations/{conv.base.id}/acks", "POST", {"seq": self.seq}
            )
            if ack["seq"] != self.seq or ack["state"] != "recipient_synced":
                raise RuntimeError("Cursor acknowledgment mismatch")
            self.acked = self.seq
            with S.lock:
                S.counts["recipient_ack_requests"] += 1
            self.record_acks(entries)
        if self.seq == target and self.head != detail["head_hash"]:
            raise RuntimeError("Discovery head mismatch")
        if self.ready_label and self.acked >= self.ready_target:
            with S.lock:
                S.add_latency(
                    "device_ready:" + self.ready_label,
                    (time.monotonic() - self.ready_started) * 1000,
                    180000,
                )
                self.ready_label = None
                self.allow_send = True
        self.receive_stage = "idle"

    def synchronize(self):
        with self.lock:
            self.sync_locked()


class Conversation:
    def __init__(self, receivers):
        self.receivers = receivers
        people = {r.user_index for r in receivers}
        self.base = N.Group(
            [r.client for r in receivers],
            kind="direct" if len(people) == 2 else "group",
        )
        self.owner = receivers[0]
        self.send_lock = threading.Lock()
        self.condition = threading.Condition()
        self.events = {}
        self.messages = self.last_rekey_messages = 0
        self.pending_author_acks = set()
        self.probe_seq = None
        self.second_application = threading.Event()
        self.members = sorted(
            (member["identity"], member["public_key"]) for member in self.base.roster
        )
        for r in receivers:
            r.conversation = self
            r.seq = r.acked = self.base.seq
            r.head = self.base.head
        S.conversations.append(self)

    def event(self, seq):
        with self.condition:
            if not self.condition.wait_for(lambda: seq in self.events, timeout=30):
                raise RuntimeError("Accepted envelope missing from independent ledger")
            return self.events[seq]

    def publish_locked(
        self,
        actor,
        scheduled,
        phase,
        transition=None,
        wire=None,
        task=None,
        acknowledge=True,
    ):
        c = self.base
        mid = str(uuid.uuid4())
        plain = json.dumps(
            {
                "id": mid,
                "conversation_id": c.id,
                "sender": actor.client.id,
                "time": N.timezone.now().isoformat(),
                "type": "text",
                "text": "Synthetic workload " + "x" * 128,
            },
            separators=(",", ":"),
        )
        if task is not None:
            task_stage(task, "native_encrypt")
        if wire is None:
            wire = N.native(actor.client, "encrypt", group_id=c.gid, plaintext=plain)[
                "ciphertext"
            ]
        header = {
            "domain": "haven/envelope/v1",
            "v": 1,
            "conversation_id": c.id,
            "group_id": c.gid,
            "sender_device": actor.client.id,
            "client_message_id": mid,
            "epoch": c.epoch,
            "seq": c.seq + 1,
            "previous_hash": c.head,
            "ciphertext_hash": N.fingerprint(N.base64.b64decode(wire)),
            "transition": transition,
        }
        body = {
            "v": 1,
            "client_message_id": mid,
            "epoch": c.epoch,
            "ciphertext": wire,
            "header": header,
            "signature": actor.client.sign(header),
        }
        endpoint = "crypto-events" if transition else "messages"
        if transition:
            body["action"] = "update"
        if task is not None:
            task_stage(task, "pending_checkpoint")
        actor.client.checkpoint(c.id, c.seq, c.head, body)
        sent = time.monotonic()
        if task is not None:
            task_stage(task, "post")
        response = actor.client.request(
            f"conversations/{c.id}/{endpoint}", "POST", body, expected=(200, 201)
        )
        accepted = time.monotonic()
        env = response["envelope"]
        head = N.chain(header, body["signature"])
        if (
            response["seq"] != c.seq + 1
            or env["chain_hash"] != head
            or env["header"] != header
            or env["signature"] != body["signature"]
            or env["ciphertext"] != wire
            or env["client_message_id"] != mid
            or env["sender_device"] != actor.client.id
        ):
            raise RuntimeError("Durable acceptance/chain mismatch")
        if task is not None:
            task_stage(task, "accepted_checkpoint")
        actor.client.checkpoint(c.id, response["seq"], head)
        actor.seq, actor.head = response["seq"], head
        event = {
            "author": actor,
            "kind": "commit" if transition else "application",
            "header": header,
            "signature": body["signature"],
            "head": head,
            "accepted_at": accepted,
            "phase": phase,
            "epoch_after": transition["next_epoch"] if transition else c.epoch,
            "state_hash": c.state_hash,
            "plaintext_hash": N.fingerprint(plain.encode()),
            "online": {
                r.index: r.generation for r in self.receivers if r.online.is_set()
            },
        }
        event["pending_online"] = set(event["online"]) - {actor.index}
        event["online_interrupted"] = False
        event["planned_offline"] = set()
        with self.condition:
            c.seq, c.head = response["seq"], head
            self.events[c.seq] = event
            with S.lock:
                key = "controls" if transition else "accepted"
                S.counts[key] += 1
                S.counts[key + ":" + phase] += 1
                if not transition:
                    S.counts["accepted_while_prior_author_ack_pending"] += bool(
                        self.pending_author_acks
                    )
                    self.pending_author_acks.add(c.seq)
                    if self.probe_seq is None:
                        self.probe_seq = c.seq
                    event["planned_offline"] = S.planned_offline_devices & {
                        r.index for r in self.receivers
                    } - set(event["online"])
                    if event["planned_offline"]:
                        S.offline_backlog_conversations.add(c.id)
                        S.counts["messages_queued_during_planned_offline"] += 1
                        S.counts["planned_offline_copies_queued"] += len(
                            event["planned_offline"]
                        )
                    if not event["pending_online"]:
                        S.counts["messages_without_online_recipient"] += 1
                    S.add_latency("post:" + phase, (accepted - sent) * 1000, 750)
                    S.add_latency(
                        "scheduled_accept:" + phase,
                        (accepted - scheduled) * 1000,
                        10000,
                    )
                for r in self.receivers:
                    if r is not actor and r.index in event["online"]:
                        S.online_pending[r.index].append(
                            (c.seq, accepted, r.generation)
                        )
            self.condition.notify_all()
        if acknowledge:
            self.acknowledge_author(actor, event, task)
        if transition:
            c.epoch += 1
        return event

    def acknowledge_author(self, actor, event, task=None):
        if (
            CONFIG.hold_first_ack
            and event["kind"] == "application"
            and event["header"]["seq"] == self.probe_seq
        ):
            task_stage(task, "diagnostic_sender_ack_hold")
            released = self.second_application.wait(timeout=5)
            with S.lock:
                S.counts["diagnostic_first_acks_held"] += 1
                S.counts["diagnostic_holds_released_by_second_publication"] += released
        task_stage(task, "sender_ack")
        ack = actor.client.request(
            f"conversations/{self.base.id}/acks", "POST", {"seq": actor.seq}
        )
        if ack["seq"] != actor.seq or ack["state"] != "recipient_synced":
            raise RuntimeError("Sender acknowledgment mismatch")
        actor.acked = actor.seq
        actor.record_acks([event])
        if event["kind"] == "application":
            with S.lock:
                self.pending_author_acks.remove(event["header"]["seq"])

    def send(self, actor, scheduled, phase, task):
        try:
            # Retain this author's client lock through its real ACK, while
            # releasing the conversation publication lane after durable save.
            # Another author's ratchet/HTTP work need not wait for that ACK.
            with ExitStack() as held_author:
                with self.send_lock:
                    if not actor.online.is_set():
                        raise RuntimeError(
                            "Scheduled sender disconnected before its pending intent drained"
                        )
                    if (
                        self.messages - self.last_rekey_messages >= CONFIG.rekey_every
                        and self.owner.online.is_set()
                        and self.owner.allow_send
                    ):
                        task_stage(task, "rekey_waiting_client_lock")
                        with self.owner.lock:
                            if self.owner.online.is_set():
                                task_stage(task, "rekey_sync")
                                self.owner.sync_locked()
                                task_stage(task, "rekey_native_update")
                                update = N.native(
                                    self.owner.client, "update", group_id=self.base.gid
                                )
                                self.base.state_hash = update["state_hash"]
                                transition = {
                                    "action": "update",
                                    "device_id": None,
                                    "next_epoch": self.base.epoch + 1,
                                    "members": self.base.roster,
                                    "welcome_hash": N.fingerprint(b""),
                                    "state_hash": update["state_hash"],
                                }
                                self.publish_locked(
                                    self.owner,
                                    scheduled,
                                    phase,
                                    transition,
                                    update["commit"],
                                    task=task,
                                )
                                self.last_rekey_messages = self.messages
                    task_stage(task, "waiting_client_lock")
                    held_author.enter_context(actor.lock)
                    task_stage(task, "sender_sync")
                    actor.sync_locked()
                    event = self.publish_locked(
                        actor, scheduled, phase, task=task, acknowledge=False
                    )
                    self.messages += 1
                    if self.messages >= 2:
                        self.second_application.set()
                self.acknowledge_author(actor, event, task)
                task_stage(task, "completed")
        finally:
            with S.lock:
                actor.pending_sends -= 1


class Fleet:
    def __init__(self):
        self.final_drain = False
        initial = [r.index for r in S.receivers if r.online.is_set()]
        self.fixed_allocation = (
            socket_allocation(initial, CONFIG.socket_target(len(initial)))
            if CONFIG.profile == "combined-natural"
            else None
        )
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def desired(self):
        active = [r.index for r in S.receivers if r.online.is_set()]
        target = len(active) if self.final_drain else CONFIG.socket_target(len(active))
        allocation = (
            fixed_socket_allocation(self.fixed_allocation, active)
            if self.fixed_allocation is not None and not self.final_drain
            else socket_allocation(active, target)
        )
        return {
            (index, tab) for index, count in allocation.items() for tab in range(count)
        }

    async def socket(self, key, semaphore):
        r = S.receivers[key[0]]
        connected = False
        ws = None
        try:
            async with semaphore:
                ws = await N.websockets.connect(
                    N.ORIGIN.replace("https:", "wss:") + "/ws/v1",
                    ssl=N.SSL,
                    origin=N.ORIGIN,
                    additional_headers={
                        "Cookie": f"{N.settings.SESSION_COOKIE_NAME}={r.client.token}"
                    },
                    local_addr=(r.client.ip, 0),
                    proxy=None,
                    ping_interval=None,
                    open_timeout=30,
                )
                hello = json.loads(await asyncio.wait_for(ws.recv(), 30))
                if (
                    hello.get("kind") != "hello"
                    or hello.get("crypto_ready") is not True
                ):
                    raise RuntimeError("Authenticated socket hello rejected")
                with N.metrics_lock:
                    N.metrics["ws_connected"] += 1
                    connected = True
                    N.metrics["ws_peak"] = max(
                        N.metrics["ws_peak"], N.metrics["ws_connected"]
                    )
            with S.lock:
                if S.offering:
                    S.counts["offering_socket_peak"] = max(
                        S.counts["offering_socket_peak"], N.metrics["ws_connected"]
                    )
            async with ws:
                r.dirty.set()
                heartbeat = 0
                while not S.stop.is_set():
                    if time.monotonic() >= heartbeat:
                        await ws.send(json.dumps({"v": 1, "kind": "heartbeat"}))
                        heartbeat = time.monotonic() + 20
                    try:
                        reply = json.loads(await asyncio.wait_for(ws.recv(), 1))
                    except TimeoutError:
                        continue
                    if reply.get("kind") not in ("heartbeat", "sync.required"):
                        raise RuntimeError("Unexpected socket frame")
                    if reply["kind"] == "sync.required":
                        r.dirty.set()
                    with N.metrics_lock:
                        label = (
                            "heartbeats"
                            if reply["kind"] == "heartbeat"
                            else "notification_hints"
                        )
                        N.metrics[label] = N.metrics.get(label, 0) + 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not S.stop.is_set() and key in self.desired():
                with N.metrics_lock:
                    N.metrics["ws_errors"] += 1
                S.fail("socket", exc)
        finally:
            if ws is not None:
                await ws.close()
            if connected:
                with N.metrics_lock:
                    N.metrics["ws_connected"] -= 1

    async def loop(self):
        tasks, semaphore = {}, asyncio.Semaphore(20)
        try:
            while not S.stop.is_set():
                desired = self.desired()
                for key in set(tasks) - desired:
                    task = tasks.pop(key)
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                for key in desired - set(tasks):
                    tasks[key] = asyncio.create_task(self.socket(key, semaphore))
                with N.metrics_lock:
                    if N.metrics["ws_connected"] == len(desired):
                        self.ready.set()
                await asyncio.sleep(0.1)
        finally:
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)

    def run(self):
        try:
            asyncio.run(self.loop())
        except Exception as exc:
            S.fail("socket-fleet", exc)


def receivers(pool):
    try:
        while not S.stop.is_set():
            for r in S.receivers:
                if r.future is not None and r.future.done():
                    try:
                        r.future.result()
                    except Exception as exc:
                        S.fail("receiver", exc)
                    r.future = None
                now = time.monotonic()
                if (
                    r.future is None
                    and r.online.is_set()
                    and (r.dirty.is_set() or now >= r.next_poll)
                ):
                    r.dirty.clear()
                    r.next_poll = now + 5
                    r.future = pool.submit(r.synchronize)
            S.stop.wait(0.05)
    except Exception as exc:
        S.fail("receiver-scheduler", exc)


def lifecycle(users, duration):
    owners = {c.owner.user_index for c in S.conversations}
    handoff = [n for n in range(CONFIG.users) if n not in owners and n % 5 != 0][
        : max(1, CONFIG.users // 10)
    ]
    intermittent = intermittent_accounts(CONFIG.population())
    actions = []
    previous_online = {}
    if CONFIG.profile in ("realistic", "handoff"):
        actions.append((duration / 3, "handoff", handoff))
    if CONFIG.profile in ("realistic", "intermittent", "combined", "combined-natural"):
        actions.extend(
            [
                (duration / 2, "offline", intermittent),
                (duration / 2 + min(120, duration * 0.2), "return", intermittent),
            ]
        )
    for at, action, selected in sorted(actions):
        if S.lifecycle_stop.wait(max(0, S.start + at - time.monotonic())):
            return
        with S.lock:
            if action == "offline":
                S.planned_offline_devices = {
                    r.index for n in selected for r in users[n] if r.online.is_set()
                }
                S.offline_expected_conversations = {
                    users[n][0].conversation.base.id for n in selected
                }
            for n in selected:
                for r in users[n]:
                    r.allow_send = False
        deadline = time.monotonic() + 30
        while any(r.pending_sends for n in selected for r in users[n]):
            if S.lifecycle_stop.wait(0.05):
                return
            if time.monotonic() >= deadline:
                S.fail("lifecycle-pending-intent", TimeoutError())
                return
        for n in selected:
            a, b = users[n]
            if action == "handoff":
                a.set_online(False)
                b.set_online(True, ready_label="handoff")
            elif action == "offline":
                previous_online[n] = (a.online.is_set(), b.online.is_set())
                a.set_online(False)
                b.set_online(False)
            else:
                a_on, b_on = previous_online[n]
                a.set_online(a_on, ready_label="return" if a_on else None)
                b.set_online(b_on, ready_label="return" if b_on else None)
        with S.lock:
            if action == "return":
                S.planned_offline_devices.clear()
            affected = {users[n][0].conversation for n in selected}
            S.lifecycle.append(
                {
                    "action": action,
                    "accounts": len(selected),
                    "affected_conversations": len(affected),
                    "conversations_with_online_peer": sum(
                        any(r.online.is_set() for r in c.receivers) for c in affected
                    ),
                    "planned_seconds": at,
                    "observed_seconds": time.monotonic() - S.start,
                    "online_devices": sum(r.online.is_set() for r in S.receivers),
                }
            )


def provision():
    from django.contrib.auth.hashers import make_password

    encoded = make_password(N.secrets.token_urlsafe(32))
    users = []
    for n in range(CONFIG.users):
        user = N.m.User.objects.create(
            username="load_" + uuid.uuid4().hex,
            display_name="Synthetic load",
            password=encoded,
            device_bootstrapped=True,
        )
        pair = [Receiver(N.Client(user, n), n, slot) for slot in range(2)]
        first, second = [r.client for r in pair]
        signed = N.native(
            first,
            "sign",
            payload=N.b64(
                f"haven/enrollment/v1:{user.pk}:{second.id}:{second.public_key}:{second.device.challenge}".encode()
            ),
        )["signature"]
        N.m.Device.objects.filter(pk=second.id).update(
            approved_by=first.device, approval_signature=N.base64.b64decode(signed)
        )
        for r in pair:
            r.client.csrf = r.client.request("auth/csrf")["csrf"]
        users.append(pair)
    for members in CONFIG.population():
        Conversation([r for n in members for r in users[n]])
        (N.PRIVATE / "fixture-progress.json").write_text(
            json.dumps(
                {
                    "conversations": len(S.conversations),
                    "target": len(CONFIG.population()),
                }
            )
        )
    for pair in users:
        pair[0].set_online(True)
        pair[1].set_online(pair[0].user_index % 5 == 0)
    return users


def run():
    fleet, receive_pool, receive_thread, life_thread = None, None, None, None
    sender_pools, file_pool, file_futures = [], None, []
    try:
        users = provision()
        authors = AuthorCycle(CONFIG.users)
        fleet = Fleet()
        fleet.thread.start()
        if not fleet.ready.wait(90) or S.failures:
            raise RuntimeError("Initial authenticated socket population failed")
        print("READY", flush=True)
        if sys.stdin.readline().strip() != "GO":
            raise RuntimeError("Measurement handshake rejected")
        with N.metrics_lock:
            for key in list(N.metrics):
                if key not in ("ws_connected", "ws_peak"):
                    N.metrics[key] = 0
        before, crypto_before, driver_before = (
            N.stats(),
            N.crypto.usage(),
            process_usage(os.getpid()),
        )
        sampler = WaitSampler(N.settings.DATABASES["default"])
        sampler.start()
        N.timings.reset()
        receive_pool = ThreadPoolExecutor(
            max_workers=32, thread_name_prefix="recipient"
        )
        receive_thread = threading.Thread(
            target=receivers, args=(receive_pool,), daemon=True
        )
        receive_thread.start()
        sender_pools = [
            ThreadPoolExecutor(max_workers=CONFIG.sender_workers)
            for _ in S.conversations
        ]
        pool_for = dict(zip(S.conversations, sender_pools))
        S.start = time.monotonic()
        S.offering = True
        S.counts["offering_socket_peak"] = N.metrics["ws_connected"]
        phases, pending, offered, stop_reason = CONFIG.phases(), deque(), 0, None
        total = sum(seconds for _, seconds, _ in phases)
        life_thread = threading.Thread(
            target=lifecycle, args=(users, total), daemon=True
        )
        life_thread.start()
        next_progress, offset = S.start, 0
        phase_results = []
        for phase, seconds, rate in phases:
            S.phase = phase
            phase_offered = 0
            if (
                CONFIG.files
                and not file_pool
                and (phase == "burst" or len(phases) == 1)
            ):
                file_pool = ThreadPoolExecutor(max_workers=CONFIG.files)
                barrier = threading.Barrier(CONFIG.files)
                for conv in S.conversations[: CONFIG.files]:
                    active = [r.client for r in conv.receivers if r.online.is_set()]
                    file_futures.append(
                        file_pool.submit(
                            N.transfer_file, conv.base, barrier, active[0], active[-1]
                        )
                    )
            for index in range(int(seconds * rate)):
                scheduled = S.start + offset + index / rate
                S.stop.wait(max(0, scheduled - time.monotonic()))
                while pending and pending[0][1].done():
                    pending.popleft()[1].result()
                online_age = S.pending_age()
                scheduler_lag = time.monotonic() - scheduled
                sender_age = time.monotonic() - pending[0][0] if pending else 0
                if (
                    S.failures
                    or online_age > 10
                    or scheduler_lag > 10
                    or sender_age > 10
                ):
                    stop_reason = (
                        "unexpected_failure_or_ten_second_sender_online_backlog"
                    )
                    S.stop_details = {
                        "online_pending_seconds": online_age,
                        "oldest_receivers": S.pending_details(),
                        "scheduler_lag_seconds": scheduler_lag,
                        "sender_pending_seconds": sender_age,
                        "sender_stage": pending[0][2]["stage"] if pending else None,
                        "sender_stage_seconds": task_times(pending[0][2])
                        if pending
                        else {},
                        "sender_conversation_users": len(
                            pending[0][3].conversation.receivers
                        )
                        // 2
                        if pending
                        else None,
                        "receiver_stage": pending[0][3].receive_stage
                        if pending
                        else None,
                        "receiver_pending_events": max(
                            0, pending[0][3].observed_target - pending[0][3].seq
                        )
                        if pending
                        else 0,
                    }
                    break
                with S.lock:
                    eligible = [
                        (user, slot)
                        for user, pair in enumerate(users)
                        for slot, receiver in enumerate(pair)
                        if receiver.online.is_set() and receiver.allow_send
                    ]
                    user, slot = authors.choose(eligible)
                    actor = users[user][slot]
                    actor.pending_sends += 1
                task = {
                    "stage": "queued",
                    "stage_started": time.monotonic(),
                    "stage_seconds": {},
                }
                future = pool_for[actor.conversation].submit(
                    actor.conversation.send, actor, scheduled, phase, task
                )
                pending.append((scheduled, future, task, actor))
                offered += 1
                phase_offered += 1
                if time.monotonic() >= next_progress:
                    row = S.progress()
                    S.series.append(row)
                    (N.PRIVATE / "progress.json").write_text(json.dumps(row))
                    next_progress = time.monotonic() + 30
            phase_results.append(
                {
                    "phase": phase,
                    "seconds": seconds,
                    "offered_rate": rate,
                    "planned_messages": int(seconds * rate),
                    "offered_messages": phase_offered,
                }
            )
            offset += seconds
            if stop_reason:
                break
        for _, future, _, _ in pending:
            future.result(timeout=120)
        S.stop.wait(
            max(0, S.start + total - time.monotonic()) if not stop_reason else 0
        )
        S.offering = False
        S.lifecycle_stop.set()
        life_thread.join(timeout=35)
        offering_elapsed = time.monotonic() - S.start
        offering_progress = S.progress()
        file_ms = [future.result(timeout=90) for future in file_futures]
        # Connect every still-trusted identity, including all intentionally
        # offline devices. Do not erase them, waive ACKs or invent deliveries.
        S.phase = "final_deferred_catchup"
        fleet.final_drain = True
        drain_started = time.monotonic()
        for r in S.receivers:
            if not r.online.is_set():
                r.set_online(True)
            r.dirty.set()
        while any(r.acked != r.conversation.base.seq for r in S.receivers):
            if S.failures or time.monotonic() - drain_started > 180:
                raise RuntimeError("Final deferred catch-up failed")
            S.stop.wait(0.1)
        catchup_seconds = time.monotonic() - drain_started
        S.stop.set()
        fleet.thread.join(timeout=35)
        receive_thread.join(timeout=35)
        receive_pool.shutdown(wait=True)
        expected = sum((len(c.receivers) - 1) * c.messages for c in S.conversations)
        restores = 0
        for r in S.receivers:
            c = r.conversation
            sealed = (N.PRIVATE / (r.client.id + ".checkpoint")).read_bytes()
            clear = json.loads(
                N.AESGCM((N.PRIVATE / "checkpoint.key").read_bytes()).decrypt(
                    sealed[:12],
                    sealed[12:],
                    f"haven-load-checkpoint/v1:{r.client.id}:{c.base.id}".encode(),
                )
            )
            if (
                clear["seq"] != c.base.seq
                or clear["head"] != c.base.head
                or r.head != c.base.head
            ):
                raise RuntimeError("Persisted device checkpoint mismatch")
            actual_cursor = N.m.DeliveryCursor.objects.values_list(
                "last_acked_seq", flat=True
            ).get(device_id=r.client.id, conversation_id=c.base.id)
            if actual_cursor != c.base.seq:
                raise RuntimeError("Authoritative database cursor mismatch")
            N.crypto.exchange(
                r.client.shard,
                {
                    "client": r.client.id,
                    "op": "restore",
                    "state": clear["state"],
                    "group_id": c.base.gid,
                },
            )
            restored = N.native(r.client, "inspect", group_id=c.base.gid)
            if (
                restored["epoch"] != c.base.epoch
                or restored["state_hash"] != c.base.state_hash
                or sorted((m["identity"], m["public_key"]) for m in restored["members"])
                != c.members
            ):
                raise RuntimeError("Native checkpoint restoration mismatch")
            restores += 1
        N.timings.enabled.clear()
        waits, crypto_after, driver_after = (
            sampler.finish(),
            N.crypto.usage(),
            process_usage(os.getpid()),
        )
        time.sleep(1.2)
        after = N.stats()
        deadlocks = after["db"]["deadlocks"] - before["db"]["deadlocks"]
        actual_applications = N.m.MessageEnvelope.objects.filter(
            kind="application"
        ).count()
        planned = sum(int(seconds * rate) for _, seconds, rate in phases)
        integrity = (
            not S.failures
            and offered == S.counts["accepted"]
            and offered
            == (
                S.counts["complete_online_messages"]
                + S.counts["interrupted_online_messages"]
                + S.counts["messages_without_online_recipient"]
            )
            and S.counts["durable_recipient_copies"] == expected
            and S.counts["planned_offline_copies_queued"]
            == S.counts["planned_offline_copies_durably_received"]
            and S.counts["sender_checkpoints"] == offered
            and all(not c.pending_author_acks for c in S.conversations)
            and restores == CONFIG.users * 2
            and N.metrics["ws_errors"] == 0
            and deadlocks == 0
            and actual_applications == S.counts["accepted"]
        )
        latency = {
            name: sample.snapshot() for name, sample in sorted(S.latencies.items())
        }
        interruption_required = (
            CONFIG.profile
            in ("realistic", "intermittent", "combined", "combined-natural")
            and CONFIG.seconds >= 60
        )
        interruption_exercised = (
            bool(S.offline_expected_conversations)
            and S.offline_backlog_conversations == S.offline_expected_conversations
            and S.counts["planned_offline_copies_queued"] > 0
            and {"offline", "return"} <= {row["action"] for row in S.lifecycle}
        )
        probe_ok = True
        if CONFIG.hold_first_ack:
            held = S.counts["diagnostic_first_acks_held"]
            released = S.counts["diagnostic_holds_released_by_second_publication"]
            overlap = S.counts["accepted_while_prior_author_ack_pending"]
            probe_ok = bool(held) and (
                (released == held and overlap > 0)
                if CONFIG.sender_workers == 2
                else (released == 0 and overlap == 0)
            )
        performance = (
            (not interruption_required or interruption_exercised)
            and not stop_reason
            and offered == planned
            and not N.metrics["retry_429"]
            and all(
                sample["p95_budget_pass"]
                for name, sample in latency.items()
                if name.startswith(
                    ("post:", "online:", "scheduled_accept:", "device_ready:")
                )
            )
        )
        print(
            json.dumps(
                {
                    "workload_version": "realistic-v6.2",
                    "socket_allocation_policy": (
                        "fixed_tabs_per_device"
                        if CONFIG.profile == "combined-natural"
                        else "constant_occupancy_redistribution"
                        if CONFIG.profile in ("combined", "connections")
                        else "one_socket_per_online_identity"
                    ),
                    "measurement_kind": "DIAGNOSTIC_AUTHOR_ACK_HOLD"
                    if CONFIG.hold_first_ack
                    else "CAPACITY",
                    "sender_pipeline_probe_status": ("PASS" if probe_ok else "FAIL")
                    if CONFIG.hold_first_ack
                    else "NOT_REQUESTED",
                    "planned_interruption": {
                        "required_for_performance": interruption_required,
                        "exercised": interruption_exercised,
                        "expected_affected_conversations": len(
                            S.offline_expected_conversations
                        ),
                        "conversations_with_actual_offline_backlog": len(
                            S.offline_backlog_conversations
                        ),
                        "previously_online_device_copies_queued": S.counts[
                            "planned_offline_copies_queued"
                        ],
                        "actual_copies_durably_received": S.counts[
                            "planned_offline_copies_durably_received"
                        ],
                    },
                    "author_schedule": {
                        "kind": "fixed_seed_interleaved_account_cycle",
                        "seed": AUTHOR_SEED,
                        "eligibility": "online and caught up; equal account opportunities; rotate each account’s eligible devices",
                    },
                    "workload_definition": CONFIG.__dict__,
                    "metrics": {
                        **{
                            k: v
                            for k, v in N.metrics.items()
                            if k not in ("accepted", "delivered", "updates")
                        },
                        **dict(S.counts),
                    },
                    "offered_messages": offered,
                    "planned_messages": planned,
                    "target_status": "PASS"
                    if integrity and performance and probe_ok
                    else "FAIL",
                    "integrity_status": "PASS" if integrity else "FAIL",
                    "performance_status": "PASS" if performance else "FAIL",
                    "reference_host_qualification": "UNQUALIFIED_SHARED_WORKSTATION",
                    "trusted_accounts": CONFIG.users,
                    "trusted_device_identities": CONFIG.users * 2,
                    "initial_online_devices": CONFIG.users + (CONFIG.users + 4) // 5,
                    "initial_socket_target": CONFIG.socket_target(
                        CONFIG.users + (CONFIG.users + 4) // 5
                    ),
                    "conversation_user_sizes": dict(
                        Counter(len(g) for g in CONFIG.population())
                    ),
                    "expected_durable_recipient_copies": expected,
                    "actual_database_application_envelopes": actual_applications,
                    "database_deadlocks": deadlocks,
                    "restored_encrypted_native_checkpoints": restores,
                    "offering_elapsed_seconds": offering_elapsed,
                    "elapsed_seconds": time.monotonic() - S.start,
                    "final_deferred_catchup_seconds": catchup_seconds,
                    "offering_end": offering_progress,
                    "phases": phase_results,
                    "latency": latency,
                    "time_series": S.series,
                    "planned_lifecycle": S.lifecycle,
                    "stop_reason": stop_reason,
                    "stop_details": S.stop_details,
                    "failures": S.failures,
                    "encrypted_files": N.summarize(file_ms),
                    "generator_timings": N.timings.snapshot(),
                    "generator_usage": {
                        "driver_cpu_seconds": driver_after["cpu_seconds"]
                        - driver_before["cpu_seconds"],
                        "driver_peak_rss_kib": driver_after["peak_rss_kib"],
                        "crypto_workers": len(N.crypto.workers),
                        "crypto_worker_cpu_seconds": [
                            a["cpu_seconds"] - b["cpu_seconds"]
                            for a, b in zip(crypto_after, crypto_before)
                        ],
                    },
                    "postgres_wait_sampling": waits,
                    "postgres_before": before,
                    "postgres_after": after,
                    "scope": "Real synthetic native MLS/HTTP/WSS with fsynced encrypted checkpoints; independent recipient queues, paged retrieval and cumulative ACKs; pre-approved fixtures; not physical browsers, mobile KDF, domestic network or production capacity",
                }
            ),
            flush=True,
        )
    finally:
        S.stop.set()
        S.lifecycle_stop.set()
        if life_thread:
            life_thread.join(timeout=35)
        if fleet:
            fleet.thread.join(timeout=35)
        if receive_thread:
            receive_thread.join(timeout=35)
        for pool in sender_pools:
            pool.shutdown(wait=True, cancel_futures=True)
        if receive_pool:
            receive_pool.shutdown(wait=True, cancel_futures=True)
        if file_pool:
            file_pool.shutdown(wait=True, cancel_futures=True)
        N.crypto.close()


if __name__ == "__main__":
    run()
