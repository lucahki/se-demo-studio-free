#!/bin/bash
# Render the full video in parallel chunks, then join them and add the mixed audio.
# usage: build/render_par.sh out/<name>_v1.mp4 [chunks=8] [mix.wav=out/mix.wav]
# A five-minute render at 8 chunks takes about 5 minutes on an Apple silicon Mac.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=$1; N=${2:-8}; MIX=${3:-out/mix.wav}
ROOT=$(pwd); while [ ! -f "$ROOT/.demo-studio" ] && [ "$ROOT" != "/" ]; do ROOT=$(dirname "$ROOT"); done
FF="$ROOT/toolkit/node_modules/ffmpeg-static/ffmpeg"; [ -e "$FF" ] || FF="$FF.exe"   # ffmpeg.exe on Windows
# frame count and chunk plan with node, which every studio has (python3 may be missing or the Windows Store placeholder)
TOTALF=$(node -p "Math.round(require('./build/cues.json').total * 30)")
rm -rf out/chunks; mkdir -p out/chunks
PER=$(( (TOTALF + N - 1) / N ))
for (( i = 0; i < N; i++ )); do a=$(( i * PER )); b=$(( (i + 1) * PER < TOTALF ? (i + 1) * PER : TOTALF )); if [ $a -lt $b ]; then echo "$i $a $b"; fi; done > out/chunks/plan.txt
: > out/chunks/list.txt
PIDS=(); CHUNKS=()
while read i a b; do
  node build/render.js video out/chunks/c_$i.mp4 30 $a $b > out/chunks/log_$i.txt 2>&1 &
  PIDS+=($!); CHUNKS+=($i)
  echo "file 'c_$i.mp4'" >> out/chunks/list.txt
done < out/chunks/plan.txt
# wait on each chunk by its pid: a bare `wait` always returns 0, and joining a crashed chunk gives a short video
FAILED=()
for k in "${!PIDS[@]}"; do wait "${PIDS[$k]}" || FAILED+=(${CHUNKS[$k]}); done
if [ ${#FAILED[@]} -gt 0 ]; then
  for i in "${FAILED[@]}"; do echo "Chunk $i failed (out/chunks/log_$i.txt):"; tail -5 out/chunks/log_$i.txt; done
  echo "Render stopped: ${#FAILED[@]} of ${#PIDS[@]} chunks failed; nothing was joined."; exit 1
fi
if grep -l "PAGEERR\|CONSOLE" out/chunks/log_*.txt >/dev/null 2>&1; then echo "Page errors during render:"; grep -h "PAGEERR\|CONSOLE" out/chunks/log_*.txt | sort -u | head -20; fi
"$FF" -y -loglevel error -f concat -safe 0 -i out/chunks/list.txt -c copy out/chunks/video.mp4
if [ -f "$MIX" ]; then
  "$FF" -y -loglevel error -i out/chunks/video.mp4 -i "$MIX" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT"
else
  echo "No mix at $MIX; writing picture only."; cp out/chunks/video.mp4 "$OUT"
fi
echo "done: $OUT ($TOTALF frames)"
