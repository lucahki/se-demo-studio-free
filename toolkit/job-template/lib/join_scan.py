# Scan every paragraph join in audio/voice.wav: the level just before each segment's end and just after its start
# (10 ms windows), and any isolated burst in the gaps between segments. A clean join ends and starts in silence or in a
# fade (below -50 dB at the very edge). usage: python3 lib/join_scan.py [wav=audio/voice.wav]
import json, sys, wave
from common import use_local_python
use_local_python()
import numpy as np
P = sys.argv[1] if len(sys.argv) > 1 else 'audio/voice.wav'
w = wave.open(P); SR = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.
C = json.load(open('build/cues.json'))
db = lambda a: 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-12) if len(a) else -240
bad = 0
for i, s in enumerate(C['segments']):
    a, b = int(s['t0'] * SR), int(s['t1'] * SR); n = int(.01 * SR)
    head, tail = db(x[a:a + n]), db(x[b - n:b])
    nxt = C['segments'][i + 1]['t0'] if i + 1 < len(C['segments']) else C['total']
    gap = x[b:int(nxt * SR)]; peak = db(gap[np.argmax(np.abs(gap)) - n // 2: np.argmax(np.abs(gap)) + n // 2]) if len(gap) > n else -240
    flag = tail > -50 or head > -50 or peak > -60
    bad += flag
    print('%-9s start %6.1f dB  end %6.1f dB  loudest in following gap %6.1f dB %s' % (s['name'], head, tail, peak, 'CHECK' if flag else 'ok'))
print('joins needing a look:', bad)
