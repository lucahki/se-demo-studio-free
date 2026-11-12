#!/bin/bash
# Verify the OpenRouter key in .env (used only for the optional paid voice) without ever printing it. Shows
# usage and the key's credit limit.
cd "$(dirname "$0")/.."
. scripts/platform.sh
EDIT=".env, then open -e .env"; [ $PLATFORM = windows ] && EDIT=".env, then notepad .env"
[ -f .env ] || { echo "OpenRouter key          NOT SET: no .env file yet (cp .env.example .env && chmod 600 $EDIT)"; exit 1; }
# read as plain text (scripts/platform.sh), never run: running .env printed a stray line once (2026-11-11)
( OPENROUTER_API_KEY=$(env_value OPENROUTER_API_KEY)
  [ -z "${OPENROUTER_API_KEY:-}" ] && { echo "OpenRouter key          NOT SET in .env (OPENROUTER_API_KEY=)"; env_layout OPENROUTER_API_KEY; exit 1; }
  # the key header goes in on stdin (-H @-, printf is a shell builtin), so it never shows in the process list
  R=$(printf 'Authorization: Bearer %s\n' "$OPENROUTER_API_KEY" | "${CURL[@]}" -s -m 20 -w '\n%{http_code}' https://openrouter.ai/api/v1/key -H @-)
  CODE=$(echo "$R" | tail -1); BODY=$(echo "$R" | sed '$d')
  if [ "$CODE" != "200" ]; then echo "OpenRouter key          REJECTED (HTTP $CODE): check the key in .env"; exit 1; fi
  echo "$BODY" | $PYTHON -c "
import json,sys; d=json.load(sys.stdin)['data']
lim=d.get('limit'); rem=d.get('limit_remaining')
print('%-24s ok (used \$%.2f, limit %s, remaining %s)' % ('OpenRouter key', d.get('usage') or 0, 'none' if lim is None else '\$%.2f'%lim, 'n/a' if rem is None else '\$%.2f'%rem))
if lim is None: print('%-24s NO CREDIT LIMIT: set one on this key at https://openrouter.ai/settings/keys so a runaway job cannot overspend' % 'OpenRouter limit'); sys.exit(1)
" )
