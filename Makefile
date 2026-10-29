SHELL := /bin/bash
.PHONY: doctor prepare dev test security-test crypto production-build offline-bundle deploy-staging pki-create-offline-root pki-issue-ip-leaf certificate-check backup restore-check outage-drill failover-plan release-check
prepare:
	bash scripts/prepare.sh
doctor:
	bash scripts/doctor.sh
integration-dev:
	bash scripts/integration-dev.sh
browser-test-prepare:
	bash scripts/prepare-browser-tests.sh
dev:
	bash scripts/dev.sh
test:
	bash scripts/test-local.sh
security-test: test
privacy-infrastructure-test:
	python3 scripts/test-privacy-infrastructure.py
crypto:
	bash scripts/build-crypto.sh
production-build: crypto
	bash scripts/build-public-verifier.sh
	uv export --project apps/api --frozen --no-dev --no-emit-project -o apps/api/requirements.lock > /dev/null
	docker build -f apps/api/Dockerfile -t haven-api:0.2.0 .
	docker build -f apps/web/Dockerfile -t haven-web:0.2.0 .
offline-bundle:
	bash scripts/build-offline-bundle.sh
deploy-staging:
	python3 scripts/validate-env.py
	docker compose --env-file .env -f infrastructure/compose/compose.yml up -d --wait
pki-create-offline-root:
	bash infrastructure/pki/create-offline-root.sh
pki-issue-ip-leaf:
	bash infrastructure/pki/issue-ip-leaf.sh
certificate-check:
	bash scripts/certificate-check.sh
backup:
	bash scripts/backup.sh
restore-check:
	bash scripts/restore-check.sh
outage-drill:
	bash scripts/outage-drill.sh
failover-plan:
	bash scripts/failover-plan.sh
release-check:
	python3 scripts/release-gate.py

standby-config-check:
	python3 scripts/check-standby-config.py
container-scan:
	bash scripts/scan-images.sh
