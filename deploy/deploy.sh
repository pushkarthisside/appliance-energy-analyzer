#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
  echo "Usage: $0 ubuntu@<elastic-ip>" >&2
  exit 2
fi

host=$1
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

if ! command -v ssh >/dev/null || ! command -v rsync >/dev/null || ! command -v git >/dev/null; then
  echo "This script requires ssh, rsync, and git on the deployment machine." >&2
  exit 2
fi
if ! git -C "$repo_root" diff --quiet || ! git -C "$repo_root" diff --cached --quiet || [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
  echo "Refusing to deploy a dirty checkout. Deploy the reviewed release from a clean checkout." >&2
  exit 2
fi
if [[ ! -f "$repo_root/backend/requirements.txt" || ! -d "$repo_root/frontend/dist" ]]; then
  echo "Build frontend/dist and verify backend/requirements.txt before deploying." >&2
  exit 2
fi

ssh "$host" 'command -v rsync >/dev/null && command -v python3.12 >/dev/null && command -v curl >/dev/null && python3.12 -c "import ensurepip" >/dev/null 2>&1 || { echo "Install remote prerequisites: rsync, python3.12-venv, and curl." >&2; exit 1; }; test -r /etc/aea/aea.env || { echo "Create /etc/aea/aea.env with the deployment settings before deploying." >&2; exit 1; }; grep -Eq "^AEA_S3_BUCKET=.+$" /etc/aea/aea.env || { echo "Set AEA_S3_BUCKET in /etc/aea/aea.env." >&2; exit 1; }'
ssh "$host" 'sudo install -d -o ubuntu -g ubuntu /srv/aea/backend /srv/aea/frontend/dist'
rsync -az --delete --exclude='.venv/' "$repo_root/backend/" "$host:/srv/aea/backend/"
rsync -az --delete "$repo_root/frontend/dist/" "$host:/srv/aea/frontend/dist/"
rsync -az "$repo_root/deploy/aea.service" "$host:/tmp/aea.service"
ssh "$host" 'sudo install -d -o ubuntu -g ubuntu /opt/aea/data && sudo install -o root -g root -m 644 /tmp/aea.service /etc/systemd/system/aea.service && rm /tmp/aea.service && cd /srv/aea/backend && if [ ! -x .venv/bin/python ]; then python3.12 -m venv .venv; fi && .venv/bin/python -m pip install -r requirements.txt && sudo systemctl daemon-reload && sudo systemctl enable aea && sudo systemctl restart aea && sudo systemctl is-active --quiet aea'
ssh "$host" 'for attempt in $(seq 1 60); do if curl -fsS --max-time 5 http://127.0.0.1/api/health | python3.12 -c '\''import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("ready") and any(s.get("id")=="simulated_scenario" and s.get("state")=="ready" for s in d.get("samples",[])) else 1)'\''; then if curl -fsS --max-time 5 http://127.0.0.1/ | grep -q "<title>Appliance Energy Analyzer</title>"; then exit 0; fi; echo "Frontend root did not serve the expected app." >&2; exit 1; fi; sleep 5; done; echo "Application did not become ready with simulated_scenario available." >&2; sudo journalctl -u aea -n 40 --no-pager >&2; exit 1'

echo "Deployment completed; service and simulated_scenario readiness verified. Verify externally with: curl -fsS http://<elastic-ip>/api/health"
