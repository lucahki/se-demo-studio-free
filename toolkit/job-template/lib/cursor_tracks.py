# Add the recorded pointer track, click times and key times (in timeline seconds) to build/footage.json, then
# write build/footage.js and build/cues.js for the stage page. Run after lib/build_clips.py.
import bisect, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build'))
from timeline import interp
import edit
meta = json.load(open('build/footage.json'))
for name, c in edit.CLIPS.items():
    if name not in meta: continue
    L = json.load(open('capture/rec/%s/log.json' % c['rec'])); T = L['frames'][0]['t']
    cur = L['cursor']; ct = [p['t'] for p in cur]; keys = meta[name]['keys']; T0 = keys[0][0]; n = meta[name]['n']
    track = []
    for i in range(n):
        s = interp(keys, T0 + i / 30); j = bisect.bisect_right(ct, T + s) - 1
        track.append([round(cur[j]['x'], 1), round(cur[j]['y'], 1)] if j >= 0 else None)
    def to_tl(kind):
        out = []
        for m in L['marks']:
            if m['k'] != kind: continue
            s = m['t'] - T
            for i in range(1, n):
                if interp(keys, T0 + (i - 1) / 30) < s <= interp(keys, T0 + i / 30): out.append(round(T0 + i / 30, 3)); break
        return out
    meta[name]['cursor'] = track; meta[name]['clicks'] = to_tl('click'); meta[name]['keysdown'] = to_tl('key')
json.dump(meta, open('build/footage.json', 'w'))
open('build/footage.js', 'w').write('const FOOT=' + json.dumps(meta) + ';')
open('build/cues.js', 'w').write('const CUES=' + open('build/cues.json').read() + ';')
print({k: ('clicks', v['clicks'], 'keys', len(v['keysdown'])) for k, v in meta.items()})
# Cursor jump check (L66): walk the timeline through SHOTS the way the stage page draws it, in capture pixels
jumps, prev = 0, None
t, end = edit.SHOTS[0][0], edit.SHOTS[-1][1]
while t < end:
    s = next((s for s in edit.SHOTS if s[0] <= t < s[1]), edit.SHOTS[-1]); m = meta[s[2]]
    p = m['cursor'][min(max(int((t - m['t0']) * 30), 0), m['n'] - 1)]
    if p and prev:
        d = math.dist(p, prev[1])
        if prev[0] != s[2] and d > 40: jumps += 1; print(f'CURSOR CUT {t:.2f}: {prev[0]} -> {s[2]}, the cursor lands {d:.0f} px away; fade it (cursorOff) or park it')
        elif prev[0] == s[2] and d > 150: jumps += 1; print(f'CURSOR JUMP {t:.2f}: {s[2]} moves {d:.0f} px in one frame')
    if p: prev = (s[2], p)
    t += 1 / 30
print('cursor check: %s' % ('no jumps' if not jumps else '%d to fix or fade' % jumps))
