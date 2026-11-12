# Read the same short sample in one or more voices, so the owner can listen and pick one before the build.
# usage: python3 lib/audition.py [VOICE ...] [--text FILE] [--speed S]                       Kokoro (seven voices)
#        python3 lib/audition.py --engine chatterbox [builtin|clip.wav ...] [--speed 0.94]    about 1 minute per voice
#        python3 lib/audition.py --engine openrouter [Iapetus Charon ...] [--model M]          paid, about 1 cent each
#        python3 lib/audition.py --engine gemini [Iapetus Charon ...] [--style S]              Google, the owner's key
#        python3 lib/audition.py --call [--engine gemini|kokoro] [Kore+Puck ...] [--text FILE] [--phone Paolo|none]
#                                   [--mode together|per_line]   (Gemini: a custom voice ID, voice_..., reads per_line)
#                                   [--redo 3]   (per_line: ask again only for those lines; changed lines are redone anyway)
#            a short two-speaker call (Italian or English sample, or the owner's own lines in the format of
#            lib/dialogue.py); each pair gives the voices in the order the speakers first speak; default pair from
#            job.json "dialogue" "speakers"; the phone filter follows job.json "dialogue" "phone" unless --phone is given
#        python3 lib/audition.py --list      (every Kokoro voice of the job's language, with its grade from the Kokoro voice list)
# The sample and the default voices follow job.json "language" (default English).
# Output: audio/audition/A_<voice>.wav (Kokoro) or A_<engine>_<voice>.wav (a call: A_call_<engine>_<v1>_<v2>.wav,
# with _raw.wav before the phone filter); each line prints its play command
# (lib/play.py, which works on macOS and Windows).
# Save the pick in job.json "voice" (see PIPELINE.md step 3 for each engine's fields).
import argparse, os, subprocess, sys
from common import language, job_config
# Overall grades from hexgrad/Kokoro-82M VOICES.md (quality and amount of training data per voice).
GRADES = {'af_heart': 'A', 'af_bella': 'A-', 'af_nicole': 'B-', 'af_aoede': 'C+', 'af_kore': 'C+', 'af_sarah': 'C+',
          'af_alloy': 'C', 'af_nova': 'C', 'af_sky': 'C-', 'af_jessica': 'D', 'af_river': 'D',
          'am_fenrir': 'C+', 'am_michael': 'C+', 'am_puck': 'C+', 'am_echo': 'D', 'am_eric': 'D', 'am_liam': 'D',
          'am_onyx': 'D', 'am_santa': 'D-', 'am_adam': 'F+',
          'bf_emma': 'B-', 'bf_isabella': 'C', 'bf_alice': 'D', 'bf_lily': 'D',
          'bm_fable': 'C', 'bm_george': 'C', 'bm_lewis': 'D+', 'bm_daniel': 'D',
          # other languages; '?' = not graded in the Kokoro voice list
          'if_sara': 'C', 'im_nicola': 'C', 'ff_siwis': 'B-', 'ef_dora': '?', 'em_alex': '?', 'em_santa': '?',
          'pf_dora': '?', 'pm_alex': '?', 'pm_santa': '?'}
KIND = {'af': 'American woman', 'am': 'American man', 'bf': 'British woman', 'bm': 'British man',
        'if': 'Italian woman', 'im': 'Italian man', 'ef': 'Spanish woman', 'em': 'Spanish man', 'ff': 'French woman',
        'pf': 'Brazilian Portuguese woman', 'pm': 'Brazilian Portuguese man'}
LANG = language()
KOKORO_DEFAULT = {'en': ['am_michael', 'am_fenrir', 'am_puck', 'af_heart', 'af_bella', 'bf_emma', 'bm_george'],
                  'it': ['im_nicola', 'if_sara'], 'es': ['em_alex', 'ef_dora', 'em_santa'], 'fr': ['ff_siwis'],
                  'pt': ['pm_alex', 'pf_dora', 'pm_santa']}
DEFAULT = {'kokoro': KOKORO_DEFAULT[LANG],
           'chatterbox': ['builtin'], 'openrouter': ['Iapetus', 'Charon'], 'gemini': ['Iapetus', 'Charon']}
SAMPLES = {'en': "Let me show you how this works in practice. I'm going to open the dashboard, pick the site that's "
                 "reporting problems, and walk you through what the system already found for us.",
           'it': "Vediamo come funziona in pratica. Apro la dashboard, scelgo la sede che segnala problemi e vi mostro "
                 "che cosa ha già trovato il sistema.",
           'es': "Veamos cómo funciona en la práctica. Voy a abrir el panel, elegir la sede que está reportando problemas "
                 "y mostrarles lo que el sistema ya encontró.",
           'fr': "Voyons comment cela fonctionne en pratique. Je vais ouvrir le tableau de bord, choisir le site qui signale "
                 "des problèmes et vous montrer ce que le système a déjà trouvé.",
           'pt': "Vamos ver como isso funciona na prática. Vou abrir o painel, escolher o local que está relatando problemas "
                 "e mostrar o que o sistema já encontrou."}
SAMPLE = SAMPLES[LANG]
# two-speaker call samples (amounts in words: voices misread digits); other languages use --text
CALL_SAMPLES = {'it': "style: una telefonata tranquilla tra due colleghi, tono colloquiale\n"
                      "Anna: Ciao Paolo, hai un minuto?\n"
                      "Paolo: Certo Anna, dimmi pure.\n"
                      "Anna: La consegna per il cliente di Torino è pronta. Parte domani mattina.\n"
                      "Paolo: Ottimo! Quanti colli sono in tutto?\n"
                      "Anna: Dodici colli, per un totale di trecentoquaranta chili.\n"
                      "Paolo: Perfetto, grazie. Ci sentiamo dopo la consegna.\n",
                'en': "style: a relaxed phone call between two colleagues, casual tone\n"
                      "Anna: Hi Paolo, have you got a minute?\n"
                      "Paolo: Sure, Anna. Go ahead.\n"
                      "Anna: The delivery for the Boston customer is ready. It leaves tomorrow morning.\n"
                      "Paolo: Great! How many boxes in total?\n"
                      "Anna: Twelve boxes, three hundred and forty pounds in all.\n"
                      "Paolo: Perfect, thanks. Talk to you after the delivery.\n"}
ap = argparse.ArgumentParser(); ap.add_argument('voices', nargs='*'); ap.add_argument('--list', action='store_true')
ap.add_argument('--engine', choices=list(DEFAULT)); ap.add_argument('--model')
ap.add_argument('--text'); ap.add_argument('--speed', type=float); ap.add_argument('--style')
ap.add_argument('--call', action='store_true'); ap.add_argument('--phone')
ap.add_argument('--mode', choices=['auto', 'together', 'per_line']); ap.add_argument('--redo')
a = ap.parse_args()
TAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'take.py')
PY = 'python' if os.name == 'nt' else 'python3'
if a.call:
    from dialogue import read_call, speakers_of
    D = job_config().get('dialogue') or {}
    engine = a.engine or D.get('engine', 'kokoro')   # free and local unless Gemini was picked
    if engine not in ('gemini', 'kokoro'): sys.exit('A call audition uses --engine gemini or --engine kokoro.')
    os.makedirs('audio/audition', exist_ok=True)
    txt = a.text
    if not txt:
        if LANG not in CALL_SAMPLES: sys.exit('No built-in call sample in this language: write a few "Name: line" lines to a file and pass --text FILE.')
        txt = 'audio/audition/call_sample_%s.txt' % LANG
        if not os.path.exists(txt): open(txt, 'w').write(CALL_SAMPLES[LANG])
    names = speakers_of(read_call(txt)[1])
    sp = D.get('speakers') or {}
    pairs = a.voices or ['+'.join(str(sp[x] if isinstance(sp.get(x), str) else (sp.get(x) or {}).get('name', '')) for x in names)]
    if not all(pairs[0].split('+')):
        pairs = ['Kore+Puck'] if engine == 'gemini' else ['+'.join((KOKORO_DEFAULT[LANG] * 2)[:2])]
    if engine == 'gemini':
        print('GOOGLE: each call audition sends the sample text to Google with the GEMINI_API_KEY in .env (free on the free tier; '
              'about 0.3 cent each at paid-tier prices, logged in logs/costs.jsonl).')
    for pair in pairs:
        vs = pair.split('+')
        if len(vs) != len(names): sys.exit('%s gives %d voice(s) for %d speaker(s) (%s); write them as Voice1+Voice2.' % (pair, len(vs), len(names), ', '.join(names)))
        name = 'A_call_%s_%s%s' % (engine, '_'.join(vs), '_' + a.mode if a.mode and a.mode != 'auto' else '')
        cmd = [sys.executable, TAKE, name, '--dialogue', txt, '--engine', engine, '--dir', 'audio/audition',
               '--speakers', ','.join('%s=%s' % kv for kv in zip(names, vs))]
        cmd += ['--model', a.model] if a.model else []
        cmd += ['--phone', a.phone] if a.phone else []
        cmd += ['--mode', a.mode] if a.mode else []
        cmd += ['--redo', a.redo] if a.redo else []
        cmd += ['--style', a.style] if a.style is not None else []
        r = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        if r.returncode: sys.exit(r.returncode)
        print('\n'.join(l for l in r.stdout.splitlines() if not l.startswith('{')))
        print('%-24s %s lib/play.py audio/audition/%s.wav   (as read: %s_raw.wav)' % (pair, PY, name, name))
    sys.exit()
a.engine = a.engine or 'kokoro'
if a.list:
    for v, g in GRADES.items():
        if v[0] in ('ab' if LANG == 'en' else DEFAULT['kokoro'][0][0]): print('%-12s %-3s %s' % (v, g, KIND[v[:2]]))
    sys.exit()
os.makedirs('audio/audition', exist_ok=True)
txt = a.text
if not txt:
    txt = 'audio/audition/sample.txt' if LANG == 'en' else 'audio/audition/sample_%s.txt' % LANG
    if not os.path.exists(txt): open(txt, 'w').write(SAMPLE + '\n')
if a.engine == 'openrouter':
    print('PAID: each OpenRouter audition sends the sample text to OpenRouter and costs about 1 cent.')
if a.engine == 'gemini':
    print('GOOGLE: each Gemini audition sends the sample text to Google with the GEMINI_API_KEY in .env (free on the free '
          'tier; about 0.2 cent each at paid-tier prices, logged in logs/costs.jsonl).')
for v in a.voices or DEFAULT[a.engine]:
    name = 'A_' + v if a.engine == 'kokoro' else 'A_%s_%s' % (a.engine, os.path.splitext(os.path.basename(v))[0])
    cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'take.py'), name, v,
           '--engine', a.engine, '--text', txt, '--dir', 'audio/audition']
    cmd += ['--speed', str(a.speed or 1.0)] if a.speed or a.engine == 'kokoro' else []   # else the engine's preset
    cmd += ['--model', a.model] if a.model else []
    cmd += ['--style', a.style] if a.style is not None and a.engine == 'gemini' else []
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    label = '%-3s %-15s' % (GRADES.get(v, '?'), KIND.get(v[:2], '')) if a.engine == 'kokoro' else '%-19s' % a.engine
    print('%-12s %s %s lib/play.py audio/audition/%s.wav' % (v, label, 'python' if os.name == 'nt' else 'python3', name))
