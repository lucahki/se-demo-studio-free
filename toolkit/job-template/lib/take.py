# Record one voice take or audition with the voice engine the owner chose (job.json "voice" "engine"):
#   kokoro      free, on this Mac, about 4x faster than real time (default)
#   chatterbox  free, on this Mac, about 7x SLOWER than real time on an M1 Pro; needs scripts/setup-chatterbox.sh
#   openrouter  paid, sends the script text to OpenRouter; only when the owner chose it and put their key in .env
#   say         macOS voices, DRAFT ONLY (Apple licenses them for personal, non-commercial use)
# usage: python3 lib/take.py NAME [VOICE] [--engine E] [--speed S] [--text script/speech.txt] [--dir audio/takes]
#        chatterbox only: [--seed 1] [--exaggeration 0.5] [--cfg 0.5]     openrouter only: [--model M]
# Defaults come from job.json "voice"; list Kokoro voices with lib/audition.py --list. Output: <dir>/NAME.wav
# (24 kHz mono) plus NAME.log. Kokoro, Chatterbox, and say read each paragraph on its own and join them with --gap
# seconds of silence, so build_voice.py can cut at paragraph gaps; OpenRouter reads the whole text in one call.
# Speed: Kokoro sets it natively; for Chatterbox and OpenRouter it is a pitch-preserving stretch of the take.
import argparse, json, os, re, subprocess, tempfile, time, wave
from common import (use_local_python, use_chatterbox_python, voice_config, run_ff, KOKORO, CHATTERBOX,
                    JOB, check_budget, post, log_cost, generation_cost)
DEFAULTS = {'kokoro': {'name': 'am_michael', 'speed': 1.0},
            # the built-in voice with Resemble's default delivery, 6% slower: chosen by ear on 2026-10-21
            'chatterbox': {'name': 'builtin', 'speed': 0.94, 'seed': 1, 'exaggeration': 0.5, 'cfg_weight': 0.5},
            'openrouter': {'name': 'Iapetus', 'model': 'google/gemini-3.8-flash-tts', 'speed': 1.0},
            'say': {'name': None, 'speed': 1.0}}
ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('voice', nargs='?')
ap.add_argument('--engine', choices=list(DEFAULTS)); ap.add_argument('--speed', type=float)
ap.add_argument('--model'); ap.add_argument('--seed', type=int)
ap.add_argument('--exaggeration', type=float); ap.add_argument('--cfg', type=float)
ap.add_argument('--text', default='script/speech.txt'); ap.add_argument('--dir', default='audio/takes')
ap.add_argument('--gap', type=float, default=0.7)
a = ap.parse_args()
V = voice_config()
engine = a.engine or V['engine']
if engine not in DEFAULTS:
    raise SystemExit('Unknown voice engine %r in job.json "voice". Use one of: %s' % (engine, ', '.join(DEFAULTS)))
S = dict(DEFAULTS[engine], **(V if V['engine'] == engine else {}))   # job.json settings apply to its own engine only
pick = lambda arg, key: arg if arg is not None else S.get(key)
voice, speed = pick(a.voice, 'name'), float(pick(a.speed, 'speed'))
os.makedirs(a.dir, exist_ok=True)
text = open(a.text).read()
paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
SR = 24000; out = bytearray(); gap = b'\0\0' * int(a.gap * SR)
info = {}
t = time.time()
if engine == 'kokoro':
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
elif engine == 'chatterbox':
    use_chatterbox_python()
    import numpy as np, torch
    from chatterbox.tts import ChatterboxTTS
    seed, exa, cfg = int(pick(a.seed, 'seed')), float(pick(a.exaggeration, 'exaggeration')), float(pick(a.cfg, 'cfg_weight'))
    # "builtin" is the voice that ships with the model (MIT). Anything else is a reference clip in the job folder to
    # clone, which the owner must have the rights to use (about 10 s of clean speech).
    ref = None if voice == 'builtin' else os.path.join(JOB, voice)
    if ref and not os.path.exists(ref):
        raise SystemExit('Chatterbox reference clip %s not found. Use "builtin" or a path inside the job folder.' % ref)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    m = ChatterboxTTS.from_local(CHATTERBOX, device)
    if m.sr != SR:
        raise SystemExit('Chatterbox returned %d Hz audio; this script expects %d.' % (m.sr, SR))
    def chunks(p, most=90):
        # Chatterbox stops after about 40 s of speech per call, so split a long paragraph at sentence ends.
        if len(p.split()) <= most:
            return [p]
        out_, cur = [], ''
        for s in re.split(r'(?<=[.!?])\s+', p):
            if cur and len((cur + ' ' + s).split()) > most:
                out_.append(cur); cur = s
            else:
                cur = (cur + ' ' + s).strip()
        return out_ + [cur]
    small = b'\0\0' * int(0.3 * SR)
    for i, p in enumerate(paras):
        parts = chunks(p)
        for j, c in enumerate(parts):
            # Seeded, but on the Mac GPU the same text, settings, and seed still give a slightly different read each
            # run (tested 2026-10-21), so keep the take the owner approved; redo a paragraph with build_voice.py segment=T2.
            torch.manual_seed(seed)
            print('chatterbox: paragraph %d/%d%s' % (i + 1, len(paras), ' part %d/%d' % (j + 1, len(parts)) if len(parts) > 1 else ''), flush=True)
            w = m.generate(c, audio_prompt_path=ref, exaggeration=exa, cfg_weight=cfg).squeeze(0).cpu().numpy()
            out += (np.clip(w, -1, 1) * 32767).astype('<i2').tobytes() + (small if j < len(parts) - 1 else b'')
        out += gap if i < len(paras) - 1 else b''
    info.update(device=device, seed=seed, exaggeration=exa, cfg_weight=cfg, reference=voice,
                license='Chatterbox MIT; every take carries an inaudible Perth watermark marking it as AI speech')
elif engine == 'openrouter':
    use_local_python()   # for its certificate handling (truststore); no local model is used
    model = a.model or S['model']
    check_budget()
    body = {'model': model, 'input': '\n\n'.join(paras), 'voice': voice}
    pcm = 'gemini' in model   # Gemini TTS returns raw 24 kHz PCM; everything else returns MP3
    body['response_format'] = 'pcm' if pcm else 'mp3'
    r = post('/audio/speech', body, timeout=600, raw=True)
    data = r.read(); gid = r.headers.get('X-Generation-Id')
    with tempfile.TemporaryDirectory() as tmp:
        src, raw = os.path.join(tmp, 'in.' + ('pcm' if pcm else 'mp3')), os.path.join(tmp, 'out.pcm')
        open(src, 'wb').write(data)
        run_ff((['-f', 's16le', '-ar', '24000', '-ac', '1'] if pcm else []) + ['-i', src, '-f', 's16le', '-ac', '1', '-ar', str(SR), raw])
        out += open(raw, 'rb').read()
    cost = generation_cost(gid) if gid else None
    log_cost(model, 'voice %s (%s)' % (a.name, voice), cost, gid)
    info.update(model=model, gen=gid, cost=cost, paid=True)
else:
    print('DRAFT ONLY: macOS system voices are licensed for personal, non-commercial use. Do not use this take in a shared video.')
    with tempfile.TemporaryDirectory() as tmp:
        for i, p in enumerate(paras):
            src, aiff, raw = os.path.join(tmp, 'p.txt'), os.path.join(tmp, 'p.aiff'), os.path.join(tmp, 'p.pcm')
            open(src, 'w').write(p)
            subprocess.run(['say', '-o', aiff, '-f', src] + (['-v', voice] if voice else []) + (['-r', str(int(175 * speed))] if speed != 1.0 else []), check=True)
            run_ff(['-i', aiff, '-f', 's16le', '-ac', '1', '-ar', str(SR), raw])
            out += open(raw, 'rb').read() + (gap if i < len(paras) - 1 else b'')
    info['license'] = 'draft only: macOS system voice, personal non-commercial use'
if engine in ('chatterbox', 'openrouter') and speed != 1.0:
    with tempfile.TemporaryDirectory() as tmp:
        src, raw = os.path.join(tmp, 'in.pcm'), os.path.join(tmp, 'out.pcm')
        open(src, 'wb').write(bytes(out))
        run_ff(['-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', src, '-filter:a', 'atempo=%g' % speed, '-f', 's16le', raw])
        out = bytearray(open(raw, 'rb').read())
wav = os.path.join(a.dir, a.name + '.wav')
w = wave.open(wav, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(out)); w.close()
info = dict({'out': wav, 'engine': engine, 'voice': voice, 'speed': speed, 'paragraphs': len(paras),
             'seconds': round(len(out) / 2 / SR, 1), 'secs': round(time.time() - t, 1),
             'words': sum(len(p.split()) for p in paras)}, **info)
open(os.path.join(a.dir, a.name + '.log'), 'w').write(json.dumps(info))
print(json.dumps(info))
