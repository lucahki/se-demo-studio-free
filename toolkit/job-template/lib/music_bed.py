# Build the music bed: audio/music/bed.wav, exactly as long as the video, from the owner's track (job.json "music"
# "file"). The track's own ending is kept so it lands on the end slide: when the track is shorter than the video it is
# lengthened with one or two jumps back into its main section, when it is longer it skips forward once, each jump a
# whole number of bars (8 or more) crossfaded over one bar, at the bar boundaries where the music after the jump sounds
# most like the music it replaces. Within 8 bars of the video's length the track plays as is (padded or trimmed).
# Fades (2 s in, out after the last word) and levels are applied in lib/mix.py, not here; mix.py runs this itself
# when the bed is missing or the video length changed.
# bed.json also gives "beat_near_3s": set script/segments.json "intro_seconds" so the first word lands there (on a beat).
# usage: python3 lib/music_bed.py [total_seconds]   (default: build/cues.json total)  -> audio/music/bed.wav, bed.json
import json, os, subprocess, sys
from common import use_local_python, job_config, FF
use_local_python()
import numpy as np
SR = 48000; SRC = (job_config().get('music') or {}).get('file') or sys.exit('job.json "music" has no "file": nothing to build.')
T = float(sys.argv[1]) if len(sys.argv) > 1 else json.load(open('build/cues.json'))['total']
x = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', SRC, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout, np.float32).reshape(-1, 2)
mono = x.mean(1); N = len(mono); dur = N / SR
# where the track's sound ends (its natural ending): last moment above -40 dB in 0.25 s windows
w = int(.25 * SR); lv = np.array([20 * np.log10(np.sqrt((mono[i:i + w] ** 2).mean()) + 1e-9) for i in range(0, N - w, w)])
end_t = (np.nonzero(lv > -40)[0][-1] + 1) * .25
# beat grid: onset envelope, period by autocorrelation, phase by the largest onset sum
hop = 512; fps = SR / hop; fr = mono[:N // hop * hop].reshape(-1, hop); e = np.log(np.sqrt((fr ** 2).mean(1)) + 1e-6)
on = np.maximum(0, np.diff(e)); on -= on.mean()
ac = np.correlate(on, on, 'full')[len(on) - 1:]; lo, hi = int(fps * 60 / 180), int(fps * 60 / 70)
lag = lo + np.argmax(ac[lo:hi]); lag = lag + (ac[lag + 1] - ac[lag - 1]) / (2 * (2 * ac[lag] - ac[lag - 1] - ac[lag + 1]))   # sub-frame peak
beat = lag / fps
# refine the period over 16 beats, where a frame of error is spread 16 times thinner
c = int(round(16 * lag)); r = np.arange(c - 6, c + 7); pk = r[np.argmax(ac[r])]
pk = pk + (ac[pk + 1] - ac[pk - 1]) / (2 * (2 * ac[pk] - ac[pk - 1] - ac[pk + 1])); beat = pk / 16 / fps; bar = 4 * beat
phase = max(np.arange(0, beat, 1 / fps), key=lambda p: on[np.clip(((np.arange(p, dur - 1, beat)) * fps).astype(int), 0, len(on) - 1)].sum())
# spectral features per beat (log energy in 24 bands) to compare what follows two bar boundaries
F = np.abs(np.fft.rfft(mono[:N // 2048 * 2048].reshape(-1, 2048) * np.hanning(2048), axis=1)); edges = np.unique(np.geomspace(3, F.shape[1] - 1, 25).astype(int))
B = np.log(np.stack([F[:, a:b].mean(1) for a, b in zip(edges[:-1], edges[1:])], 1) + 1e-6); bfps = SR / 2048
def feat(t, beats=8):   # features of the next `beats` beats after time t
    i0, i1 = int(t * bfps), int((t + beats * beat) * bfps); return B[i0:i1].mean(0) if i1 <= len(B) else None
def lvl(t, s=4): a = mono[int(t * SR):int((t + s) * SR)]; return 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-9)
bars = [phase + k * bar for k in range(int(dur / bar)) if 16 <= phase + k * bar <= end_t - 12]   # skip intro and ending
def score(a, b):
    fa, fb = feat(a), feat(b)
    if fa is None or fb is None: return -1e9
    return -np.abs(fa - fb).mean() - .15 * abs(lvl(a) - lvl(b))
need = T - end_t   # seconds to add (or, when negative, to skip) so the track's ending plays at the very end
K = round(need / bar)
def one_jump(k):   # best single jump from bar a to bar b with a - b = k bars (k < 0 skips forward)
    best = None
    for a1 in bars:
        for b1 in bars:
            if round((a1 - b1) / bar) != k: continue
            s = score(a1, b1)
            if not best or s > best[0]: best = (s, [(a1, b1)])
    return best
def two_jumps():
    best = None
    for a1 in bars:
        for b1 in bars:
            j1 = a1 - b1; k1 = round(j1 / bar)
            if k1 < 8 or abs(j1 - k1 * bar) > .05: continue
            j2 = need - j1; k2 = round(j2 / bar)
            if k2 < 8: continue
            s1 = score(a1, b1)
            if best and s1 < best[0] - 1: continue
            for a2 in bars:   # second jump happens later in the track timeline, after pass 2 reaches a2 (> b1)
                if a2 <= b1 + 4 * bar: continue
                b2 = a2 - k2 * bar
                if b2 < 16: continue
                s = s1 + score(a2, b2)
                if not best or s > best[0]: best = (s, [(a1, b1), (a2, b2)])
    return best
if abs(K) < 8: best = (0.0, [])                     # close enough: play the track as is
else:
    best = one_jump(K) if (K < 0 or K <= len(bars)) else None
    if best is None and K > 0: best = two_jumps()
    if best is None:
        sys.exit('The track (%.0f s) cannot be fitted to a %.0f s video with at most two jumps of 8 bars or more. Use a longer '
                 'track, or set job.json "music" "file" to "" for no music.' % (dur, T))
s, jumps = best
def refine(a, b):   # fine-align b to a within +-40 ms by onset-envelope correlation over 4 s
    ia = int(a * fps); best = (-1e9, 0)
    for d in range(-int(.04 * fps), int(.04 * fps) + 1):
        ib = int(b * fps) + d; c = float(np.dot(on[ia:ia + int(4 * fps)], on[ib:ib + int(4 * fps)]))
        if c > best[0]: best = (c, d)
    return b + best[1] / fps
jumps = [(a, refine(a, b)) for a, b in jumps]
xf = bar   # crossfade over one bar, centred on the bar boundary
def seg(t0, t1): return x[int(t0 * SR):int(t1 * SR)]
cuts = [0.0] + [v for a, b in jumps for v in (a, b)] + [dur]   # play cuts[0]..cuts[1], cuts[2]..cuts[3], ...
parts = [seg(max(0, cuts[i] - (xf / 2 if i else 0)), min(dur, cuts[i + 1] + (xf / 2 if i + 1 < len(cuts) - 1 else 0))) for i in range(0, len(cuts), 2)]
n = int(xf * SR); ramp = np.linspace(0, 1, n)[:, None]; out = parts[0]
for p in parts[1:]:
    eqp_in, eqp_out = np.sin(ramp * np.pi / 2), np.cos(ramp * np.pi / 2)   # equal-power crossfade
    out = np.concatenate([out[:-n], out[-n:] * eqp_out + p[:n] * eqp_in, p[n:]])
L = int(T * SR); out = out[:L] if len(out) >= L else np.concatenate([out, np.zeros((L - len(out), 2), np.float32)])
pcm = (np.clip(out, -1, 1) * 32767).astype('<i2').tobytes(); os.makedirs('audio/music', exist_ok=True)
subprocess.run([FF, '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', '-', 'audio/music/bed.wav'], input=pcm, check=True)
# where each jump lands on the video timeline
tl, info_j, pos = 0.0, [], 0.0
for a, b in jumps:
    tl += a - pos; info_j.append(dict(at_video=round(tl, 2), from_track=round(a, 2), to_track=round(b, 2), bars=round((a - b) / bar))); pos = b
end_tl = tl + (end_t - pos)
info = dict(file=SRC, total=T, track=round(dur, 2), track_sound_ends=round(end_t, 2), bpm=round(60 / beat, 2), bar_s=round(bar, 3), beat_s=round(beat, 4), beat_phase_s=round(float(phase), 4),
            jumps=info_j, crossfade_s=round(xf, 3), track_ending_lands_at_video=round(end_tl, 2), score=round(float(s), 3),
            beat_near_3s=round(float(phase + round((3.0 - phase) / beat) * beat), 3))
json.dump(info, open('audio/music/bed.json', 'w'), indent=1); print(json.dumps(info))
