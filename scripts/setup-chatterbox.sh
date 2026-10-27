#!/bin/bash
# Optional: install the Chatterbox voice (Resemble AI, MIT), only when a job picks it. Safe to rerun; it also checks.
# usage: scripts/setup-chatterbox.sh [--multilingual]     (run scripts/setup.sh first)
# About 3.5 GB downloaded once (PyTorch and other packages 300 MB, model 3.2 GB) and 4.5 GB on disk, all inside
# toolkit/. Runs on this Mac afterwards with no network. Remove it with: rm -rf toolkit/.venv-chatterbox toolkit/models/chatterbox
# --multilingual also fetches Chatterbox Multilingual (23 languages, same licence and commit; 3.2 GB more) into
# toolkit/models/chatterbox-mtl, for jobs whose job.json "language" is not English. Remove: rm -rf toolkit/models/chatterbox-mtl
cd "$(dirname "$0")/.."
ok=1; MTL=0; [ "$1" = "--multilingual" ] || [ -d toolkit/models/chatterbox-mtl ] && MTL=1
say() { printf '%-28s %s\n' "$1" "$2"; }
export UV_PYTHON_INSTALL_DIR="$PWD/toolkit/.python" UV_NO_CACHE=1
UV=toolkit/.uv/bin/uv; PY=toolkit/.venv-chatterbox/bin/python
[ -x $UV ] || { say "uv" "MISSING: run scripts/setup.sh first"; exit 1; }
reqhash=$(shasum -a 256 toolkit/requirements-chatterbox.txt | awk '{print $1}')
# a venv whose own Python no longer starts (for example made from a Python that was later deleted) is rebuilt
if [ -e toolkit/.venv-chatterbox ] && ! $PY -c 1 2>/dev/null; then
  echo "toolkit/.venv-chatterbox cannot start its Python; rebuilding it."; rm -rf toolkit/.venv-chatterbox
fi
if [ "$(cat toolkit/.venv-chatterbox/.studio-req-hash 2>/dev/null)" != "$reqhash" ]; then
  echo "Installing Chatterbox and PyTorch into toolkit/.venv-chatterbox (about 300 MB download, 1.3 GB on disk)..."
  { [ -x $PY ] || $UV venv --quiet --python 3.11 toolkit/.venv-chatterbox; } &&
  $UV pip install --quiet --python $PY --no-deps -r toolkit/requirements-chatterbox.txt &&
  echo "$reqhash" > toolkit/.venv-chatterbox/.studio-req-hash || { say "Chatterbox install" "FAILED: rerun and read the error above"; ok=0; }
fi
# fetch <label> <url> <file> <bytes> <sha256>: download once, keep only a file with the expected size and checksum
fetch() {
  [ -f "$3" ] && [ "$(stat -f %z "$3")" = "$4" ] && return 0
  echo "Downloading $1 ($(( $4 / 1000000 )) MB)..."; mkdir -p "$(dirname "$3")"
  if curl -fL --retry 3 --progress-bar -o "$3.part" "$2" && [ "$(shasum -a 256 "$3.part" | awk '{print $1}')" = "$5" ]; then mv "$3.part" "$3"; else rm -f "$3.part"; return 1; fi
}
C=https://huggingface.co/ResembleAI/chatterbox/resolve/5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18; D=toolkit/models/chatterbox
fetch "Chatterbox voice encoder" $C/ve.safetensors $D/ve.safetensors 5695784 f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c &&
fetch "Chatterbox text-to-speech" $C/t3_cfg.safetensors $D/t3_cfg.safetensors 2129653744 914cb1696f47527fe8852ca8f1fe1fa63cb34f76f9c715e84e067b744dd0da81 &&
fetch "Chatterbox speech decoder" $C/s3gen.safetensors $D/s3gen.safetensors 1056484620 2b78103c654207393955e4900aac14a12de8ef25f4b09424f1ef91941f161d4e &&
fetch "Chatterbox tokenizer" $C/tokenizer.json $D/tokenizer.json 25470 d71e3a44eabb1784df9a68e9f95b251ecbf1a7af6a9f50835856b2ca9d8c14a5 &&
fetch "Chatterbox built-in voice" $C/conds.pt $D/conds.pt 107374 6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e &&
  say "Chatterbox model" "ok" || { say "Chatterbox model" "DOWNLOAD FAILED: check the network (or proxy) and rerun"; ok=0; }
if [ $MTL = 1 ]; then
  M=toolkit/models/chatterbox-mtl
  fetch "Multilingual voice encoder" $C/ve.pt $M/ve.pt 5698626 4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1 &&
  fetch "Multilingual built-in voice" $C/conds.pt $M/conds.pt 107374 6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e &&
  fetch "Multilingual tokenizer" $C/grapheme_mtl_merged_expanded_v1.json $M/grapheme_mtl_merged_expanded_v1.json 69989 69632f47220a788a52ce2661d096453c5655e9bf25289d89a8d832c46ee07dbf &&
  fetch "Multilingual Chinese table" $C/Cangjie5_TC.json $M/Cangjie5_TC.json 1920163 7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c &&
  fetch "Multilingual speech decoder" $C/s3gen.pt $M/s3gen.pt 1057165844 9b9ff07e60b20c136e2b1b3d7563a24604e8d2c4c267888d1ee929dd0151d2a3 &&
  fetch "Multilingual text-to-speech" $C/t3_mtl23ls_v2.safetensors $M/t3_mtl23ls_v2.safetensors 2143989752 b1237586127ce98e7800a68e49938eb5092846862aabcb6e17b2fda7889a6c75 &&
    say "Chatterbox Multilingual" "ok" || { say "Chatterbox Multilingual" "DOWNLOAD FAILED: check the network (or proxy) and rerun"; ok=0; }
fi
[ -x $PY ] && $PY -c "import chatterbox.tts, chatterbox.mtl_tts, perth; assert perth.PerthImplicitWatermarker" 2>/dev/null && say "Chatterbox (local)" "ok" || { say "Chatterbox (local)" "BROKEN: delete toolkit/.venv-chatterbox and rerun"; ok=0; }
echo; if [ $ok = 1 ]; then echo "CHATTERBOX OK"; else echo "CHATTERBOX INCOMPLETE: fix the lines above, then rerun scripts/setup-chatterbox.sh"; exit 1; fi
