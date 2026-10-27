# Word timestamps for a take, with Whisper large-v3-turbo running on this Mac (mlx-whisper; no network, no cost).
# Whisper mishears some words; confirm by ear before rewording a line.
# usage: python3 lib/stt.py audio/takes/NAME.wav [--language it]  -> audio/takes/NAME_words.json
# The language defaults to job.json "language" (English when missing).
import argparse, json, subprocess
from common import use_local_python, language, FF, WHISPER
use_local_python()
import numpy as np, mlx_whisper
ap = argparse.ArgumentParser(); ap.add_argument('audio'); ap.add_argument('--model', default=WHISPER)
ap.add_argument('--language', default=language())
a = ap.parse_args()
# decode with the bundled ffmpeg (mlx-whisper would look for one on PATH): 16 kHz mono float
pcm = subprocess.run([FF, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', a.audio, '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'],
                     check=True, capture_output=True).stdout
r = mlx_whisper.transcribe(np.frombuffer(pcm, np.float32), path_or_hf_repo=a.model, word_timestamps=True, language=a.language)
words = [{'word': w['word'], 'start': round(float(w['start']), 3), 'end': round(float(w['end']), 3)}
         for s in r['segments'] for w in s.get('words', [])]
d = {'text': r['text'], 'words': words,
     'segments': [{'start': s['start'], 'end': s['end'], 'text': s['text']} for s in r['segments']]}
out = a.audio.rsplit('.', 1)[0] + '_words.json'
json.dump(d, open(out, 'w'), indent=1)
print(d['text'].strip()); print('words', len(words), '->', out)
