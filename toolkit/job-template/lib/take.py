# Record one voice take or audition with Kokoro, a free voice model that runs on this Mac (no network, no cost).
# usage: python3 lib/take.py NAME [VOICE] [--speed 1.0] [--text script/speech.txt] [--dir audio/takes] [--engine kokoro|say]
# VOICE and speed default to job.json "voice" ({"name": "am_michael", "speed": 1.0}); list voices with lib/audition.py --list.
# Each paragraph is read on its own and joined with --gap seconds of silence, so build_voice.py can cut at paragraph
# gaps. Output: <dir>/NAME.wav (24 kHz mono) plus NAME.log.
# --engine say uses macOS `say` for a quick DRAFT only: Apple licenses its system voices for personal,
# non-commercial use, so a say take must never reach a video that is shared.
import argparse, json, os, re, subprocess, tempfile, time, wave
from common import use_local_python, job_config, run_ff, KOKORO
ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('voice', nargs='?')
ap.add_argument('--speed', type=float); ap.add_argument('--engine', default='kokoro', choices=['kokoro', 'say'])
ap.add_argument('--text', default='script/speech.txt'); ap.add_argument('--dir', default='audio/takes')
ap.add_argument('--gap', type=float, default=0.7)
a = ap.parse_args()
V = job_config().get('voice') or {}
voice = a.voice or (V.get('name') if a.engine == 'kokoro' else None) or ('am_michael' if a.engine == 'kokoro' else None)
speed = a.speed or float(V.get('speed', 1.0))
os.makedirs(a.dir, exist_ok=True)
paras = [p.strip() for p in re.split(r'\n\s*\n', open(a.text).read()) if p.strip()]
SR = 24000; out = bytearray(); gap = b'\0\0' * int(a.gap * SR)
t = time.time()
if a.engine == 'kokoro':
    use_local_python()
    import numpy as np
    from kokoro_onnx import Kokoro
    if not all(os.path.exists(f) for f in KOKORO):
        raise SystemExit('Kokoro model files are missing. Run scripts/setup.sh from the studio root.')
    k = Kokoro(*KOKORO)
    if voice not in k.get_voices():
        raise SystemExit('Unknown Kokoro voice %r. List them with: python3 lib/audition.py --list' % voice)
    lang = 'en-gb' if voice.startswith('b') else 'en-us'
    for i, p in enumerate(paras):
        audio, sr = k.create(p, voice=voice, speed=speed, lang=lang)
        out += (np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes() + (gap if i < len(paras) - 1 else b'')
else:
    print('DRAFT ONLY: macOS system voices are licensed for personal, non-commercial use. Do not use this take in a shared video.')
    with tempfile.TemporaryDirectory() as tmp:
        for i, p in enumerate(paras):
            src, aiff, raw = os.path.join(tmp, 'p.txt'), os.path.join(tmp, 'p.aiff'), os.path.join(tmp, 'p.pcm')
            open(src, 'w').write(p)
            subprocess.run(['say', '-o', aiff, '-f', src] + (['-v', voice] if voice else []) + (['-r', str(int(175 * speed))] if speed != 1.0 else []), check=True)
            run_ff(['-i', aiff, '-f', 's16le', '-ac', '1', '-ar', str(SR), raw])
            out += open(raw, 'rb').read() + (gap if i < len(paras) - 1 else b'')
wav = os.path.join(a.dir, a.name + '.wav')
w = wave.open(wav, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(out)); w.close()
info = {'out': wav, 'engine': a.engine, 'voice': voice, 'speed': speed, 'paragraphs': len(paras), 'seconds': round(len(out) / 2 / SR, 1),
        'secs': round(time.time() - t, 1), 'words': sum(len(p.split()) for p in paras)}
if a.engine == 'say': info['license'] = 'draft only: macOS system voice, personal non-commercial use'
open(os.path.join(a.dir, a.name + '.log'), 'w').write(json.dumps(info))
print(json.dumps(info))
