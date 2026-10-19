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
| pdftotext (optional) | `brew install poppler`. Needed only when an official source is a PDF (a data sheet, for example); without it that source fails to fetch and the researcher uses another page. |
| NodeTerm | Recommended; download from https://nodeterm.dev. Without it the builder runs in a second Terminal window (references/SUPERVISING.md). |

## Local voice and Whisper

This studio runs free: no OpenRouter or other paid account, and no key. Setup installs, inside `toolkit/` and
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

## Claude Code

The studio's `.claude/settings.json` sets model `claude-opus-5-5` and effort `high` for every session opened in
this folder, including the builder session and subagents. If the session header shows another model, or
`/effort` shows another level, ask them to run `/model claude-opus-5-5` and `/effort high`. Personal settings can
override project settings, so check at the start of every job.

## Disk

A 5-minute job can reach 10 GB of raw capture and frames before cleanup. Check free space with `df -h .` and warn
them if less than 20 GB is free.
