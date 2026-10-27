# Final mix: voice (EQ, light compression), the owner's music under the whole video, and the quiet recorded click/key
# effects, mastered to -16 LUFS integrated with a -1.5 dBTP limiter.
# Music is optional and off by default: there is no music generator. To use your own track (one you have the rights
# to), put it in audio/music/ and set job.json "music" "file". lib/music_bed.py (run from here when needed) fits the
# track to the video so its own ending lands at the end. Settings in job.json "music", first set by ear on 2026-10-20:
#   level_db = bed loudness relative to the voice's measured loudness (default -20 LU)
#   duck_db  = extra reduction while the SE speaks (default -6 dB), with 0.35 s ramps, held through pauses under 1.2 s
#              so it does not pump between sentences
#   intro_boost_db = louder music while it plays alone before the first word, easing down over 0.8 s just before it
#              (default 9; 11 was picked by ear)
#   end_slide_seconds = length of the closing fade (default: from just after the last word to the end)
# The music fades in over 2 s. Give it a lead-in with script/segments.json "intro_seconds" (bed.json "beat_near_3s"
# puts the first word on a beat).
# usage: python3 lib/mix.py out/mix.wav [--from S --to S]   (a window renders an excerpt, e.g. the agenda sample)
# Prints the measured voice-to-music difference, under speech and between phrases, and writes it to build/mix_levels.json.
import argparse, json, os, subprocess, sys, wave
from common import use_local_python, run_ff, job_config, FF, JOB
use_local_python()
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--from', dest='t0', type=float, default=0); ap.add_argument('--to', dest='t1', type=float)
a = ap.parse_args()
C = json.load(open('build/cues.json')); TOT = C['total']; SR = 48000; n = int(round(TOT * SR))
M = job_config().get('music') or {}
LVL = float(M.get('level_db', -20)); DUCK = float(M.get('duck_db', -6)); BOOST = float(M.get('intro_boost_db', 9));
E_io = lambda k: np.where(k < .5, 4 * k ** 3, 1 - (-2 * k + 2) ** 3 / 2)
END = float(M['end_slide_seconds']) if 'end_slide_seconds' in M else max(1.5, TOT - C['words'][-1]['e'] - .15)   # fade out after the last word
def read(path, ch=1, filt=None):
    args = [FF, '-v', 'error', '-i', path] + (['-af', filt] if filt else []) + ['-ac', str(ch), '-ar', str(SR), '-f', 'f32le', '-']
    y = np.frombuffer(subprocess.run(args, capture_output=True, check=True).stdout, np.float32)
    return y.reshape(-1, ch) if ch > 1 else y
def fit(y):
    return y[:n] if len(y) >= n else np.concatenate([y, np.zeros((n - len(y),) + y.shape[1:], np.float32)])
def lufs(y):   # integrated loudness (EBU R128, gated) of a mono or stereo float signal
    ch = 1 if y.ndim == 1 else y.shape[1]
    r = subprocess.run([FF, '-v', 'info', '-f', 'f32le', '-ar', str(SR), '-ac', str(ch), '-i', '-', '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'],
                       input=np.ascontiguousarray(y, np.float32).tobytes(), capture_output=True)
    for line in r.stderr.decode().splitlines()[::-1]:
        if line.strip().startswith('I:'): return float(line.split()[1])
    return float('nan')
# voice: same chain as the studio's mix
vo = fit(read('audio/voice.wav', 1, 'highpass=f=70,equalizer=f=220:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=1.5,'
                                   'acompressor=threshold=-21dB:ratio=2.5:attack=5:release=120:makeup=2.5dB'))
# speech mask from the word timings: phrases merged across pauses shorter than 0.8 s
sp = []
for w in C['words']:
    if sp and w['t'] - sp[-1][1] < 1.2: sp[-1][1] = max(sp[-1][1], w['e'])   # hold the duck through gaps under 1.2 s (no pumping)
    else: sp.append([w['t'], w['e']])
t = np.arange(n) / SR; mask = np.zeros(n, np.float32); R = .35
for s0, s1 in sp:   # 1 inside a phrase, ramping over R seconds before and after
    i0, i1 = int(max(0, s0 - R) * SR), int(min(TOT, s1 + R) * SR)
    seg = t[i0:i1]; m = np.minimum(1, np.minimum((seg - (s0 - R)) / R, ((s1 + R) - seg) / R)); mask[i0:i1] = np.maximum(mask[i0:i1], np.clip(m, 0, 1))
mus = np.zeros((n, 2), np.float32)
if M.get('file'):
    if not os.path.exists(M['file']): sys.exit('job.json music file %s does not exist; fix the path or set "file": "".' % M['file'])
    bj = json.load(open('audio/music/bed.json')) if os.path.exists('audio/music/bed.json') else {}
    if not os.path.exists('audio/music/bed.wav') or abs(bj.get('total', -1) - TOT) > .05 or bj.get('file', M['file']) != M['file']:
        subprocess.run([sys.executable, 'lib/music_bed.py', str(TOT)], check=True)
    bed = fit(read('audio/music/bed.wav', 2))
    Lv, Lb = lufs(vo), lufs(bed)
    g = 10 ** ((Lv + LVL - Lb) / 20)                         # bed loudness = voice loudness + level_db
    env = np.minimum(1, t / 2.0)                              # 2 s fade-in
    fo0 = TOT - END; env = env * np.where(t < fo0, 1, np.cos(np.clip((t - fo0) / END, 0, 1) * np.pi / 2) ** 2)   # out over the end slide
    duck = 10 ** (DUCK * mask / 20)                           # extra reduction while speaking
    # louder music in the music-only intro, easing down (0.8 s) to the bed just before the first word
    tw = C['words'][0]['t']; B0, B1 = tw - .95, tw - .15
    boost = np.where(t < B0, BOOST, np.where(t < B1, BOOST * (1 - E_io(np.clip((t - B0) / (B1 - B0), 0, 1))), 0))
    duck = duck * 10 ** (boost / 20)
    mus = bed * (g * env * duck)[:, None]
fx = np.zeros(n, np.float32)
if os.path.exists('build/sfx_events.json'):
    for name, ts, gn in json.load(open('build/sfx_events.json')):
        s = read('audio/sfx/%s.wav' % name) * gn * 10 ** (-6 / 20); o = int(ts * SR); e = min(n, o + len(s))
        if o < n: fx[o:e] += s[:e - o]
mix = mus + (vo + fx)[:, None]
# master: integrated -16 LUFS, then a peak limiter at -1.5 dBTP
Lm = lufs(mix); mix = mix * 10 ** ((-16 - Lm) / 20)
i0, i1 = int(a.t0 * SR), int((a.t1 or TOT) * SR)
tmp = os.path.join(JOB, 'build', '_mix_pre.f32'); np.ascontiguousarray(mix[i0:i1], np.float32).tofile(tmp)
run_ff(['-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', tmp, '-af', 'alimiter=limit=0.84:level=false', '-ar', str(SR), '-c:a', 'pcm_s16le', a.out])
os.remove(tmp)
# measured levels (before mastering gain, which moves voice and music together)
rep = {}
if M.get('file'):
    spk, gap = mask > .99, (mask < .01) & (t > 2.5) & (t < TOT - END)
    def band(y, sel):   # loudness of the stretches where sel is true, joined
        return lufs(y[sel]) if sel.sum() > SR * 3 else float('nan')
    rep = dict(voice_lufs=round(Lv, 1), bed_lufs_raw=round(Lb, 1), level_db=LVL, duck_db=DUCK,
               voice_under_speech=round(band(vo, spk), 1), music_under_speech=round(band(mus, spk), 1),
               music_between_phrases=round(band(mus, gap), 1))
    rep['voice_minus_music_under_speech_db'] = round(rep['voice_under_speech'] - rep['music_under_speech'], 1)
    rep['voice_minus_music_between_phrases_db'] = round(rep['voice_under_speech'] - rep['music_between_phrases'], 1)
    intro = (t >= 1.5) & (t < B0 + .2)                       # the loudest stretch of the music-only intro (end of the fade-in, start of the ease-down)
    if intro.sum() > SR * .5:
        rep['music_intro_lufs_momentary'] = round(lufs(np.concatenate([mus[intro]] * 4)), 1)   # repeated to reach the 400 ms gate
        rep['voice_minus_music_intro_db'] = round(rep['voice_under_speech'] - rep['music_intro_lufs_momentary'], 1)
    rep['intro_first_word_s'] = round(tw, 2)
rep['master_gain_db'] = round(-16 - Lm, 1); rep['excerpt'] = [a.t0, a.t1 or TOT]
rep = {k: (None if isinstance(v, float) and v != v else v) for k, v in rep.items()}   # NaN (too little to measure) -> null
json.dump(rep, open('build/mix_levels.json', 'w'), indent=1)
print('wrote', a.out); print(json.dumps(rep))
