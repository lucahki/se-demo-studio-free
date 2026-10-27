# Build script/speech.txt (what the voice reads) from script/written.txt (the approved talk track, as captions show it)
# with job.json "respell" (spoken form -> written form), then check that the spoken text maps back to the written text
# exactly, the way captions and alignment read it (lib/speech.py). Use it whenever a script needs respellings, above all
# in a language other than English, where English product names need spelling in that language's sounds
# ("Uèbex" for Webex in Italian) or an [en:word] marker (one word read with English pronunciation, Kokoro only).
# A respelling may also add a pause the captions must not show, e.g. "punto còm," -> "developer.webex.com".
# usage: python3 lib/spoken.py [script/written.txt]
import os, re, sys
from common import JOB, job_config
from speech import paragraphs, segments
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(JOB, 'script', 'written.txt')
R = job_config().get('respell', {})
written = [p.strip() for p in re.split(r'\n\s*\n', open(src).read()) if p.strip()]
def to_spoken(p):
    # longest written form first, whole words only (so "Webex" is not respelled inside "developer.webex.com")
    for sp, w in sorted(R.items(), key=lambda kv: -len(kv[1])):
        p = re.sub(r'(?<![\w.])%s(?![\w])' % re.escape(w), lambda m: sp, p)
    return p
spoken = [to_spoken(p) for p in written]
open(os.path.join(JOB, 'script', 'speech.txt'), 'w').write('\n\n'.join(spoken) + '\n')
back = paragraphs()
bad = [i for i, (a, b) in enumerate(zip(written, back)) if a != b]
for i in bad: print('paragraph %d differs after respelling:\n  written: %s\n  read as: %s' % (i + 1, written[i], back[i]))
if bad or len(back) != len(written): sys.exit('ROUND TRIP FAILED: fix job.json "respell" (spoken -> written) so every respelling maps back')
segments()   # also checks that script/segments.json has one segment per paragraph
print('script/speech.txt: %d paragraphs; round trip ok' % len(spoken))
