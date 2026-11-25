#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-web.txt
export MESA_SECRET_KEY="${MESA_SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_hex(32))')}"
python -m web.app
