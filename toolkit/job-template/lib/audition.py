# Read the same short sample in one or more voices, so the owner can listen and pick one before the build.
# usage: python3 lib/audition.py [VOICE ...] [--text FILE] [--speed S]                       Kokoro (seven voices)
#        python3 lib/audition.py --engine chatterbox [builtin|clip.wav ...] [--speed 0.94]    about 1 minute per voice
#        python3 lib/audition.py --engine openrouter [Iapetus Charon ...] [--model M]          paid, about 1 cent each
#        python3 lib/audition.py --list      (every Kokoro voice of the job's language, with its grade from the Kokoro voice list)
# The sample and the default voices follow job.json "language" (default English).
# Output: audio/audition/A_<voice>.wav (Kokoro) or A_<engine>_<voice>.wav; each line prints its play command
# (lib/play.py, which works on macOS and Windows).
# Save the pick in job.json "voice" (see PIPELINE.md step 3 for each engine's fields).
import argparse, os, subprocess, sys
from common import language
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
           'chatterbox': ['builtin'], 'openrouter': ['Iapetus', 'Charon']}
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
ap = argparse.ArgumentParser(); ap.add_argument('voices', nargs='*'); ap.add_argument('--list', action='store_true')
ap.add_argument('--engine', default='kokoro', choices=list(DEFAULT)); ap.add_argument('--model')
ap.add_argument('--text'); ap.add_argument('--speed', type=float)
a = ap.parse_args()
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
for v in a.voices or DEFAULT[a.engine]:
    name = 'A_' + v if a.engine == 'kokoro' else 'A_%s_%s' % (a.engine, os.path.splitext(os.path.basename(v))[0])
    cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'take.py'), name, v,
           '--engine', a.engine, '--text', txt, '--dir', 'audio/audition']
    cmd += ['--speed', str(a.speed or 1.0)] if a.speed or a.engine == 'kokoro' else []   # else the engine's preset
    cmd += ['--model', a.model] if a.model else []
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    label = '%-3s %-15s' % (GRADES.get(v, '?'), KIND.get(v[:2], '')) if a.engine == 'kokoro' else '%-19s' % a.engine
    print('%-12s %s %s lib/play.py audio/audition/%s.wav' % (v, label, 'python' if os.name == 'nt' else 'python3', name))
