# Shared helpers for every job script. Run scripts from the job folder: `python3 lib/<script>.py ...`.
# Finds the studio root (the folder holding .demo-studio), the bundled ffmpeg, and the local voice and
# transcription models. Everything runs on this Mac; nothing here calls a paid or remote service.
import json, os, sys

JOB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _studio():
    d = JOB
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, '.demo-studio')):
            return d
        d = os.path.dirname(d)
    sys.exit('Cannot find the studio root (.demo-studio). Run jobs from inside the studio folder.')

STUDIO = _studio()
NM = os.path.join(STUDIO, 'toolkit', 'node_modules')
FF = os.path.join(NM, 'ffmpeg-static', 'ffmpeg')
FFPROBE = os.path.join(NM, 'ffprobe-static', 'bin', 'darwin', os.uname().machine.replace('x86_64', 'x64'), 'ffprobe')
VENV_PY = os.path.join(STUDIO, 'toolkit', '.venv', 'bin', 'python')
MODELS = os.path.join(STUDIO, 'toolkit', 'models')
KOKORO = (os.path.join(MODELS, 'kokoro', 'kokoro-v1.0.onnx'), os.path.join(MODELS, 'kokoro', 'voices-v1.0.bin'))
WHISPER = os.path.join(MODELS, 'whisper-large-v3-turbo')

def job_config():
    p = os.path.join(JOB, 'job.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def use_local_python():
    # Voice and transcription need the studio's own Python (toolkit/.venv, made by scripts/setup.sh).
    # Rerun this script under it, so commands stay `python3 lib/<script>.py ...`.
    if os.path.realpath(sys.prefix) == os.path.realpath(os.path.join(STUDIO, 'toolkit', '.venv')):
        return
    if not os.path.exists(VENV_PY):
        sys.exit('The local voice and transcription tools are not installed. Run scripts/setup.sh from the studio root.')
    os.execv(VENV_PY, [VENV_PY] + sys.argv)

def run_ff(args, check=True):
    import subprocess
    return subprocess.run([FF, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y'] + args, check=check)
