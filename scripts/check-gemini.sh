#!/bin/bash
# Verify the Google AI Studio key in .env (used only for the optional Gemini voice) without ever printing it. Makes
# free requests only: the list of models (is the Gemini speech model available to the key?) and the list of the
# custom voices in the key's Google project (made in AI Studio: Voice design, remixing, or replication), with the
# IDs to put in job.json. usage: scripts/check-gemini.sh [--library it-IT]
#   --library LANG  also lists Google's Extended Voice Library voices for that language (id, name, description)
cd "$(dirname "$0")/.."
. scripts/platform.sh
LIB=; [ "${1:-}" = "--library" ] && LIB=${2:?usage: scripts/check-gemini.sh --library it-IT}
EDIT=".env, then open -e .env"; [ $PLATFORM = windows ] && EDIT=".env, then notepad .env"
[ -f .env ] || { echo "Gemini key              NOT SET: no .env file yet (cp .env.example .env && chmod 600 $EDIT)"; exit 1; }
# read as plain text (scripts/platform.sh), never run: running .env printed a stray line once (2026-11-11)
( GEMINI_API_KEY=$(env_value GEMINI_API_KEY)
  [ -z "${GEMINI_API_KEY:-}" ] && { echo "Gemini key              NOT SET in .env (GEMINI_API_KEY=)"; env_layout GEMINI_API_KEY; exit 1; }
  # the key header goes in on stdin (-H @-, printf is a shell builtin), so it never shows in the process list
  R=$(printf 'x-goog-api-key: %s\n' "$GEMINI_API_KEY" | "${CURL[@]}" -s -m 20 -w '\n%{http_code}' "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000" -H @-)
  RC=$?; CODE=$(echo "$R" | tail -1); BODY=$(echo "$R" | sed '$d')
  if [ $RC -ne 0 ] || [ "$CODE" = "000" ]; then echo "Gemini key              NO CONNECTION: could not reach Google (network or proxy)"; exit 1; fi
  case "$CODE" in
    200) ;;
    400|401|403) echo "Gemini key              REJECTED (HTTP $CODE): check GEMINI_API_KEY in .env, or make a new key in Google AI Studio"; exit 1 ;;
    429) echo "Gemini key              LIMIT REACHED (HTTP 429): the key works but its project is over a rate limit; try again later"; exit 1 ;;
    *) echo "Gemini key              ERROR (HTTP $CODE) from Google; try again later"; exit 1 ;;
  esac
  echo "$BODY" | $PYTHON -c "
import json,sys; names=[m.get('name','') for m in json.load(sys.stdin).get('models',[])]
tts=sorted(n.split('/')[-1] for n in names if 'tts' in n)
if 'models/gemini-3.8-flash-tts' in names: print('%-24s ok (speech models: %s)' % ('Gemini key', ', '.join(tts)))
else: print('%-24s works, but gemini-3.8-flash-tts is not listed for it (speech models: %s)' % ('Gemini key', ', '.join(tts) or 'none')); sys.exit(1)
"; ST=$?
  # voices: informational, never a failure
  voices() {   # voices <title> <query...>: one line per voice, id first
    local Q=(-G "https://generativelanguage.googleapis.com/v1beta/voices" --data-urlencode "page_size=1000")
    for q in "${@:2}"; do Q+=(--data-urlencode "$q"); done
    local V; V=$(printf 'x-goog-api-key: %s\n' "$GEMINI_API_KEY" | "${CURL[@]}" -s -m 20 -w '\n%{http_code}' "${Q[@]}" -H @-)
    local VC; VC=$(echo "$V" | tail -1)
    if [ "$VC" != "200" ]; then printf '%-24s could not list them (HTTP %s)\n' "$1" "$VC"; return; fi
    echo "$V" | sed '$d' | $PYTHON -c "
import json,sys; vs=json.load(sys.stdin).get('voices',[]); t=sys.argv[1]
g=lambda v,*k: next((v[x] for x in k if v.get(x)), '')
if not vs: print('%-24s none' % t)
for v in vs:
    vid=str(g(v,'id','name')).split('/')[-1]
    print('%-24s %s  %s  %s' % (t, vid, g(v,'display_name','displayName'), ' '.join(str(g(v,k)) for k in ('gender','accent','description') if g(v,k))[:110]))
" "$1"
  }
  voices "Custom voices" "type=prompted" "type=replicated"
  [ -n "$LIB" ] && voices "Library ($LIB)" "type=prebuilt" "language_code=$LIB"
  exit $ST )
