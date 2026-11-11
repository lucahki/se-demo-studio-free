# Phone filter: makes a voice sound as if it comes through a phone line (free, on this computer, any voice engine).
# 8 kHz, band 400 to 3000 Hz, +4 dB at 1800 Hz, hard compression, a light bit crush; the level is matched to the dry
# voice. First set by ear on 2026-11-11 (job notes: the owner asked for a stronger filter than a plain band-pass).
# usage: python3 lib/phone.py IN.wav OUT.wav          the whole file on the phone
# lib/take.py --dialogue uses it for the speakers in job.json "dialogue" "phone", only on their lines.
import os, sys, tempfile
from common import use_local_python, run_ff
FILTER = ('aresample=8000,highpass=f=400,highpass=f=400,lowpass=f=3000,lowpass=f=3000,'
          'equalizer=f=1800:t=q:w=1:g=4,acompressor=threshold=-24dB:ratio=8:attack=5:release=60,'
          'acrusher=bits=10:mix=0.25,aresample=24000')
SR = 24000

def _rms(x):
    import numpy as np
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0

def filtered(x):
    # x: float32 mono at 24 kHz -> the same length through the phone chain
    import numpy as np
    with tempfile.TemporaryDirectory() as tmp:
        a, b = os.path.join(tmp, 'a.f32'), os.path.join(tmp, 'b.f32')
        np.ascontiguousarray(x, np.float32).tofile(a)
        run_ff(['-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', a, '-af', FILTER, '-f', 'f32le', '-ar', str(SR), '-ac', '1', b])
        y = np.fromfile(b, np.float32)
    return np.concatenate([y, np.zeros(max(0, len(x) - len(y)), np.float32)])[:len(x)]

def on_phone(x, spans):
    # Put only the given (start, end) seconds on the phone, each stretch level-matched to its dry version and
    # crossfaded over 10 ms at both edges.
    import numpy as np
    y = filtered(x); out = x.copy(); f = int(.01 * SR)
    for s, e in spans:
        a, b = max(0, int(s * SR)), min(len(x), int(e * SR))
        if b - a < 2 * f: continue
        g = _rms(x[a:b]) / max(1e-9, _rms(y[a:b]))
        w = np.ones(b - a, np.float32); w[:f] = np.linspace(0, 1, f); w[-f:] = np.linspace(1, 0, f)
        out[a:b] = x[a:b] * (1 - w) + y[a:b] * g * w
    return np.clip(out, -1, 1)

if __name__ == '__main__':
    use_local_python()
    import numpy as np, wave
    if len(sys.argv) != 3: sys.exit('usage: python3 lib/phone.py IN.wav OUT.wav')
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, 'in.f32')
        run_ff(['-i', sys.argv[1], '-f', 'f32le', '-ar', str(SR), '-ac', '1', raw])
        x = np.fromfile(raw, np.float32)
    y = on_phone(x, [(0, len(x) / SR)])
    w = wave.open(sys.argv[2], 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((y * 32767).astype('<i2').tobytes()); w.close()
    print('wrote', sys.argv[2])
