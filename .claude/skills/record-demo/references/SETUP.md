# Setup

Run `scripts/setup.sh` from the studio root. It checks everything and installs the capture and render tools
into `toolkit/node_modules` on first run (about 400 MB; that install needs no admin rights). Rerun it any time;
it ends with "SETUP OK" or lists what to fix. Walk the person through each failing line below, one at a time, and
rerun. If they have no Homebrew, use the download links below instead of `brew`; on a company-managed Mac, the
Node.js, Python, or Chrome installers may need IT.

## Requirements

| Line in setup.sh output | What to do |
|---|---|
| macOS | This studio is built and tested on macOS only. |
| Node.js | `brew install node`, or the installer from https://nodejs.org (version 20 or newer). |
| Python 3 | `xcode-select --install` (includes Python 3), or `brew install python`. The system Python needs no extra packages; setup installs a separate Python 3.13 for the voice and Whisper (below). |
| Claude Code | Update with `claude update`. The studio was tested on Claude Code 2.1.300. |
| Google Chrome | Install from https://www.google.com/chrome into Applications (the system one or the one in their home folder). Capture drives a separate Chrome window with its own profile, so their normal browsing is untouched. |
| toolkit install | `(cd toolkit && npm install)` and read any error. Behind a corporate proxy, ask IT for the proxy address and run `npm config set proxy <that address>`. |
| local tools install, Kokoro voice (local), Whisper (local), local tools | See "Local voice and Whisper" below. |
| Chatterbox voice (optional) | Information only. "not installed" is fine unless a job picks Chatterbox; see "Chatterbox voice" below. |
| pdftotext (optional) | `brew install poppler`. Needed only when an official source is a PDF (a data sheet, for example); without it that source fails to fetch and the researcher uses another page. |
| NodeTerm | Recommended; download from https://nodeterm.dev. Without it the builder runs in a second Terminal window (references/SUPERVISING.md). |

## Local voice and Whisper

By default this studio runs free: no OpenRouter or other paid account, and no key. Setup installs, inside `toolkit/` and
without admin rights:

| What | Why | Download | On disk |
|---|---|---|---|
| `uv` (in `toolkit/.uv`) and Python 3.13 (in `toolkit/.python`) | Kokoro needs Python 3.10 to 3.13 | about 35 MB | about 110 MB |
| Packages in `toolkit/.venv`, pinned in `toolkit/requirements-local.txt` | kokoro-onnx, ONNX Runtime, mlx-whisper, MLX | about 150 MB | about 620 MB |
| Kokoro v1.0 model and voices (`toolkit/models/kokoro`) | the narration voice | 354 MB | 354 MB |
| Whisper large-v3-turbo, MLX format (`toolkit/models/whisper-large-v3-turbo`) | word timestamps | 1.6 GB | 1.6 GB |

Every model download is checked against its size and SHA-256 before it is kept. After setup, the voice and word
timing run on this Mac with no network. The scripts switch to `toolkit/.venv` on their own, so commands stay
`python3 lib/<script>.py`.

Licenses: Kokoro model Apache-2.0; kokoro-onnx, ONNX Runtime, MLX, mlx-whisper, and the Whisper weights MIT;
numpy, scipy, numba BSD; uv MIT or Apache-2.0. Kokoro works out pronunciation with espeak-ng and phonemizer,
which are GPL-3.0: fine to run and to use the audio they help make, since the GPL covers handing the software
itself to others. If their company's open source policy asks for GPL tools to be registered even for internal
use, they can check that.

macOS `say` (`lib/take.py ... --engine say`) is a draft fallback only. Apple's macOS license allows the system
voices "for your personal, non-commercial use" and rules out recording or publishing them in a commercial
context, so a `say` take never goes into a video that is shared.

If a line fails:
- **DOWNLOAD FAILED**: check the network. Behind a corporate proxy, ask IT for the proxy address and run
  `export HTTPS_PROXY=<that address>` in the same Terminal before `scripts/setup.sh`. A partial download is
  deleted and retried on the next run.
- **local tools install FAILED** or **BROKEN**: delete `toolkit/.venv` and rerun `scripts/setup.sh`.
- Disk: the tools take about 2.6 GB; deleting the `toolkit/.venv`, `.uv`, `.python`, and `models` folders removes
  them completely.

## Chatterbox voice (optional, free)

Only when a job picks it. `scripts/setup-chatterbox.sh` installs it inside `toolkit/`, without admin rights, and
ends with "CHATTERBOX OK"; rerun it any time as a check.

| What | Download | On disk |
|---|---|---|
| Python 3.11 (in `toolkit/.python`) and packages in `toolkit/.venv-chatterbox`, pinned in `toolkit/requirements-chatterbox.txt` (PyTorch 2.6.0, chatterbox-tts 0.1.7) | about 320 MB | about 1.3 GB |
| Chatterbox model, pinned to one Hugging Face commit (`toolkit/models/chatterbox`) | 3.2 GB | 3.2 GB |

Every model file is checked against its size and SHA-256. Licenses: the Chatterbox code and weights are MIT
(Resemble AI). Its packages are permissive except pykakasi (GPL-3.0, Japanese text only) and soxr (LGPL-2.1),
fine to run for the same reason as phonemizer above. It runs on the Mac GPU: about 7 times slower than real time
on an M1 Pro with 16 GB. Every take carries Resemble's inaudible Perth watermark, which marks it as AI speech.
If "Chatterbox (local) BROKEN": delete `toolkit/.venv-chatterbox` and rerun. To remove it: delete
`toolkit/.venv-chatterbox` and `toolkit/models/chatterbox`.

## OpenRouter voice (optional, paid)

Only for someone who picks it and has their own OpenRouter account; nothing else in the studio uses OpenRouter.
It receives the script text (and the voice provider behind it does too). Walk them through, in order:

1. **Account and credits** at https://openrouter.ai and https://openrouter.ai/settings/credits. A few dollars
   covers many jobs: a 5-minute script is about $0.08 a take.
2. **Key** at https://openrouter.ai/settings/keys, with a **credit limit** on it (for example $5) so a runaway job
   cannot overspend. `check-openrouter.sh` does not pass without a limit.
3. **Save it in the studio `.env`, never in the chat.** If there is no `.env` yet, they run
   `cp .env.example .env && chmod 600 .env`, then `open -e .env` (TextEdit), paste the key after
   `OPENROUTER_API_KEY=` with no spaces or quotes, and save. If they paste the key into the chat anyway, tell
   them to delete that key on the keys page and create a new one.
4. **Verify** with `scripts/check-openrouter.sh`. It prints usage and limit, never the key. HTTP 401 means the
   key is wrong; "OUT OF CREDITS (402)" from a later take means the account balance is empty.
5. If a take fails with a message about data policy or "no endpoints found", try the other voice model in
   references/MODELS.md before touching https://openrouter.ai/settings/privacy, and tell them first that
   allowing more providers means those providers receive the script text.

Never read `.env` yourself (the studio settings deny it); `lib/take.py` loads the key on its own. Each job caps
its voice spend with job.json "voice" "budget_usd" (default $2).

## Claude Code

The studio's `.claude/settings.json` sets model `claude-opus-5-5` and effort `high` for every session opened in
this folder, including the builder session and subagents. If the session header shows another model, or
`/effort` shows another level, ask them to run `/model claude-opus-5-5` and `/effort high`. Personal settings can
override project settings, so check at the start of every job.

## Disk

A 5-minute job can reach 10 GB of raw capture and frames before cleanup. Check free space with `df -h .` and warn
them if less than 20 GB is free.
