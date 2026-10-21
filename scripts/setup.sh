#!/bin/bash
# One-time studio setup and a health check you can rerun any time. Safe to run repeatedly.
# usage: scripts/setup.sh
cd "$(dirname "$0")/.."
ok=1
say() { printf '%-28s %s\n' "$1" "$2"; }
say "Studio version" "$(cat VERSION 2>/dev/null || echo unknown)"
[ "$(uname)" = "Darwin" ] && say "macOS" "ok" || { say "macOS" "MISSING: this studio is built and tested for macOS only"; ok=0; }
if command -v node >/dev/null; then v=$(node -p 'process.versions.node.split(".")[0]'); [ "$v" -ge 20 ] && say "Node.js" "ok ($(node --version))" || { say "Node.js" "TOO OLD: need 20 or newer (brew install node)"; ok=0; }; else say "Node.js" "MISSING: brew install node  (or https://nodejs.org)"; ok=0; fi
if command -v python3 >/dev/null; then say "Python 3" "ok ($(python3 --version 2>&1))"; else say "Python 3" "MISSING: xcode-select --install  (or brew install python)"; ok=0; fi
if command -v claude >/dev/null; then cv=$(claude --version 2>/dev/null | awk '{print $1}'); python3 -c "import sys; sys.exit(0 if tuple(map(int,'$cv'.split('.')[:3])) >= (2,1,300) else 1)" 2>/dev/null && say "Claude Code" "ok ($cv)" || say "Claude Code" "${cv:-unknown}: older than the tested 2.1.300; run claude update"; else say "Claude Code" "claude command not found; the studio is run from the claude command in Terminal"; fi
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; [ -x "$CH" ] || CH="$HOME$CH"
[ -x "$CH" ] && say "Google Chrome" "ok" || { say "Google Chrome" "MISSING: install from https://www.google.com/chrome"; ok=0; }
# Install when the tools are missing, and reinstall when toolkit/package-lock.json changed since the last install.
lockhash=$(shasum -a 256 toolkit/package-lock.json | awk '{print $1}')
if command -v node >/dev/null && { [ ! -d toolkit/node_modules/playwright-core ] || [ "$(cat toolkit/node_modules/.studio-lock-hash 2>/dev/null)" != "$lockhash" ]; }; then
  echo "Installing capture and render tools into toolkit/node_modules (about 400 MB)..."
  (cd toolkit && npm install --no-audit --no-fund --silent) && echo "$lockhash" > toolkit/node_modules/.studio-lock-hash || { say "toolkit install" "FAILED: run (cd toolkit && npm install) and read the error"; ok=0; }
fi
[ -x toolkit/node_modules/ffmpeg-static/ffmpeg ] && say "ffmpeg (bundled)" "ok" || { say "ffmpeg (bundled)" "MISSING: (cd toolkit && npm install)"; ok=0; }
[ -d toolkit/node_modules/playwright-core ] && say "playwright-core" "ok" || { say "playwright-core" "MISSING: (cd toolkit && npm install)"; ok=0; }
# Local voice (Kokoro) and word timing (Whisper): a private Python 3.13 in toolkit/.venv (made by uv, which
# setup installs into toolkit/.uv) and the two models in toolkit/models. About 2.1 GB downloaded once, 2.6 GB on disk.
# No account, key, or admin rights; everything runs on this Mac afterwards.
export UV_PYTHON_INSTALL_DIR="$PWD/toolkit/.python" UV_NO_CACHE=1
UV=toolkit/.uv/bin/uv; PY=toolkit/.venv/bin/python
reqhash=$(shasum -a 256 toolkit/requirements-local.txt | awk '{print $1}')
if command -v python3 >/dev/null && [ "$(cat toolkit/.venv/.studio-req-hash 2>/dev/null)" != "$reqhash" ]; then
  echo "Installing the local voice and transcription tools into toolkit/.venv (about 150 MB download, 700 MB on disk)..."
  { [ -x $UV ] || { python3 -m venv toolkit/.uv && toolkit/.uv/bin/pip install --quiet --disable-pip-version-check uv==0.13.1; }; } &&
  { [ -x $PY ] || $UV venv --quiet --python 3.13 toolkit/.venv; } &&
  $UV pip install --quiet --python $PY --no-deps -r toolkit/requirements-local.txt &&
  echo "$reqhash" > toolkit/.venv/.studio-req-hash || { say "local tools install" "FAILED: rerun scripts/setup.sh and read the error above"; ok=0; }
fi
# fetch <label> <url> <file> <bytes> <sha256>: download once, keep only a file with the expected size and checksum
fetch() {
  [ -f "$3" ] && [ "$(stat -f %z "$3")" = "$4" ] && return 0
  echo "Downloading $1 ($(( $4 / 1000000 )) MB)..."; mkdir -p "$(dirname "$3")"
  if curl -fL --retry 3 --progress-bar -o "$3.part" "$2" && [ "$(shasum -a 256 "$3.part" | awk '{print $1}')" = "$5" ]; then mv "$3.part" "$3"; else rm -f "$3.part"; return 1; fi
}
K=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
W=https://huggingface.co/mlx-community/whisper-large-v3-turbo/resolve/a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb
fetch "Kokoro voice model" $K/kokoro-v1.0.onnx toolkit/models/kokoro/kokoro-v1.0.onnx 325532387 7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 &&
fetch "Kokoro voices" $K/voices-v1.0.bin toolkit/models/kokoro/voices-v1.0.bin 28214398 bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d &&
  say "Kokoro voice (local)" "ok" || { say "Kokoro voice (local)" "DOWNLOAD FAILED: check the network (or proxy) and rerun"; ok=0; }
fetch "Whisper config" $W/config.json toolkit/models/whisper-large-v3-turbo/config.json 268 b34fc29e4e11e0a25e812775dd67f4dd16fc2c8eb43d28ae25ff7d660ecb6379 &&
fetch "Whisper large-v3-turbo" $W/weights.safetensors toolkit/models/whisper-large-v3-turbo/weights.safetensors 1613977612 951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6 &&
  say "Whisper (local)" "ok" || { say "Whisper (local)" "DOWNLOAD FAILED: check the network (or proxy) and rerun"; ok=0; }
[ -x $PY ] && $PY -c "import kokoro_onnx, mlx_whisper" 2>/dev/null && say "local tools (Python $($PY -c 'import platform; print(platform.python_version())'))" "ok" || { say "local tools" "BROKEN: delete toolkit/.venv and rerun scripts/setup.sh"; ok=0; }
[ -x toolkit/.venv-chatterbox/bin/python ] && [ -f toolkit/models/chatterbox/t3_cfg.safetensors ] && say "Chatterbox voice (optional)" "installed" || say "Chatterbox voice (optional)" "not installed; only for jobs that pick it (scripts/setup-chatterbox.sh)"
command -v pdftotext >/dev/null && say "pdftotext (optional)" "ok" || say "pdftotext (optional)" "not installed; PDF sources will not fetch (brew install poppler)"
[ -f "$HOME/Library/Application Support/node-terminal/canvas-control/nodeterm.sh" ] && say "NodeTerm" "ok" || say "NodeTerm" "not found (recommended: https://nodeterm.dev); without it the builder runs in a second Terminal window"
echo; if [ $ok = 1 ]; then echo "SETUP OK"; [ -d jobs ] || echo "First time? In Claude, say: do a test run  (about 5 to 10 minutes, free)"; else echo "SETUP INCOMPLETE: fix the lines above, then rerun scripts/setup.sh"; exit 1; fi
