# Shared helpers for every job script. Run scripts from the job folder: `python3 lib/<script>.py ...`.
# Finds the studio root (the folder holding .demo-studio), the bundled ffmpeg, and the local voice and
# transcription models. Everything runs on this computer, except the narration voice when the job's owner chose the
# paid OpenRouter voice (job.json "voice": {"engine": "openrouter", ...}); only lib/take.py calls it.
# Runs on macOS and Windows; WINDOWS marks the few places that differ.
import json, os, platform, subprocess, sys, time

WINDOWS = os.name == 'nt'

def rerun(py, env=None):
    # Continue this script in another Python process. On Windows os.execv starts that process and returns at once,
    # so the shell would see the script finish while it still runs; there, wait for it and pass on its exit code.
    if WINDOWS:
        sys.exit(subprocess.call([py] + sys.argv, env=env))
    os.execve(py, [py] + sys.argv, env if env is not None else os.environ)

# Windows: open() and print() default to the system code page (cp1252 here), which garbles accented script text,
# curly quotes, and the captions. Every job script imports this file first, so run them all in UTF-8 mode instead.
if WINDOWS and not sys.flags.utf8_mode:
    rerun(sys.executable, dict(os.environ, PYTHONUTF8='1'))

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
EXE = '.exe' if WINDOWS else ''
FF = os.path.join(NM, 'ffmpeg-static', 'ffmpeg' + EXE)
_ARCH = {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64'}.get(platform.machine().lower(), platform.machine().lower())
FFPROBE = os.path.join(NM, 'ffprobe-static', 'bin', sys.platform, _ARCH, 'ffprobe' + EXE)

def venv_python(venv):
    return os.path.join(venv, 'Scripts', 'python.exe') if WINDOWS else os.path.join(venv, 'bin', 'python')

VENV = os.path.join(STUDIO, 'toolkit', '.venv')
VENV_PY = venv_python(VENV)
MODELS = os.path.join(STUDIO, 'toolkit', 'models')
KOKORO = (os.path.join(MODELS, 'kokoro', 'kokoro-v1.0.onnx'), os.path.join(MODELS, 'kokoro', 'voices-v1.0.bin'))
# Whisper large-v3-turbo: for mlx-whisper on a Mac, for faster-whisper (CTranslate2) on Windows
WHISPER = os.path.join(MODELS, 'faster-whisper-large-v3-turbo' if WINDOWS else 'whisper-large-v3-turbo')
# Chatterbox needs PyTorch, so it has its own Python (made by scripts/setup-chatterbox.sh, only when a job picks it).
CHATTERBOX_VENV = os.path.join(STUDIO, 'toolkit', '.venv-chatterbox')
CHATTERBOX = os.path.join(MODELS, 'chatterbox')
# Chatterbox Multilingual, for narration that is not English (scripts/setup-chatterbox.sh --multilingual)
CHATTERBOX_MTL = os.path.join(MODELS, 'chatterbox-mtl')
# Narration languages (job.json "language", default "en"). Kokoro voice names start with the language's letter
# (af_/bm_ English, if_/im_ Italian, ef_/em_ Spanish, ff_ French, pf_/pm_ Brazilian Portuguese); "kokoro" is the
# phonemizer code (None: English, chosen per voice); Whisper and Chatterbox Multilingual take the two-letter code.
LANGS = {'en': {'name': 'English', 'kokoro': None, 'prefix': 'ab'},
         'it': {'name': 'Italiano', 'kokoro': 'it', 'prefix': 'i'},
         'es': {'name': 'Español', 'kokoro': 'es', 'prefix': 'e'},
         'fr': {'name': 'Français', 'kokoro': 'fr-fr', 'prefix': 'f'},
         'pt': {'name': 'Português', 'kokoro': 'pt-br', 'prefix': 'p'}}
COSTS = os.path.join(JOB, 'logs', 'costs.jsonl')
API = 'https://openrouter.ai/api/v1'

def job_config():
    p = os.path.join(JOB, 'job.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def language():
    # job.json "language": the narration and caption language, a key of LANGS; jobs without it are English
    code = str(job_config().get('language') or 'en').lower()
    if code not in LANGS:
        sys.exit('job.json "language" %r is not supported. Use one of: %s' % (code, ', '.join(LANGS)))
    return code

def voice_config():
    # job.json "voice"; jobs made before engines existed have no "engine" and mean Kokoro.
    v = dict(job_config().get('voice') or {})
    v.setdefault('engine', 'kokoro')
    return v

def use_python(venv, missing):
    # Rerun this script under the given private Python, so commands stay `python3 lib/<script>.py ...`.
    if os.path.realpath(sys.prefix) == os.path.realpath(venv):
        return
    py = venv_python(venv)
    if not os.path.exists(py):
        sys.exit(missing)
    rerun(py)

def use_local_python():
    # Voice and transcription need the studio's own Python (toolkit/.venv, made by scripts/setup.sh).
    use_python(VENV, 'The local voice and transcription tools are not installed. Run scripts/setup.sh from the studio root.')

def use_chatterbox_python():
    use_python(CHATTERBOX_VENV, 'Chatterbox is not installed. Run scripts/setup-chatterbox.sh from the studio root '
                                '(about 3.5 GB download, once).')

# OpenRouter: the paid voice only, and only when the owner chose it. The key is read from the studio .env by this
# code; Claude never reads .env or sees the key.
def api_key():
    k = os.environ.get('OPENROUTER_API_KEY')
    if k:
        return k
    env = os.path.join(STUDIO, '.env')
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line.startswith('OPENROUTER_API_KEY='):
                k = line.split('=', 1)[1].strip().strip('"').strip("'")
                if k:
                    return k
    sys.exit('OPENROUTER_API_KEY is not set. Put it in the studio .env (see .env.example), never in chat.')

def spent():
    # (billed total, number of paid calls with no known cost). A call logged before OpenRouter reported its cost is
    # looked up again and its line filled in; one that still has no cost is counted as unknown, never as $0.
    if not os.path.exists(COSTS):
        return 0.0, 0
    lines = [l for l in open(COSTS).read().splitlines() if l.strip()]
    total, unknown, changed = 0.0, 0, False
    for i, line in enumerate(lines):
        try:
            r = json.loads(line)
        except ValueError:
            unknown += 1; continue
        if r.get('cost') is None and r.get('id'):
            r['cost'] = generation_cost(r['id'], tries=2)
            if r['cost'] is not None:
                lines[i] = json.dumps(r); changed = True
        try:
            total += float(r.get('cost'))
        except (TypeError, ValueError):
            unknown += 1
    if changed:
        open(COSTS, 'w').write('\n'.join(lines) + '\n')
    return total, unknown

def check_budget(estimate=0.0):
    cap = float(voice_config().get('budget_usd', 2))
    s, unknown = spent()
    if unknown:
        sys.exit('BUDGET STOP: %d paid call(s) in logs/costs.jsonl have no billed cost (OpenRouter did not report it), '
                 'so this job\'s spend is unknown. Ask the owner to look it up at https://openrouter.ai/activity and '
                 'put it in that line\'s "cost", then rerun.' % unknown)
    if s + estimate > cap:
        sys.exit('BUDGET STOP: this job has spent $%.2f of its $%.2f voice cap. Ask the owner before raising '
                 '"budget_usd" in job.json "voice".' % (s, cap))
    return s

def log_cost(model, purpose, cost, gen_id=None):
    os.makedirs(os.path.dirname(COSTS), exist_ok=True)
    with open(COSTS, 'a') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%d %H:%M:%S'), 'model': model, 'purpose': purpose,
                            'cost': cost, 'id': gen_id}) + '\n')

def _urlopen(req, timeout):
    import urllib.request
    try:  # trust the Mac's certificate store, so a company network that inspects TLS still works
        import truststore; truststore.inject_into_ssl()
    except ImportError:
        pass
    return urllib.request.urlopen(req, timeout=timeout)

def post(path, body, timeout=600, raw=False):
    import urllib.error, urllib.request
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + api_key(), 'Content-Type': 'application/json',
                                          'X-Title': 'demo-builder'})
    try:
        r = _urlopen(req, timeout)
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:800]
        if e.code == 402:
            sys.exit('OPENROUTER OUT OF CREDITS (402): the account balance is empty even if the key limit has room. '
                     'Add credits at https://openrouter.ai/settings/credits, then rerun. ' + msg)
        if e.code == 401:
            sys.exit('OPENROUTER KEY REJECTED (401): check OPENROUTER_API_KEY in the studio .env. ' + msg)
        sys.exit('ERR %s %s' % (e.code, msg))
    return r if raw else json.load(r)

def generation_cost(gen_id, tries=8):
    # Speech returns no usage; the generation record has the billed cost a few seconds later.
    import urllib.request
    for _ in range(tries):
        try:
            req = urllib.request.Request(API + '/generation?id=' + gen_id, headers={'Authorization': 'Bearer ' + api_key()})
            return json.load(_urlopen(req, 30))['data'].get('total_cost')
        except Exception:
            time.sleep(3)
    return None

def run_ff(args, check=True):
    import subprocess
    return subprocess.run([FF, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y'] + args, check=check)
