#!/bin/bash
# Lists jobs that may have left the terminal's Screen Recording or Accessibility on: jobs that recorded a desktop
# app (such as the Webex app), where the permissions were off before the job, and whose clean-up never ran (the
# job stopped early, or the session ended before the final report), or ran but macOS kept one on.
# Reads only jobs/*/logs/permissions.json (written by the job's capture/native.js and capture/app.js); it never
# changes a permission and never builds or runs the capture helper.
# usage: scripts/pending-cleanup.sh     Prints "Permission clean-up: nothing pending" or one PENDING line per job.
#                                       Always exits 0.
cd "$(dirname "$0")/.." || exit 0
. scripts/platform.sh; PYTHON=${PYTHON:-python3}
$PYTHON - <<'PY' || echo "Permission clean-up: could not check (Python did not run)"
import glob, json, os
LABELS = (('screen', 'Screen Recording'), ('accessibility', 'Accessibility'))
pending = []
for f in sorted(glob.glob(os.path.join('jobs', '*', 'logs', 'permissions.json'))):
    job = os.path.basename(os.path.dirname(os.path.dirname(f)))
    try:
        r = json.load(open(f, encoding='utf-8'))
    except (OSError, ValueError):
        pending.append((job, 'its record logs/permissions.json is unreadable')); continue
    before = r.get('before') or {}
    could = [label for k, label in LABELS if not before.get(k)]   # what this job may have turned on
    if not could or r.get('kept'):
        continue   # both were on before the job, or the owner said to keep them
    rv = r.get('revoked')
    if rv and not rv.get('still_on'):
        continue   # cleaned up
    why = ('the clean-up ran but macOS kept %s on' % ' and '.join(rv['still_on'])) if rv else 'the clean-up never ran'
    status, last = os.path.join('jobs', job, 'STATUS.md'), ''
    if os.path.exists(status):
        lines = [l for l in open(status, encoding='utf-8', errors='replace').read().splitlines() if l.strip()]
        last = lines[-1][:19] if lines else ''
    pending.append((job, '%s %s off before it and %s%s' % (' and '.join(could), 'were' if len(could) > 1 else 'was', why,
                                                            '; last status %s' % last if last else '')))
if not pending:
    print('Permission clean-up: nothing pending')
for job, why in pending:
    print('PENDING permission clean-up: jobs/%s (%s)' % (job, why))
PY
exit 0
