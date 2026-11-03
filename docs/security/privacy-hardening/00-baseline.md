# Baseline — 2026-11-03

Ground truth: clean checkout `8fb3c6c808d14277cc59e53d7363af62d9ea6c5b`, before this change set. Owner reports no real users and no need to preserve test history. We nevertheless preserve signing bytes, MLS/vault/outbox state and replay protection; no existing deployment or backups are modified.

Read: README, SECURITY, SECURITY_STATUS, IMPLEMENTATION_STATUS, RELEASE_CHECKLIST and TEST_REPORT; threat-model and ADR 0013–0015; metadata-privacy inventory/flows/threat-model/research; current models, views, protocol, middleware, authorization, privacy, retention, consumers, storage, UI/privacy/messenger/vault/contact/connection/proxy, crypto-core, Compose/Nginx and release workflows. Existing metadata work is authoritative historical evidence, not a qualification of new changes.

Baseline: `timeout 120s .venv/bin/pytest -q core/tests/test_metadata_privacy.py core/tests/test_privacy.py core/tests/test_friend_invitations.py` with `.local/test.env`, isolated haven-test PostgreSQL/Redis: **21 PASS, 8.23 s** ([log](evidence/baseline-tests.txt)). No endurance run.

Confirmed weaknesses: full `haven-local-user` plaintext localStorage; mandatory display name; approved device lookup and KeyPackage claim available by UUID; contact links default to account name; raw user.UUID Channels groups; notification worker shares API credentials and application signing secret despite projected queries. Exact attachment plaintext size is derivable from chunk lengths. Optional activity already defaults off, notifications already generic, consumed fragments already cleared, retention already preserves unacknowledged ciphertext/replay markers, normal CRYPTO_READY is False.

Synthetic graph reproduction and updated verification are recorded in [adversarial results](adversarial-test-results.md). PostgreSQL contains redundant links through genesis and full signed transitions even if foreign keys were removed. Active graph concealment is outside this architecture.
