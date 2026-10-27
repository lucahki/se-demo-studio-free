# Free, local mode: what changed from the original studio

This file describes the git branch `free-local` compared with `main` (the original studio). It is written for
someone who knows the original studio. It comes from the two commits on the branch, both dated 2026-10-19:

- `80ea786` Recorder: also hide the OneTrust dark backdrop
- `d75ad39` Free, local mode: Kokoro voice, local Whisper, no paid services

To see the same comparison yourself: `git log main..free-local` and `git diff main...free-local`.

## 1. Summary

The original studio sent everything except Claude through OpenRouter: the narration voice, word timing, music,
connective art, listening checks, and reviews of the frames. Each person needed their own OpenRouter account,
credits, and a key with a spending limit.

The free, local mode drops OpenRouter completely. Claude still does the planning, recording, editing, and
reviews, using your Claude plan. Everything else runs on your Mac with free, open models that setup downloads
once. No account, no key, no spend caps, and the narration audio never leaves the Mac.

The workflow is the same as before: interview, research, exploration, storyboard approval, build, report. There
are two new steps for you: you pick the voice by ear before the build, and you listen to a short list of lines
at the rough cut, because Claude cannot hear audio.

## 2. What was replaced

| Job | Original | Free, local mode | Differences |
|---|---|---|---|
| Narration voice | OpenRouter speech models (default `google/gemini-3.8-flash-tts`, voice `Iapetus`; about $0.08 for a 5-minute script) | Kokoro v1.0 through kokoro-onnx, on the Mac (`lib/take.py`) | Kokoro's best female voices are graded A and A- (`af_heart`, `af_bella`); its best male voices only C+ (`am_michael`, `am_fenrir`, `am_puck`). No style field, only speed (0.9 to 1.1 sounds natural). The same text and settings give a byte-identical take, so to change a read you change the words, punctuation, or speed. Each paragraph is read separately and joined with a 0.7 s gap, so cuts land in clean silence. About 4 times faster than real time on an Apple Silicon Mac. |
| Choosing a voice | Claude auditioned voices and an audio model scored them | You listen to a short audition and choose (`lib/audition.py`, new) | Seven voices by default, each with its grade and a play command. You can use a line from your own script and try other speeds. The choice is saved in `job.json` `"voice"`. |
| Word timing (captions and cut points) | `openai/whisper-large-v3` through OpenRouter | Whisper large-v3-turbo through mlx-whisper, on the Mac (`lib/stt.py`) | Same output file and format, so the rest of the pipeline is unchanged. Whisper still mishears some words. In the test run it timed all 119 words in 7 seconds with no wording differences. |
| Listening checks | `openai/gpt-audio` judged takes, pronunciation, and missing words | You, from `review/LISTEN.md` | Missing or misread words are still caught by `check_take.py` against Whisper's text. Pronunciation and audio artifacts are now a human check: the builder lists every doubtful line with its time in `audio/voice.wav`, and the supervisor goes through it with you at the rough cut. |
| Frame and fact review | Two rounds by two different non-Claude models (for example Gemini, then an OpenAI model) | Two rounds by Claude: the builder reads every contact sheet, then a fresh subagent sees only the review package, plus the `claim-checker` agent | Both rounds are now the same model family, though the second reviewer starts without the script-writing history. |
| Connective art | Image models (`google/gemini-3-pro-image`, `openai/gpt-image-2`) | HTML and CSS title cards in `build/story.js` | No generated backgrounds. |
| Spend tracking | Per-job cap (`budget_usd`, default $15), cost log, key limit check | Removed | Nothing costs money, so there is nothing to cap. |

## 3. What was removed or turned off

- **Generated music.** `lib/music.py` (Lyria) is gone. Music is now off by default.
- **The AI caller.** ChatGPT voice mode placing a live call over Webex Calling, with two BlackHole audio cables,
  is removed: `capture/caller.js`, `capture/caller_patch.js`, and the `AI_CALLER.md` reference, plus the
  interview question and builder prompt section that offered it. Demos that need a live call now use the
  existing owner-action flow, where you place the call yourself when the builder asks.
- **OpenRouter plumbing.** The key loader, HTTP client, and cost logging in `lib/common.py`; `lib/chat.py`,
  `lib/models.py`, `lib/spend.py`, `lib/img.py`; `scripts/check-openrouter.sh`; `.env.example`; and every
  mention of the key, credits, and budget in the skill, setup, and README.
- **Budget question.** The interview asks about time and music instead of spend.

### Using your own music

1. Pick a track you have the rights to use (licensed, royalty-free, or your own).
2. Put it in the job's `audio/music/` folder.
3. Set `music` in the job's `job.json`, for example:
   `{"file": "audio/music/track.mp3", "level_db": -20, "duck_db": -6, "intro_boost_db": 11}`.
   The track runs under the whole video, fitted so its own ending lands at the end, about 20 dB under the voice and
   lower while the SE speaks, louder in the intro (section 10). Jobs made before 2026-10-27 keep their own `mix.py`
   and its `"windows"` setting.
4. Run `python3 lib/mix.py out/mix.wav` as usual.

An empty `"file"` (the default) means no music. If the file path is wrong, `mix.py` now stops with a clear
message instead of mixing without it.

## 4. Other changes

- **Cookie banner backdrop.** The recorder (`capture/rec.js`) already hid the OneTrust cookie banner but left
  its full-screen dark backdrop, which dimmed every frame of the test run. It now hides
  `.onetrust-pc-dark-filter` as well.
- **Setup checks.** `scripts/setup.sh` no longer creates `.env` or checks a key. It installs `uv`, a private
  Python 3.13, and pinned packages into `toolkit/`, downloads the Kokoro and Whisper models with a size and
  SHA-256 check on each file, and confirms the packages import. New status lines: `Kokoro voice (local)`,
  `Whisper (local)`, `local tools (Python 3.13.x)`. It passes with no key, and only reinstalls the packages
  when `toolkit/requirements-local.txt` changes.
- **Scripts find their own Python.** `lib/take.py` and `lib/stt.py` switch to `toolkit/.venv` on their own, so
  commands are still `python3 lib/<script>.py`.
- **macOS `say` as a draft voice.** `lib/take.py --engine say` reads with the built-in Mac voices for quick
  drafts. It prints a warning and marks the take's log "draft only", because Apple licenses those voices for
  personal, non-commercial use. Never use one in a shared video.
- **Job settings.** `job.json` gains `"voice": {"name": "am_michael", "speed": 1.0}` and loses `budget_usd`.
  New jobs no longer get a `logs/costs.jsonl`.
- **Permissions.** `.claude/settings.json` pre-approves `afplay audio/*` (to play auditions and takes) in place
  of `scripts/check-openrouter.sh`.
- **Studio rules.** `CLAUDE.md` and the skill now say: never call OpenRouter, OpenAI, or any other paid or
  remote AI service, and never add one back during a job.
- **What leaves your Mac.** Only what Claude reads (product screens, page text, job files) goes to Anthropic.
  Setup downloads the tools once from PyPI, GitHub, and Hugging Face.
- **Updates.** The README now explains how to bring in new versions of the original:
  `git fetch origin`, then `git merge origin/main`, and how to switch between the two versions
  (`git switch main`, `git switch free-local`).

- **Cursor rules (L66).** This branch adds default cursor rules that `main` does not have: eased moves only,
  park the cursor before a wait, prefer a 4x to 8x speed-up to a cut, fade the cursor at cuts (`cursorOff` in
  `build/story.js`, drawn by `build/scenes.js`), and a jump check at the end of `lib/cursor_tracks.py` that
  prints `CURSOR JUMP` and `CURSOR CUT` lines. The rules are in the builder prompt template and `PIPELINE.md`.

## 5. Setup

You need what the original needed (macOS, Chrome, Node.js 20 or newer, Python 3, Claude Code with Opus 5.5) and
an **Apple Silicon Mac**, because Whisper runs on MLX. Then run `scripts/setup.sh` from the studio folder. It
installs everything below inside `toolkit/`, with no admin rights:

| What | Where | Download | On disk |
|---|---|---|---|
| `uv` and Python 3.13 | `toolkit/.uv`, `toolkit/.python` | about 35 MB | about 110 MB |
| Packages (kokoro-onnx, ONNX Runtime, mlx-whisper, MLX, and their dependencies; no PyTorch) | `toolkit/.venv` | about 150 MB | about 620 MB |
| Kokoro v1.0 model and voices | `toolkit/models/kokoro` | 354 MB | 354 MB |
| Whisper large-v3-turbo (MLX format) | `toolkit/models/whisper-large-v3-turbo` | 1.6 GB | 1.6 GB |
| **Total for the local voice and Whisper** | | **about 2.1 GB** | **about 2.6 GB** |

This is on top of the capture and render tools the original already installed (`toolkit/node_modules`, about
400 MB). After setup, the voice and word timing work with no network.

If a line fails: for **DOWNLOAD FAILED**, check the network (behind a proxy, run
`export HTTPS_PROXY=<address>` in the same Terminal first); for **FAILED** or **BROKEN**, delete
`toolkit/.venv` and rerun setup. To remove the local tools completely, delete `toolkit/.venv`, `toolkit/.uv`,
`toolkit/.python`, and `toolkit/models`.

Licenses: Kokoro model Apache-2.0; kokoro-onnx, ONNX Runtime, MLX, mlx-whisper, and the Whisper weights MIT;
numpy, scipy, numba BSD; uv MIT or Apache-2.0. Kokoro uses espeak-ng and phonemizer (GPL-3.0) for
pronunciation. Running them and using the audio is fine; the GPL applies to handing the software itself to
others. Check your company's open source policy if it asks for GPL tools to be registered.

## 6. Every file changed, added, or removed

### Added

| File | Why |
|---|---|
| `toolkit/job-template/lib/audition.py` | Reads one sample in several Kokoro voices with their grades, so you can pick one by ear. |
| `toolkit/requirements-local.txt` | Pins every Python package for the local voice and Whisper (installed with `--no-deps`, no PyTorch). |

### Changed

| File | Why |
|---|---|
| `.claude/settings.json` | Pre-approves `afplay audio/*` instead of the OpenRouter check. |
| `.claude/skills/record-demo/SKILL.md` | Preflight with no key, a free test run, the new voice audition step before launch, and the no-paid-services rule. |
| `.claude/skills/record-demo/references/BUILDER_PROMPT_TEMPLATE.md` | Voice from the audition, `review/LISTEN.md` for the owner, no music unless supplied, reviews by Claude, "Cost" instead of "Budget", AI caller section removed. |
| `.claude/skills/record-demo/references/INTERVIEW.md` | What leaves the Mac, voice picked by audition, time and music instead of budget, AI caller offer removed. |
| `.claude/skills/record-demo/references/MODELS.md` | Lists Claude, Kokoro with voice grades, local Whisper, and who does each check, instead of OpenRouter models. |
| `.claude/skills/record-demo/references/PIPELINE.md` | New voice, timing, and music commands; review by Claude; results of the 2026-10-19 local test run. |
| `.claude/skills/record-demo/references/SETUP.md` | "Local voice and Whisper" section (sizes, checksums, licenses, fixes) replaces the OpenRouter walkthrough. |
| `.claude/skills/record-demo/references/SUPERVISING.md` | Spend checks replaced by going through `review/LISTEN.md` with the person; AI caller launch note removed. |
| `.claude/skills/record-demo/test-run/job-settings.json` | Drops `budget_usd`. |
| `.gitignore` | Ignores the local tools and models installed into `toolkit/`. |
| `CLAUDE.md` | Describes the free, local mode and forbids paid or remote AI services. |
| `README.md` | No OpenRouter, free test run, new disk size, "Free, local mode" section, how to update and switch branches. |
| `scripts/new-job.sh` | No longer creates `logs/costs.jsonl`. |
| `scripts/setup.sh` | Installs and checks the local voice and Whisper instead of the OpenRouter key. |
| `toolkit/job-template/capture/rec.js` | Also hides the cookie banner's dark backdrop. |
| `toolkit/job-template/job.json` | Adds `voice`, drops `budget_usd`. |
| `toolkit/job-template/lib/common.py` | Paths to the local Python and models, and a helper that switches to it; OpenRouter, key, and cost code removed. |
| `toolkit/job-template/lib/mix.py` | Comments explain music is optional; stops clearly if the music file is missing. |
| `toolkit/job-template/lib/stt.py` | Runs Whisper large-v3-turbo locally with mlx-whisper; same output. |
| `toolkit/job-template/lib/take.py` | Runs Kokoro locally, paragraph by paragraph, with voice and speed from `job.json`; optional `say` draft engine. |

### Removed

| File | Why |
|---|---|
| `.claude/skills/record-demo/references/AI_CALLER.md` | AI caller removed (it sent the whole call to OpenAI). |
| `.env.example` | No key to store. |
| `scripts/check-openrouter.sh` | No key to check. |
| `toolkit/job-template/capture/caller.js` | AI caller removed. |
| `toolkit/job-template/capture/caller_patch.js` | AI caller removed. |
| `toolkit/job-template/lib/chat.py` | Sent frames and audio to reviewer models; Claude reviews now. |
| `toolkit/job-template/lib/img.py` | Image generation removed. |
| `toolkit/job-template/lib/models.py` | Listed OpenRouter models. |
| `toolkit/job-template/lib/music.py` | Music generation removed. |
| `toolkit/job-template/lib/spend.py` | Spend tracking removed. |

## 7. Known limitations

- **Male voices are weaker.** Kokoro's best male voices grade C+, against A and A- for its best female
  voices. Hear both before deciding.
- **Less control over the read.** No style or emotion setting; only words, punctuation, and speed change how a
  line sounds.
- **Claude cannot hear the narration.** Pronunciation, odd stresses, and audio glitches are only caught if you
  listen to the lines in `review/LISTEN.md`. A video nobody has listened to is not checked for these.
- **Whisper still mishears.** It wrote "SD-WAN" as "SDWAN", for example. A flagged line may be a Whisper
  mistake, not a voice mistake: listen before rewording.
- **Reviews are less independent.** Both review rounds are Claude, where the original used two other model
  families. The second round starts fresh, but it is the same model.
- **No music or art generation.** Music must be a track you have the rights to; title cards are plain HTML and
  CSS.
- **No AI caller.** Demos with a live phone call need a person to place it.
- **Apple Silicon only.** Whisper runs on MLX, which needs an M-series Mac.
- **Disk and first download.** About 2.1 GB to download and 2.6 GB on disk, on top of the original 400 MB.
- **`say` is drafts only.** The macOS voices may not be used in a shared video.
- **Pinned versions.** The Python packages and model files are pinned by version and checksum. Newer versions
  only arrive when `requirements-local.txt` and `setup.sh` are updated.
- **Old job folders keep their own copy of the scripts.** Each job copies `toolkit/job-template/` when it is
  created. A job made on `main` still has the OpenRouter scripts inside it; start a new job on this branch
  instead of continuing an old one.
- **Merging updates from the original.** New versions of `main` may change the same files (setup, the skill,
  `take.py`, `stt.py`), so a merge can need conflicts resolved by hand.
- **One recorded end-to-end test.** The branch documents one full test: the test run on 2026-10-19 (a
  55-second video, no music). Longer demos have no recorded result yet in the studio's notes.

## 8. Later change: a choice of three voice engines (2026-10-21)

After a side-by-side listening test, the voice step now asks which engine to use. Kokoro stays the default, and a
job with no `"engine"` in job.json is still Kokoro, so older jobs are unchanged.

| Engine | What it is | Cost and where it runs | Tested |
|---|---|---|---|
| `kokoro` | Kokoro v1.0, as before | Free, on the Mac, about 4 times faster than real time | Unchanged; a take from the new `take.py` matched the old behavior |
| `chatterbox` | Chatterbox original English model (Resemble AI, MIT), built-in voice, default speed 0.94 | Free, on the Mac GPU, about 7 times slower than real time on an M1 Pro; installed only when picked (`scripts/setup-chatterbox.sh`, about 3.5 GB) | Install, take, audition, Whisper alignment; the agenda paragraph read in 2 minutes for 18.4 s of speech |
| `openrouter` | `google/gemini-3.8-flash-tts`, voice Iapetus, the original studio's voice | Paid from the person's own key in `.env`, voice only, capped per job by `budget_usd` (default $2) | Only that it stops before any network call when no key is set; no paid take was made |

Findings from the test: Chatterbox's reads differ run to run even with the same seed on the Mac GPU. Its default
pace sounded rushed; a 6% pitch-preserving stretch (speed 0.94) was the take preferred by ear. VoxCPM2 (OpenBMB,
Apache-2.0, 2B) was also tried and dropped: on a 16 GB M1 Pro its maintainers force full precision on the GPU,
which swapped (about 30 s per step), and the CPU path was still too slow for full scripts.

Files: `lib/take.py` (engines), `lib/audition.py` (`--engine`), `lib/common.py` (Chatterbox paths, OpenRouter
key loader, request, cost log, and voice cap restored from main for the voice only), `job.json` (`"engine"`),
new `scripts/setup-chatterbox.sh` and `toolkit/requirements-chatterbox.txt`, restored `scripts/check-openrouter.sh`
and `.env.example` (voice only), `scripts/setup.sh` (an optional Chatterbox status line), `.gitignore`,
`.claude/settings.json` (allows the two scripts), `CLAUDE.md`, the skill and its references, and the README.
Word timing, reviews, music, and everything else stay local.

## 9. Later change: narration in other languages (2026-10-27)

After the Italian version of a finished demo, the studio can narrate and caption
in English, Italian, Spanish, French, or Brazilian Portuguese. job.json `"language"` picks it (default `"en"`), so
English jobs are unchanged. Everything still runs on the Mac.

| Part | Change | Tested |
|---|---|---|
| Kokoro (`lib/take.py`) | Reads in the job's language with a voice of that language (Italian `im_nicola`, `if_sara`); refuses a voice that does not speak it. `[en:word]` reads one word with English pronunciation | English: a take, its Whisper words, alignment, narration, cues, captions, player page, and voice list byte-identical to the scripts before the change. Italian: reproduces the Italian job's final take sample for sample |
| Chatterbox | Chatterbox Multilingual (Resemble AI, MIT, same Hugging Face commit) for other languages: `scripts/setup-chatterbox.sh --multilingual`, 3.2 GB, size and SHA-256 checked | An Italian line, transcribed correctly; English Chatterbox also rerun |
| Setup | `setup-chatterbox.sh` rebuilds `toolkit/.venv-chatterbox` when its Python no longer starts. It had been made from a Python under `voice-test/` that was later deleted, so Chatterbox could not start; the script found and rebuilt it | Rerun ends with "CHATTERBOX OK" |
| Whisper (`lib/stt.py`) | Transcribes in the job's language (`--language` overrides) | Italian takes |
| Text matching (`speech.py`, `timeline.py`, `deliver.py`) | Accents folded (è -> e) instead of dropped; `[en:word]` written as the plain word | Italian captions show the approved wording, no respellings |
| New `lib/spoken.py` | Builds `script/speech.txt` from the approved `script/written.txt` and job.json `"respell"`, and stops if the captions would not show the approved wording | Rebuilt the Italian job's spoken text; it also caught one "Webex" before a full stop that the job's own script had left unrespelled |
| `lib/audition.py`, player | Voice list, default voices, and sample in the job's language; player page and caption track labelled with it | Italian list and player |

Files: `toolkit/job-template/lib/` (`common.py`, `take.py`, `stt.py`, `speech.py`, `timeline.py`, `deliver.py`,
`audition.py`, `player_template.html`, new `spoken.py`), `toolkit/job-template/job.json` (`"language"`),
`scripts/setup-chatterbox.sh`, `CLAUDE.md`, the README, the skill, and its references (new `LOCALIZE.md`: making a
finished job in another language from its own screen capture, with the Italian findings).

## 10. Later change: the voice joins and music mix from the 2026-10-20 demo (2026-10-27)

That demo fixed two things in its own copies of the scripts, after
listening by ear. They are now in the template, so new jobs get them. Jobs made earlier keep their own scripts.

| Part | Change | Tested |
|---|---|---|
| Voice joins (`lib/build_voice.py`) | Each paragraph is cut at the take's own 0.7 s silences instead of at Whisper's word ends, which run early and clipped word endings; 10 ms fade-in, 30 ms fade-out. Falls back to word-based cuts when a take has no such silences (OpenRouter) | The demo's final take rebuilt: narration and cues byte-identical to the demo's; a new Kokoro take: 0 joins needing a look |
| New `lib/join_scan.py` | Checks that every join starts and ends in silence or a fade, with nothing in the gaps | Both takes above |
| Music (`lib/mix.py`) | Replaces the music "windows": the track runs under the whole video at a level set from the voice's measured loudness (`level_db` -20), lowered while the SE speaks (`duck_db` -6, held through pauses under 1.2 s), louder in the music-only intro and easing down before the first word (`intro_boost_db` 11), fading out after the last word; master -16 LUFS with a -1.5 dBTP limiter; measured levels in `build/mix_levels.json`; `--from/--to` excerpts for samples | The demo's mix rebuilt from its voice and sounds: byte-identical to the demo's `out/mix.wav`; no-music and short-video mixes |
| New `lib/music_bed.py` | Fits the track to the video so its own ending lands at the end: plays as is within 8 bars, else one skip forward, or one or two bar-aligned jumps back, crossfaded over one bar where the music matches best. Generalized from the demo's copy (one track, always two jumps) | The demo's and its Italian version's beds byte-identical; 55, 90, 100, 120, and 180 s videos fitted within 0.7 s; a 500 s video stops with a message |

Files: `toolkit/job-template/lib/` (`build_voice.py`, `mix.py`, new `music_bed.py` and `join_scan.py`),
`toolkit/job-template/job.json` (`music` fields), the test run's `job-settings.json`, PIPELINE.md, MODELS.md.
