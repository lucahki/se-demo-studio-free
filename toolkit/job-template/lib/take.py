# Record one voice take or audition with the voice engine the owner chose (job.json "voice" "engine"):
#   kokoro      free, on this computer, about 4x faster than real time (default)
#   chatterbox  free, on a Mac, about 7x SLOWER than real time on an M1 Pro; needs scripts/setup-chatterbox.sh
#   openrouter  paid, sends the script text to OpenRouter; only when the owner chose it and put their key in .env
#   gemini      Google Gemini speech with the owner's own Google AI Studio key in .env (free tier, or paid); sends the
#               script text to Google; only when the owner chose it
#   say         macOS voices, Mac only, DRAFT ONLY (Apple licenses them for personal, non-commercial use)
# usage: python3 lib/take.py NAME [VOICE] [--engine E] [--speed S] [--text script/speech.txt] [--dir audio/takes]
#        chatterbox only: [--seed 1] [--exaggeration 0.5] [--cfg 0.5]     openrouter and gemini: [--model M]
#        gemini only: [--style "calm and assured"] (a short delivery style, sent apart from the text). VOICE is one of
#        the 30 built-in names or a custom voice ID made in Google AI Studio (voice_..., same Google project as the key)
# A call between two people (lib/dialogue.py has the file format; settings in job.json "dialogue"):
#        python3 lib/take.py NAME --dialogue script/calls/NAME.txt [--engine gemini|kokoro] [--speakers Anna=Kore,Paolo=Puck]
#                                [--phone Paolo|none] [--style S] [--dir audio/calls] [--mode together|per_line]
#   Gemini "together" reads the whole call in one request with two voices that react to each other (at most two
#   speakers, built-in voices only); "per_line" reads each line in its own request, which is how a custom voice ID
#   (voice_...) can speak in a call, but each line is read without hearing the one before. Per line, each line's
#   audio is kept in <dir>/NAME_parts/; a rerun asks Google again only for lines whose text, voice, style, or model
#   changed, or those named with --redo 3,7 (line numbers from 1), so the lines already approved stay as they are.
#   The default ("auto",
#   job.json "dialogue" "mode") is together when every voice is built in, else per_line. Kokoro reads each line with
#   its speaker's voice. Then local Whisper times each line (NAME_raw_words.json), the wording differences are
#   listed, and the speakers in "phone" go on the phone (lib/phone.py), only on their own lines. Output:
#   <dir>/NAME_raw.wav (as read), NAME.wav (with the phone filter), NAME_lines.json (each line's timing, for
#   build_voice.py, mix.py, and the captions; the caption text uses job.json "respell", spoken -> written, so a
#   word written as said, such as "iva", shows as "IVA"), and NAME.log.
# Defaults come from job.json "voice"; list Kokoro voices with lib/audition.py --list. Output: <dir>/NAME.wav
# (24 kHz mono) plus NAME.log. Kokoro, Chatterbox, and say read each paragraph on its own and join them with --gap
# seconds of silence, so build_voice.py can cut at paragraph gaps; OpenRouter reads the whole text in one call.
# Speed: Kokoro sets it natively; for Chatterbox and OpenRouter it is a pitch-preserving stretch of the take.
# Language: job.json "language" (default "en"). Kokoro then needs a voice of that language (if_/im_ for Italian), and
# Chatterbox uses Chatterbox Multilingual (scripts/setup-chatterbox.sh --multilingual). In a non-English script,
# [en:word] reads one word with English pronunciation (Kokoro), e.g. "Usa [en:OAuth] per l'autenticazione"; captions
# show the word without the brackets. Other engines read the plain word.
import argparse, base64, json, os, re, subprocess, sys, tempfile, time, wave
from common import (use_local_python, use_chatterbox_python, voice_config, run_ff, KOKORO, CHATTERBOX, CHATTERBOX_MTL,
                    JOB, LANGS, language, check_budget, post, log_cost, generation_cost, WINDOWS, job_config,
                    gemini_post, gemini_cost, GEMINI_VOICES)
DEFAULTS = {'kokoro': {'name': 'am_michael', 'speed': 1.0},
            # the built-in voice with Resemble's default delivery, 6% slower: chosen by ear on 2026-10-21
            'chatterbox': {'name': 'builtin', 'speed': 0.94, 'seed': 1, 'exaggeration': 0.5, 'cfg_weight': 0.5},
            'openrouter': {'name': 'Iapetus', 'model': 'google/gemini-3.8-flash-tts', 'speed': 1.0},
            # the same Google model as the OpenRouter default, called directly with the owner's Google AI Studio key
            'gemini': {'name': 'Iapetus', 'model': 'gemini-3.8-flash-tts', 'speed': 1.0, 'style': ''},
            'say': {'name': None, 'speed': 1.0}}
ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('voice', nargs='?')
ap.add_argument('--engine', choices=list(DEFAULTS)); ap.add_argument('--speed', type=float)
ap.add_argument('--model'); ap.add_argument('--seed', type=int)
ap.add_argument('--exaggeration', type=float); ap.add_argument('--cfg', type=float)
ap.add_argument('--text', default='script/speech.txt'); ap.add_argument('--dir')
ap.add_argument('--gap', type=float, default=0.7); ap.add_argument('--style')
ap.add_argument('--dialogue'); ap.add_argument('--speakers'); ap.add_argument('--phone')
ap.add_argument('--mode', choices=['auto', 'together', 'per_line']); ap.add_argument('--redo')
a = ap.parse_args()
SR = 24000

def gemini_speech(model, parts, speech_config):
    # One request to Google (lib/common.py gemini_post; the key never leaves that function). Returns 16-bit 24 kHz
    # mono PCM, the cost at paid-tier prices, and the token counts. Gemini 3.8 returns a WAV file; older models
    # returned raw PCM, so both are read.
    body = {'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': {'responseModalities': ['AUDIO'], 'speechConfig': speech_config}}
    r = gemini_post(model, body)
    try:
        inline = next(p['inlineData'] for p in r['candidates'][0]['content']['parts'] if 'inlineData' in p)
    except (KeyError, IndexError, StopIteration):
        raise SystemExit('GEMINI returned no audio (often a safety block or an empty text): %s' % json.dumps(r)[:600])
    data, mime = base64.b64decode(inline['data']), inline.get('mimeType', '')
    rate = re.search(r'rate=(\d+)', mime)
    with tempfile.TemporaryDirectory() as tmp:
        src, raw = os.path.join(tmp, 'in.audio'), os.path.join(tmp, 'out.pcm')
        open(src, 'wb').write(data)
        head = [] if data[:4] == b'RIFF' else ['-f', 's16le', '-ar', rate.group(1) if rate else '24000', '-ac', '1']
        run_ff(head + ['-i', src, '-f', 's16le', '-ac', '1', '-ar', str(SR), raw])
        pcm = open(raw, 'rb').read()
    u = r.get('usageMetadata') or {}
    t_in = int(u.get('promptTokenCount') or 0)
    t_out = int(u.get('candidatesTokenCount') or round(len(pcm) / 2 / SR * 25))   # 25 audio tokens per second
    return pcm, gemini_cost(model, t_in, t_out), {'in': t_in, 'out': t_out}

def stretch(pcm, speed):
    # pitch-preserving speed change of 16-bit 24 kHz mono PCM
    with tempfile.TemporaryDirectory() as tmp:
        src, raw = os.path.join(tmp, 'in.pcm'), os.path.join(tmp, 'out.pcm')
        open(src, 'wb').write(bytes(pcm))
        run_ff(['-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', src, '-filter:a', 'atempo=%g' % speed, '-f', 's16le', raw])
        return open(raw, 'rb').read()

def write_wav(path, pcm):
    w = wave.open(path, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(pcm)); w.close()

if a.dialogue:
    # ---- a call between two people (job.json "dialogue") ----
    use_local_python()
    import numpy as np
    from dialogue import read_call, speakers_of, align, cut_points, spoken
    from speech import respell
    from phone import on_phone
    D = dict(job_config().get('dialogue') or {})
    engine = a.engine or D.get('engine', 'gemini')
    if engine not in ('gemini', 'kokoro'):
        raise SystemExit('A call is read with the gemini or kokoro engine (job.json "dialogue" "engine"), not %r.' % engine)
    style0, lines = read_call(a.dialogue)
    style = a.style if a.style is not None else style0 if style0 is not None else D.get('style', '')
    voices = dict(D.get('speakers') or {})
    if a.speakers: voices.update(kv.split('=', 1) for kv in a.speakers.split(',') if '=' in kv)
    names = speakers_of(lines)
    if [n for n in names if n not in voices]:
        raise SystemExit('No voice for speaker(s) %s: add them to job.json "dialogue" "speakers" (or --speakers Name=Voice).'
                         % ', '.join(n for n in names if n not in voices))
    phone = [p for p in (D.get('phone') or [])] if a.phone is None else [p for p in a.phone.split(',') if p and p != 'none']
    out_dir = a.dir or 'audio/calls'; os.makedirs(out_dir, exist_ok=True)
    LANG = language(); t = time.time(); info = {}; bounds = None
    if engine == 'gemini':
        model = a.model or D.get('model', DEFAULTS['gemini']['model'])
        check_budget(block='dialogue')
        meta = lambda sp: dict({'speaker': sp}, **({'style': style} if style else {}))
        parts = [{'text': re.sub(r'\[en:([^\]]+)\]', r'\1', txt), 'speech_metadata': meta(sp)} for sp, txt in lines]
        mode = a.mode or D.get('mode', 'auto')
        if mode == 'auto': mode = 'together' if all(voices[n] in GEMINI_VOICES for n in names) else 'per_line'
        speed = float(D.get('speed', 1.0))
        if mode == 'together' and len(names) > 2:
            raise SystemExit('Gemini reads at most two speakers in one request; this call has %d (%s). Use --mode per_line.'
                             % (len(names), ', '.join(names)))
        if mode == 'together':
            # built-in names in the documented form; anything else (to try an Extended Voice Library ID) as "voice"
            voice_of = lambda n: {'prebuiltVoiceConfig': {'voiceName': voices[n]}} if voices[n] in GEMINI_VOICES else {'voice': voices[n]}
            if len(names) == 2:
                cfg = {'multiSpeakerVoiceConfig': {'speakerVoiceConfigs': [{'speaker': n, 'voiceConfig': voice_of(n)} for n in names]}}
            else:
                cfg = {'voiceConfig': voice_of(names[0])}
            pcm, cost, usage = gemini_speech(model, parts, cfg)
            log_cost(model, 'call %s (%s)' % (a.name, ', '.join('%s=%s' % (n, voices[n]) for n in names)), cost)
            if speed != 1.0: pcm = stretch(pcm, speed)
        else:
            # one request per line, each with its speaker's voice (built-in or custom), joined by "gap" seconds; a
            # line whose text and settings did not change, and that is not in --redo, is reused from NAME_parts/
            gap = b'\0\0' * int(float(D.get('gap', 0.35)) * SR)
            pcm, bounds, cost, usage = bytearray(), [], 0.0, {'in': 0, 'out': 0}
            pdir = os.path.join(out_dir, a.name + '_parts'); os.makedirs(pdir, exist_ok=True)
            ip = os.path.join(pdir, 'index.json'); idx = json.load(open(ip)) if os.path.exists(ip) else {}
            redo = {int(x) for x in (a.redo or '').split(',') if x.strip()}
            if redo - set(range(1, len(lines) + 1)):
                raise SystemExit('--redo %s: this call has lines 1 to %d.' % (a.redo, len(lines)))
            kept = 0
            for i, (sp, part) in enumerate(zip([l[0] for l in lines], parts)):
                key = {'text': part['text'], 'voice': voices[sp], 'style': style, 'model': model}
                pf = os.path.join(pdir, '%03d.wav' % (i + 1))
                if i + 1 not in redo and idx.get(str(i + 1)) == key and os.path.exists(pf):
                    w = wave.open(pf); one = w.readframes(w.getnframes()); w.close(); kept += 1
                    print('gemini: line %d/%d (%s) kept from the last take' % (i + 1, len(lines), sp), flush=True)
                else:
                    check_budget(block='dialogue')
                    print('gemini: line %d/%d (%s)' % (i + 1, len(lines), sp), flush=True)
                    p1 = {'text': part['text']}
                    if style: p1['speech_metadata'] = {'style': style}
                    one, c1, u1 = gemini_speech(model, [p1], {'voiceConfig': {'voice': voices[sp]}})
                    log_cost(model, 'call %s line %d (%s=%s)' % (a.name, i + 1, sp, voices[sp]), c1)
                    write_wav(pf, one); idx[str(i + 1)] = key; json.dump(idx, open(ip, 'w'), indent=1, ensure_ascii=False)
                    cost += c1 or 0; usage = {'in': usage['in'] + u1['in'], 'out': usage['out'] + u1['out']}
                if speed != 1.0: one = stretch(one, speed)
                s0 = len(pcm) / 2 / SR; pcm += one; bounds.append((s0, len(pcm) / 2 / SR))
                if i < len(lines) - 1: pcm += gap
            cost = round(cost, 6); info['kept_lines'] = kept
        info.update(model=model, mode=mode, cost=cost, tokens=usage, paid=True, speed=speed)
    else:
        from kokoro_onnx import Kokoro
        if not all(os.path.exists(f) for f in KOKORO):
            raise SystemExit('Kokoro model files are missing. Run scripts/setup.sh from the studio root.')
        k = Kokoro(*KOKORO); lang = LANGS[LANG]['kokoro']
        gap = b'\0\0' * int(float(D.get('gap', 0.35)) * SR)
        pcm, bounds = bytearray(), []
        for i, (sp, txt) in enumerate(lines):
            v = voices[sp] if isinstance(voices[sp], dict) else {'name': voices[sp]}
            if v['name'] not in k.get_voices() or v['name'][0] not in LANGS[LANG]['prefix']:
                raise SystemExit('Kokoro voice %r is unknown or does not speak %s. Voices: python3 lib/audition.py --list' % (v['name'], LANGS[LANG]['name']))
            audio, _ = k.create(spoken(txt), voice=v['name'], speed=float(v.get('speed', 1.0)),
                                lang=lang or ('en-gb' if v['name'].startswith('b') else 'en-us'))
            s0 = len(pcm) / 2 / SR
            pcm += (np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes()
            bounds.append((s0, len(pcm) / 2 / SR))
            if i < len(lines) - 1: pcm += gap
        info['license'] = 'Kokoro v1.0, Apache 2.0'
    def written(t):   # caption text: job.json "respell" (spoken -> written), as for the narration
        for k_, w_ in respell().items(): t = t.replace(k_, w_)
        return t
    raw = os.path.join(out_dir, a.name + '_raw.wav'); write_wav(raw, pcm)
    total = len(pcm) / 2 / SR
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stt.py'), raw], check=True,
                   stdout=subprocess.DEVNULL)
    words = json.load(open(raw.rsplit('.', 1)[0] + '_words.json'))['words']
    spans, issues = align(lines, words)
    if bounds:   # Kokoro and Gemini per_line: each line's exact place is known
        h = float(D.get('gap', 0.35)) / 2
        cuts = [(round(s0, 3), round(s1, 3), round(max(0, s0 - h), 3), round(min(total, s1 + h), 3)) for s0, s1 in bounds]
    else:
        cuts = cut_points(spans, words, total)
    x = np.frombuffer(bytes(pcm), '<i2').astype(np.float32) / 32768
    if phone:
        x = on_phone(x, [(c[2], c[3]) for (sp, _), c in zip(lines, cuts) if sp in phone])
    wav = os.path.join(out_dir, a.name + '.wav'); write_wav(wav, (x * 32767).astype('<i2').tobytes())
    L = {'name': a.name, 'engine': engine, 'style': style, 'speakers': {n: voices[n] for n in names}, 'phone': phone,
         'raw': raw, 'wav': wav, 'seconds': round(total, 3),
         'lines': [{'speaker': sp, 'text': written(spoken(txt)), 't': c[0], 'e': c[1], 'c0': c[2], 'c1': c[3]} for (sp, txt), c in zip(lines, cuts)],
         'words': words, 'issues': issues}
    json.dump(L, open(os.path.join(out_dir, a.name + '_lines.json'), 'w'), indent=1, ensure_ascii=False)
    print('== call %s%s | lines %d | speakers %s | phone %s | wording differences %d'
          % (a.name, ' (%s)' % info['mode'] if 'mode' in info else '', len(lines), ', '.join('%s=%s' % (n, voices[n]) for n in names), ', '.join(phone) or 'none', len(issues)))
    for d in issues:
        print('  line %d (%s): script "%s" | heard "%s"' % (d['line'] + 1, lines[d['line']][0], d['script'], d['heard']))
    info = dict({'out': wav, 'raw': raw, 'engine': engine, 'style': style, 'lines': len(lines), 'seconds': round(total, 1),
                 'secs': round(time.time() - t, 1), 'words': sum(len(spoken(x_).split()) for _, x_ in lines)}, **info)
    open(os.path.join(out_dir, a.name + '.log'), 'w').write(json.dumps(info, ensure_ascii=False))
    print(json.dumps(info, ensure_ascii=False))
    sys.exit()

a.dir = a.dir or 'audio/takes'
V = voice_config()
engine = a.engine or V['engine']
if engine not in DEFAULTS:
    raise SystemExit('Unknown voice engine %r in job.json "voice". Use one of: %s' % (engine, ', '.join(DEFAULTS)))
if engine == 'say' and WINDOWS:
    raise SystemExit('The say engine uses the macOS system voices and does not exist on Windows. Use kokoro for drafts.')
S = dict(DEFAULTS[engine], **(V if V['engine'] == engine else {}))   # job.json settings apply to its own engine only
pick = lambda arg, key: arg if arg is not None else S.get(key)
voice, speed = pick(a.voice, 'name'), float(pick(a.speed, 'speed'))
os.makedirs(a.dir, exist_ok=True)
text = open(a.text).read()
LANG = language()
EN_WORD = re.compile(r'\[en:([^\]]+)\]')
if engine != 'kokoro': text = EN_WORD.sub(r'\1', text)   # only Kokoro can switch pronunciation per word
paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
out = bytearray(); gap = b'\0\0' * int(a.gap * SR)
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
    if voice[0] not in LANGS[LANG]['prefix']:
        raise SystemExit('Kokoro voice %r does not speak %s (job.json "language": %r). Voices: python3 lib/audition.py --list'
                         % (voice, LANGS[LANG]['name'], LANG))
    lang = LANGS[LANG]['kokoro'] or ('en-gb' if voice.startswith('b') else 'en-us')
    def phonemes(p):   # [en:word] parts in English, the rest in the job's language
        return ' '.join(k.tokenizer.phonemize(s, 'en-us' if j % 2 else lang).strip() for j, s in enumerate(EN_WORD.split(p)) if s.strip())
    for i, p in enumerate(paras):
        if EN_WORD.search(p): audio, sr = k.create(phonemes(p), voice=voice, speed=speed, is_phonemes=True)
        else: audio, sr = k.create(p, voice=voice, speed=speed, lang=lang)
        out += (np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes() + (gap if i < len(paras) - 1 else b'')
elif engine == 'chatterbox':
    use_chatterbox_python()
    import numpy as np, torch
    from chatterbox.tts import ChatterboxTTS
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    seed, exa, cfg = int(pick(a.seed, 'seed')), float(pick(a.exaggeration, 'exaggeration')), float(pick(a.cfg, 'cfg_weight'))
    # "builtin" is the voice that ships with the model (MIT). Anything else is a reference clip in the job folder to
    # clone, which the owner must have the rights to use (about 10 s of clean speech).
    ref = None if voice == 'builtin' else os.path.join(JOB, voice)
    if ref and not os.path.exists(ref):
        raise SystemExit('Chatterbox reference clip %s not found. Use "builtin" or a path inside the job folder.' % ref)
    # an NVIDIA GPU, else the Mac GPU, else the CPU (many times slower: warn, since a full take could run for hours)
    device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    if device == 'cpu':
        print('WARNING: no GPU found, so Chatterbox runs on the CPU and is very slow. Kokoro is the better choice here.', flush=True)
    if LANG == 'en': m = ChatterboxTTS.from_local(CHATTERBOX, device)
    elif not os.path.exists(os.path.join(CHATTERBOX_MTL, 't3_mtl23ls_v2.safetensors')):
        raise SystemExit('Chatterbox Multilingual is not installed. Run scripts/setup-chatterbox.sh --multilingual (3.2 GB, once).')
    else: m = ChatterboxMultilingualTTS.from_local(CHATTERBOX_MTL, device)
    if m.sr != SR:
        raise SystemExit('Chatterbox returned %d Hz audio; this script expects %d.' % (m.sr, SR))
    def chunks(p, most=90 if LANG == 'en' else 60):
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
            kw = {} if LANG == 'en' else {'language_id': LANG}
            w = m.generate(c, audio_prompt_path=ref, exaggeration=exa, cfg_weight=cfg, **kw).squeeze(0).cpu().numpy()
            out += (np.clip(w, -1, 1) * 32767).astype('<i2').tobytes() + (small if j < len(parts) - 1 else b'')
        out += gap if i < len(paras) - 1 else b''
    info.update(device=device, language=LANG, seed=seed, exaggeration=exa, cfg_weight=cfg, reference=voice,
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
elif engine == 'gemini':
    use_local_python()   # for its certificate handling (truststore); no local model is used
    model = a.model or S['model']; style = a.style if a.style is not None else S.get('style') or ''
    check_budget()
    part = {'text': '\n\n'.join(paras)}
    if style: part['speech_metadata'] = {'style': style}
    # "voice" takes a built-in name or a custom voice ID (aistudio.google.com/docs/speech-generation, single speaker)
    pcm, cost, usage = gemini_speech(model, [part], {'voiceConfig': {'voice': voice}})
    out += pcm
    log_cost(model, 'voice %s (%s)' % (a.name, voice), cost)
    info.update(model=model, style=style, cost=cost, tokens=usage, paid=True)
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
if engine in ('chatterbox', 'openrouter', 'gemini') and speed != 1.0:
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
