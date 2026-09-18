#!/usr/bin/env bash
set -euo pipefail

required_uv='0.8.22'
if ! command -v uv >/dev/null 2>&1; then
  echo "uv ${required_uv} is required" >&2
  exit 1
fi
if [[ "$(uv --version)" != "uv ${required_uv}" ]]; then
  echo "expected uv ${required_uv}, found $(uv --version)" >&2
  exit 1
fi

compile() {
  uv pip compile \
    --python-version 3.12 \
    --generate-hashes \
    --strip-extras \
    --output-file "$2" \
    "$1"
}

compile ha-sync/requirements.txt ha-sync/requirements.lock
compile query-api/requirements.txt query-api/requirements.lock
compile semantic-enrichment/requirements.txt semantic-enrichment/requirements.lock
compile world-model-chat/requirements.txt world-model-chat/requirements.lock
compile quality/application-requirements.in quality/application-requirements.lock
compile quality/ci-requirements.in quality/ci-requirements.lock

python3 -m pip install --dry-run --require-hashes -r quality/ci-requirements.lock >/dev/null
echo 'Dependency locks regenerated and hash installation validated.'
