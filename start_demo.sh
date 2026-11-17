#!/usr/bin/env bash
# Mac/Linux twin of start_demo.ps1: starts the engine workers in the background, then the demo server.
#   ./start_demo.sh            normal
#   ./start_demo.sh --debug    also enables the developer audio preview
cd "$(dirname "$0")" || exit 1
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
get() { $PY -c "import config; print(config.$1)"; }
ENABLED=" $($PY -c "import config; print(' '.join(config.ENGINES))") "
export HF_HOME="$(get HF_HOME)"
mkdir -p logs

start_worker() {  # name engine port python script
  case "$ENABLED" in *" $2 "*) ;; *) return ;; esac
  if (echo > "/dev/tcp/127.0.0.1/$3") 2>/dev/null; then echo "$1 worker already running."; return; fi
  if [ ! -x "$4" ]; then echo "$1: environment not found at $4. Run: python3 setup.py"; return; fi
  nohup "$4" "$5" > "logs/$2.log" 2>&1 &
  echo "$1 worker starting (about 25 s to load); log: logs/$2.log"
}
start_worker Qwen3-TTS qwen3tts 8766 "$(get QWEN_PYTHON)" workers/qwen3tts_server.py

[ "$1" = "--debug" ] && export DEMO_DEBUG=1
echo "Demo at http://localhost:8000   (health: http://localhost:8000/api/health)"
exec $PY -m uvicorn server:app --host 127.0.0.1 --port 8000
