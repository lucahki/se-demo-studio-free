# Call scripts: a conversation between two people (for example a phone call), read by lib/take.py --dialogue.
# File format (UTF-8), one turn per line:
#   style: a relaxed phone call between two colleagues     (optional; else job.json "dialogue" "style")
#   Anna: Good morning Paolo, how are you?
#   Paolo: Fine, thanks. I just got your email.
# A speaker may be written in bold as in a meeting script (**Anna:** ...). Blank lines, lines starting with #, and
# --- lines are skipped. Every speaker must be in job.json "dialogue" "speakers". Write amounts in words if the voice
# misreads digits. Gemini reads short sounds written in English angle brackets, such as <laugh> or <short pause>.
import json, os, re, difflib
from speech import tokens

LINE = re.compile(r'^\**\s*([^:*]{1,40}?)\s*:\s*\**\s*(.+?)\s*$')
STYLE = re.compile(r'^style\s*:\s*(.*)$', re.I)

def read_call(path):
    style, lines = None, []
    for n, raw in enumerate(open(path), 1):
        s = raw.strip()
        if not s or s.startswith('#') or set(s) <= set('-'):
            continue
        m = STYLE.match(s)
        if m and not lines:
            style = m.group(1).strip(); continue
        m = LINE.match(s)
        if not m:
            raise SystemExit('%s line %d is not "Speaker: text": %r' % (path, n, s[:80]))
        if not tokens(spoken(m.group(2))):
            raise SystemExit('%s line %d has no words, only a sound such as <laugh>: put the sound at the start or end '
                             'of a line with words, so Whisper can time it and the captions show it.' % (path, n))
        lines.append((m.group(1).strip(), m.group(2).strip()))
    if not lines:
        raise SystemExit('%s has no "Speaker: text" lines.' % path)
    return style, lines

def speakers_of(lines):
    out = []
    for sp, _ in lines:
        if sp not in out: out.append(sp)
    return out

def spoken(text):
    # what the voice actually says: angle-bracket sound tags (<laugh>) and [en:word] marks removed
    return re.sub(r'\[en:([^\]]+)\]', r'\1', re.sub(r'<[^>]*>', ' ', text)).strip()

def align(lines, words):
    # Whisper words -> (first word index, last word index) per line, or None; and the wording differences.
    stoks, lidx = [], []
    for i, (_, t) in enumerate(lines):
        for k in tokens(spoken(t)): stoks.append(k); lidx.append(i)
    wt, wi = [], []
    for j, x in enumerate(words):
        for k in tokens(x['word']): wt.append(k); wi.append(j)
    amap, issues = {}, []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(a=stoks, b=wt, autojunk=False).get_opcodes():
        if op == 'equal':
            for k in range(a2 - a1): amap[a1 + k] = wi[b1 + k]
            continue
        ref, hyp = ' '.join(stoks[a1:a2]), ' '.join(wt[b1:b2])
        if ref.replace(' ', '') == hyp.replace(' ', ''):
            for k in range(a2 - a1): amap[a1 + k] = wi[min(b1 + k, b2 - 1)] if b2 > b1 else None
            continue
        issues.append({'line': lidx[min(a1, len(lidx) - 1)], 'script': ref, 'heard': hyp})
    spans = []
    for i in range(len(lines)):
        ks = [amap[k] for k in range(len(stoks)) if lidx[k] == i and amap.get(k) is not None]
        spans.append((ks[0], ks[-1]) if ks else None)
    return spans, issues

def cut_points(spans, words, total):
    # Each line's stretch of the take: from the midpoint of the silence before it to the midpoint after it.
    known = [(i, words[a]['start'], words[b]['end']) for i, s in enumerate(spans) if s for a, b in [s]]
    if len(known) != len(spans):
        missing = [i + 1 for i, s in enumerate(spans) if s is None]
        raise SystemExit('Whisper did not find line(s) %s of the call; listen to the take, and fix the text or redo it.' % missing)
    out = []
    for k, (i, s, e) in enumerate(known):
        c0 = 0.0 if k == 0 else (known[k - 1][2] + s) / 2
        c1 = total if k == len(known) - 1 else (e + known[k + 1][1]) / 2
        out.append((round(s, 3), round(e, 3), round(c0, 3), round(c1, 3)))
    return out

def load_call(job, name):
    # audio/calls/<name>_lines.json, written by lib/take.py --dialogue
    p = os.path.join(job, 'audio', 'calls', name + '_lines.json')
    if not os.path.exists(p):
        raise SystemExit('Call %r is not recorded yet: run python3 lib/take.py %s --dialogue script/calls/%s.txt' % (name, name, name))
    return json.load(open(p))
