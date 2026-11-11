#!/bin/bash
# Sourced by the studio scripts, not run on its own: what differs between macOS and Windows (Git Bash).
#   PLATFORM  mac | windows | other
#   PYTHON    a Python 3 that runs. On Windows `python3` is usually the Microsoft Store placeholder, which only
#             prints an install message, so `python` and `py` are tried as well. Empty when there is none.
#   CURL      curl and the options this machine needs (use as "${CURL[@]}"). On a company network that inspects
#             TLS, Windows cannot check the certificate's revocation and curl refuses to connect;
#             --ssl-revoke-best-effort skips that check only when it cannot be done.
#   CHROME    the Google Chrome program, or empty when it is not installed
#   VENV_BIN  the folder inside a Python venv that holds its programs (bin, or Scripts on Windows)
#   EXE       the suffix of a program file ("" or .exe)
#   winpath   winpath <path>: the path as a Windows program needs it (unchanged on macOS)
#   filesize  filesize <file>: its size in bytes
# Safe to source under set -e: nothing here fails when a program is not found.
case "$(uname -s)" in
  Darwin) PLATFORM=mac ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM=windows ;;
  *) PLATFORM=other ;;
esac
PYTHON=
for p in python3 python py; do if "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then PYTHON=$p; break; fi; done
CURL=(curl); VENV_BIN=bin; EXE=; CHROME=
if [ $PLATFORM = windows ]; then
  CURL+=(--ssl-revoke-best-effort); VENV_BIN=Scripts; EXE=.exe
  for d in "$(cygpath -u "${PROGRAMFILES:-C:\\Program Files}")" "/c/Program Files (x86)" "$(cygpath -u "${LOCALAPPDATA:-C:\\}")"; do
    if [ -x "$d/Google/Chrome/Application/chrome.exe" ]; then CHROME="$d/Google/Chrome/Application/chrome.exe"; break; fi
  done
else
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if [ -x "$c" ]; then CHROME=$c; break; fi
  done
fi
winpath() { if [ $PLATFORM = windows ]; then cygpath -w "$1"; else printf '%s\n' "$1"; fi; }
filesize() { wc -c < "$1" | tr -d ' '; }
# env_value NAME: the value of NAME=... in the studio .env, read as plain text (never run as shell code, so a stray
# line can never be printed in an error). Empty when missing. Never echo what it returns.
env_value() {
  [ -f .env ] || return 0
  awk -v k="$1" '{ sub(/\r$/, "") }
    $0 ~ "^[[:space:]]*" k "[[:space:]]*=" { sub(/^[^=]*=[[:space:]]*/, ""); v = $0 }
    END { sub(/[[:space:]]+$/, "", v); gsub(/^["\047]|["\047]$/, "", v); printf "%s", v }' .env
}
# env_layout NAME: a hint, by line number only (never the line's content), when .env holds a line that is not a
# comment, blank, or NAME=value, for example a key pasted on its own line below its name.
env_layout() {
  [ -f .env ] || return 0
  awk -v k="$1" '{ sub(/\r$/, "") }
    /^[[:space:]]*(#|$)/ { next }
    /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/ { name = $0; sub(/[[:space:]]*=.*/, "", name); sub(/^[[:space:]]*/, "", name); last = name; lastnr = NR; next }
    { if (last == k && lastnr == NR - 1) printf "line %d of .env looks like the key on its own line: put it right after %s= on the same line, with no space\n", NR, k
      else printf "line %d of .env is not NAME=value (the line is not shown here); fix or delete it\n", NR }' .env
}
