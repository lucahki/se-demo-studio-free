# Models

Claude: every Claude Code session and subagent in this studio runs `claude-opus-5-5` at high effort (set in
`.claude/settings.json`, the skill, and every agent file). Launch NodeTerm sessions with the exact id
`--model claude-opus-5-5`, never the `opus` alias, which resolved to an older Opus on 2026-09-23.

Everything else runs on this computer and costs nothing (free, local mode; installed by `scripts/setup.sh`), except
the OpenRouter voice when the owner picks it.

| Job | Tool | Notes |
|---|---|---|
| Demo voice (default) | Kokoro v1.0 through kokoro-onnx (`lib/take.py`, engine `kokoro`) | The owner picks the engine in the interview and the voice by ear with `lib/audition.py` before the build. Default `am_michael`. No style field; only speed (0.9 to 1.1 sounds natural). Same text and settings give an identical take. About 4 times faster than real time on an M-series Mac. Apache-2.0. |
| Demo voice (optional, free) | Chatterbox, original English model (Resemble AI, MIT), engine `chatterbox` | Installed only when picked (`scripts/setup-chatterbox.sh`, about 3.5 GB). One built-in voice; speed 0.94 sounded less rushed than 1.0 in the 2026-10-21 test. About 7 times slower than real time on an M1 Pro (17 s of speech in 2 minutes). Reads vary run to run. Inaudible Perth watermark in every take. VoxCPM2 (Apache-2.0) was also tried that day and dropped: on a 16 GB M1 Pro it needs full precision on the GPU and swapped. |
| Demo voice (optional, paid) | `google/gemini-3.8-flash-tts` through OpenRouter, voice `Iapetus`, engine `openrouter` | From the original studio (L22): won for "calm, assured, technical demo voice"; `Charon` is better for ads. One call holds a 5-minute script, about $0.08. Needs the owner's own key in `.env`; the script text leaves the Mac. |
| Demo voice in another language | Kokoro in the job's language (job.json `"language"`: `it`, `es`, `fr`, `pt`), or Chatterbox Multilingual (Resemble AI, MIT, 23 languages; `scripts/setup-chatterbox.sh --multilingual`, 3.2 GB) | Kokoro voices: Italian `im_nicola`, `if_sara` (C), French `ff_siwis` (B-), Spanish `em_alex`, `ef_dora`, `em_santa` and Portuguese `pm_alex`, `pf_dora`, `pm_santa` (not graded). English names need respelling in the language's spelling, or `[en:word]` for English pronunciation (references/LOCALIZE.md). In the 2026-10-27 Italian test Kokoro `im_nicola` won: Chatterbox Multilingual's built-in voice misread acronyms differently each run, and took about 9 to 10 times real time. |
| Voice grades | from the Kokoro voice list | American women: `af_heart` A, `af_bella` A-, `af_nicole` B-. American men: `am_michael`, `am_fenrir`, `am_puck` C+. British: `bf_emma` B-, `bm_george` and `bm_fable` C. `python3 lib/audition.py --list` shows all. |
| Word timestamps | Whisper large-v3-turbo through mlx-whisper on a Mac, faster-whisper on Windows (`lib/stt.py`, in job.json `"language"`) | Mishears some words (it wrote "SD-WAN" as "SDWAN", which the alignment accepts); list doubtful lines for the owner's listen before rewording. |
| Listening | the owner | Claude cannot hear audio. Wording is checked against Whisper's text by `check_take.py`; pronunciation and artifacts are checked by the owner from `review/LISTEN.md`. Joins are judged by `build_voice.py`'s JOIN numbers (L56). |
| Music | none, or the owner's own track | No music generator. A track the owner has the rights to goes in `audio/music/` and job.json `music`; `lib/music_bed.py` fits it to the video and `lib/mix.py` sets its level from the measured voice loudness (PIPELINE.md step 5). |
| Frame and fact review | Claude | Round 1 by the builder, round 2 by a fresh subagent that has not seen the script being written, plus the `claim-checker` agent. |
| Connective art | none | Title cards and backgrounds are built in HTML and CSS in `build/story.js`; never imitate product UI. |
| Draft voice only | macOS `say` (`lib/take.py ... --engine say`, Mac only) | Apple licenses these voices for personal, non-commercial use, so never in a shared video. |
