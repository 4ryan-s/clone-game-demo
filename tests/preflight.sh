#!/usr/bin/env bash
# Run before `docker compose build` so a mistake shows up here, not on the server.   bash tests/preflight.sh
set -e
cd "$(dirname "$0")/.."
echo "1/4 syntax";            python3 -m compileall -q server.py config.py engines workers tests *.py
echo "2/4 undefined names";   (python3 -m ruff --version >/dev/null 2>&1 && python3 -m ruff check --select F --quiet .) \
                              || (command -v ruff >/dev/null && ruff check --select F --quiet .) \
                              || python3 -m pyflakes . || echo "   (install ruff or pyflakes to enable this check)"
echo "3/4 compose files";     docker compose config -q && docker compose -f docker-compose.yml -f docker-compose.cpu.yml config -q
echo "4/4 tests";             python3 -m pytest -q tests/test_qwen_routing.py tests/test_pipeline_limits.py tests/test_batcher.py
echo "preflight OK"
