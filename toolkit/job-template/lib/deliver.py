# Captions and player: out/<name>.srt and .vtt from the final word timings (words corrected to the script text),
# and player.html with chapter chips and a clickable narration list (chapters come from script/segments.json).
# A call (cues.json "calls") gets its own captions, one speaker turn at a time, each turn starting with the speaker's
# name ("Anna: ..."), and a line in the list.
# usage: python3 lib/deliver.py <video filename inside out/>
import base64, difflib, html, json, re, sys, unicodedata
from common import job_config, language, LANGS
from speech import paragraphs
video = sys.argv[1]; base = video.rsplit('.', 1)[0]
C = json.load(open('build/cues.json')); cfg = job_config(); paras = paragraphs()
n = lambda s: re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())   # accents folded, as in speech.ntok
def timing(stoks, cw):
    # each script word's (start, end) from the timed words cw ({'w', 't', 'e'}), matched with accents folded
    sm = difflib.SequenceMatcher(a=[n(x) for x in stoks], b=[n(x['w']) for x in cw], autojunk=False)
    timed = [None] * len(stoks)
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(a2 - a1): timed[a1 + k] = (cw[b1 + k]['t'], cw[b1 + k]['e'])
        elif b2 > b1:
            t0, t1 = cw[b1]['t'], cw[b2 - 1]['e']
            for k in range(a2 - a1): timed[a1 + k] = (t0 + (t1 - t0) * k / max(1, a2 - a1), t0 + (t1 - t0) * (k + 1) / max(1, a2 - a1))
    for i in range(len(timed)):
        if timed[i] is None: timed[i] = timed[i - 1] if i else (0, .3)
    return timed
def grouped(stoks):
    groups, cur = [], []
    for i, w in enumerate(stoks):
        cur.append(i); line = ' '.join(stoks[j] for j in cur)
        if re.search(r'[.?!]$', w) or len(line) > 74 or (len(line) > 40 and re.search(r'[,;:]$', w)): groups.append(cur); cur = []
    if cur: groups.append(cur)
    return groups
def fmt(t, sep=','):
    return '%02d:%02d:%02d%s%03d' % (int(t // 3600), int(t % 3600 // 60), int(t % 60), sep, int(round((t % 1) * 1000)) % 1000)
def wrap(words):
    if len(words) > 42:
        cut = words.rfind(' ', 0, len(words) // 2 + 8); words = words[:cut] + '\n' + words[cut + 1:]
    return words
stoks = [w for p in paras for w in p.split()]; timed = timing(stoks, C['words'])
groups = grouped(stoks); caps = []
for g in groups:
    t0 = timed[g[0]][0]; caps.append((t0, max(timed[g[-1]][1], t0 + .8), wrap(' '.join(stoks[j] for j in g))))
for c in C.get('calls', []):
    for l in c['lines']:
        lt = l['text'].split(); lw = [x for x in c['words'] if l['t'] - .3 <= x['t'] <= l['e'] + .3]
        tm = timing(lt, lw) if lw else [(l['t'], l['e'])] * len(lt)
        # a turn that fits on two caption lines stays whole; a longer one is split like the narration
        for k, g in enumerate([list(range(len(lt)))] if len(l['speaker']) + 2 + len(l['text']) <= 84 else grouped(lt)):
            t0 = max(l['t'], tm[g[0]][0]); words = ' '.join(lt[j] for j in g)
            caps.append((t0, max(tm[g[-1]][1], t0 + .8), wrap(('%s: ' % l['speaker'] if k == 0 else '') + words), 1))
caps.sort(key=lambda x: x[0])
# a call caption ends before the next caption starts (two speakers never share the screen)
# (never before it starts: chunks of a turn Whisper missed all share one start time)
caps = [(c[0], max(c[0] + .04, min(c[1], caps[i + 1][0] - .04)) if len(c) > 3 and i + 1 < len(caps) else c[1], c[2]) for i, c in enumerate(caps)]
srt, vtt = [], ['WEBVTT', '']
for k, (t0, t1, words) in enumerate(caps, 1):
    srt.append('%d\n%s --> %s\n%s\n' % (k, fmt(t0), fmt(t1), words)); vtt += ['%s --> %s' % (fmt(t0, '.'), fmt(t1, '.')), words, '']
open('out/%s.srt' % base, 'w').write('\n'.join(srt)); open('out/%s.vtt' % base, 'w').write('\n'.join(vtt))
segs = C['segments']; assert len(segs) == len(paras), (len(segs), len(paras))
items, chaps, last = [], [], None
for s, p in zip(segs, paras):
    ch = s.get('chapter') or s['name']
    if ch != last: chaps.append((s['t0'], ch)); last = ch
    items.append((s['t0'], ch, p))
    for c in C.get('calls', []):
        if c['after'] == s['name']: items.append((c['t0'], ch, ' '.join('%s: %s' % (l['speaker'], l['text']) for l in c['lines'])))
mm = lambda t: '%d:%02d' % (int(t // 60), int(t % 60))
chap_html = ''.join('<button class="chip" data-t="%.2f">%s<span>%s</span></button>' % (t, html.escape(c), mm(t)) for t, c in chaps)
list_html = ''.join('<li><button data-t="%.2f"><span class="t">%s</span><span class="b"><em>%s</em>%s</span></button></li>' % (t, mm(t), html.escape(c), html.escape(p)) for t, c, p in items)
page = (open('lib/player_template.html').read().replace('{{TITLE}}', html.escape(cfg.get('title', 'Demo')))
        .replace('{{DISCLOSURE}}', html.escape(cfg.get('disclosure', ''))).replace('{{VIDEO}}', 'out/' + video)
        .replace('{{LANG}}', language()).replace('{{LANG_NAME}}', LANGS[language()]['name'])
        # captions inline: Chrome will not load a .vtt file next to a page opened from disk
        .replace('{{VTT}}', 'data:text/vtt;base64,' + base64.b64encode('\n'.join(vtt).encode()).decode())
        .replace('{{CHAPTERS}}', chap_html).replace('{{LIST}}', list_html))
open('player.html', 'w').write(page); print('captions', len(caps), 'cues; player.html with', len(chaps), 'chapters')
