# Word timestamps for a take, with Whisper large-v3-turbo running on this computer (no network, no cost):
# mlx-whisper on a Mac (Apple GPU), faster-whisper on Windows (CPU). Both write the same file.
# Whisper mishears some words; confirm by ear before rewording a line.
# usage: python3 lib/stt.py audio/takes/NAME.wav [--language it]  -> audio/takes/NAME_words.json
# The language defaults to job.json "language" (English when missing).
import argparse, json, subprocess
from common import use_local_python, language, FF, WHISPER, WINDOWS
use_local_python()
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('audio'); ap.add_argument('--model', default=WHISPER)
ap.add_argument('--language', default=language())
a = ap.parse_args()
# decode with the bundled ffmpeg (Whisper would look for one on PATH): 16 kHz mono float
pcm = subprocess.run([FF, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', a.audio, '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'],
                     check=True, capture_output=True).stdout
audio = np.frombuffer(pcm, np.float32)
if WINDOWS:
    from faster_whisper import WhisperModel
    segs, _ = WhisperModel(a.model, device='cpu', compute_type='int8').transcribe(audio, language=a.language, word_timestamps=True)
    segs = [{'start': s.start, 'end': s.end, 'text': s.text,
             'words': [{'word': w.word, 'start': w.start, 'end': w.end} for w in s.words or []]} for s in segs]
    r = {'text': ''.join(s['text'] for s in segs), 'segments': segs}
else:
    import mlx_whisper
    r = mlx_whisper.transcribe(audio, path_or_hf_repo=a.model, word_timestamps=True, language=a.language)
words = [{'word': w['word'], 'start': round(float(w['start']), 3), 'end': round(float(w['end']), 3)}
         for s in r['segments'] for w in s.get('words', [])]
d = {'text': r['text'], 'words': words,
     'segments': [{'start': s['start'], 'end': s['end'], 'text': s['text']} for s in r['segments']]}
out = a.audio.rsplit('.', 1)[0] + '_words.json'
json.dump(d, open(out, 'w'), indent=1)
print(d['text'].strip()); print('words', len(words), '->', out)
