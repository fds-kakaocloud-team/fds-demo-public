#!/usr/bin/env bash
# Run only after this WAS has been removed from the LB and the API has stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
if systemctl is-active --quiet fds-api.service || systemctl is-active --quiet fds-audit-worker.service || systemctl is-active --quiet fds-security.service; then
  echo 'Stop fds-api.service, fds-audit-worker.service and fds-security.service after removing this WAS from the load balancer.' >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Working tree is not clean; refusing to update.' >&2
  exit 1
fi
git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import joblib; [joblib.load('models/'+p) for p in ('fds_model.pkl','context_model.pkl','paysim_model.pkl')]; print('Models loaded successfully')"
echo 'Update prepared. Start services and verify before rejoining the load balancer.'
