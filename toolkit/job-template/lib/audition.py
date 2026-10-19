# Read the same short sample in several Kokoro voices, so the owner can listen and pick one before the build.
# usage: python3 lib/audition.py [VOICE ...] [--text FILE] [--speed 1.0]   -> audio/audition/A_<voice>.wav
#        python3 lib/audition.py --list      (every English voice with its grade from the Kokoro voice list)
# Play one with: afplay audio/audition/A_<voice>.wav . Save the pick in job.json "voice": {"name": ..., "speed": ...}.
import argparse, os, subprocess, sys
# Overall grades from hexgrad/Kokoro-82M VOICES.md (quality and amount of training data per voice).
GRADES = {'af_heart': 'A', 'af_bella': 'A-', 'af_nicole': 'B-', 'af_aoede': 'C+', 'af_kore': 'C+', 'af_sarah': 'C+',
          'af_alloy': 'C', 'af_nova': 'C', 'af_sky': 'C-', 'af_jessica': 'D', 'af_river': 'D',
          'am_fenrir': 'C+', 'am_michael': 'C+', 'am_puck': 'C+', 'am_echo': 'D', 'am_eric': 'D', 'am_liam': 'D',
          'am_onyx': 'D', 'am_santa': 'D-', 'am_adam': 'F+',
          'bf_emma': 'B-', 'bf_isabella': 'C', 'bf_alice': 'D', 'bf_lily': 'D',
          'bm_fable': 'C', 'bm_george': 'C', 'bm_lewis': 'D+', 'bm_daniel': 'D'}
KIND = {'af': 'American woman', 'am': 'American man', 'bf': 'British woman', 'bm': 'British man'}
DEFAULT = ['am_michael', 'am_fenrir', 'am_puck', 'af_heart', 'af_bella', 'bf_emma', 'bm_george']
SAMPLE = ("Let me show you how this works in practice. I'm going to open the dashboard, pick the site that's "
          "reporting problems, and walk you through what the system already found for us.")
ap = argparse.ArgumentParser(); ap.add_argument('voices', nargs='*'); ap.add_argument('--list', action='store_true')
ap.add_argument('--text'); ap.add_argument('--speed', type=float, default=1.0)
a = ap.parse_args()
if a.list:
    for v, g in GRADES.items(): print('%-12s %-3s %s' % (v, g, KIND[v[:2]]))
    sys.exit()
os.makedirs('audio/audition', exist_ok=True)
txt = a.text
if not txt:
    txt = 'audio/audition/sample.txt'
    if not os.path.exists(txt): open(txt, 'w').write(SAMPLE + '\n')
for v in a.voices or DEFAULT:
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'take.py'), 'A_' + v, v,
                    '--speed', str(a.speed), '--text', txt, '--dir', 'audio/audition'], check=True, stdout=subprocess.DEVNULL)
    print('%-12s %-3s %-15s afplay audio/audition/A_%s.wav' % (v, GRADES.get(v, '?'), KIND.get(v[:2], ''), v))
