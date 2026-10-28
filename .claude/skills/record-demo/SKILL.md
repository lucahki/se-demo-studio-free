---
name: record-demo
description: Plan, record, and produce a narrated virtual SE product demo video (or a short product ad) from a live, signed-in product in Chrome, with AI voice, captions, and a player page. Use when the person says "help me record a demo", "make a demo video", "build a virtual SE demo", asks you to come up with a demo idea or scenario for a video in their product or environment, asks to continue a demo job in jobs/, or says "do a test run" (a short first video that proves the setup, with no demo environment or sign-in).
model: claude-opus-5-5
effort: high
---

# Record a demo

You run a small studio. The person tells you what they want in an interview; you research the product, set up a
job, launch a builder session that explores, records, narrates, and renders the video, and bring the story back
for their approval before final recording. Everything happens inside this folder.

Current effort for this session: ${CLAUDE_EFFORT}

## Step 0: preflight (every time)

Run this before any exploration or planning, including when the conversation started as brainstorming a demo
idea. A missing tool or the wrong effort found after an hour of planning costs a restart.

0. **Studio root.** The session must start in the studio root (the folder holding `.demo-studio`); the studio's
   agents (`demo-researcher`, `demo-explorer`, `claim-checker`) only register there. If the Agent tool says one is
   not found, ask the person to restart `claude` in the studio root. If they would rather not, run a
   general-purpose agent instead, with the agent file's body from `.claude/agents/<name>.md` pasted in as its
   instructions, and say you did.
1. **Model and effort.** This studio must run on Opus 5.5 at high effort. If the effort shown above is not
   `high`, or the session is not running `claude-opus-5-5`, stop and ask the person to run `/model
   claude-opus-5-5` and `/effort high`, then continue. The studio settings set both, but personal settings can
   override them.
2. **Continuing a job?** If the person names an existing job, or `jobs/*/SUPERVISOR.md` shows a builder still
   running, read that job's `SUPERVISOR.md`, `ORCHESTRATOR_NOTES.md`, and newest files, tell them where it
   stands, and resume supervising (references/SUPERVISING.md). Skip the interview.
3. **Setup.** Run `scripts/setup.sh`. If it does not end with "SETUP OK", walk them through
   references/SETUP.md one failing line at a time. There is no key to set up; never read `.env`.

## Test run

Use this when the person says "do a test run", or when `jobs/` does not exist yet (their first time) and they
agree to one before the interview. It records a short narrated video of a public cisco.com page with the files in
`test-run/` (next to this skill), proving the install, capture, the local voice and Whisper, render, captions, and player.
No interview, research, claim check, music, or storyboard stop. Run Step 0 first (items 0, 1, and 3).

Tell them first: it takes about 5 to 10 minutes and costs nothing (everything except Claude runs on their computer); a separate
Chrome window opens on a public Cisco page, with nothing to sign in to; leave it alone while it records (about a minute).

1. From the studio root: `scripts/new-job.sh test-run --test-run` (if `jobs/test-run` exists, use `test-run-2`, and
   so on; `<slug>` below). It copies the ready-made test files and settings into the job.
2. `scripts/chrome.sh <slug>`. In `jobs/<slug>/`: `node capture/rec.js take1 capture/takes/test_run.js`, then
   `python3 lib/recsheet.py take1 4 12 26 44` and look at `review/sheet_take1.jpg`: the Cisco page, no cookie banner.
3. Voice: `python3 lib/take.py T1` (Kokoro's `am_michael`, on this computer), `python3 lib/stt.py audio/takes/T1.wav`,
   `python3 lib/check_take.py T1`, `python3 lib/build_voice.py T1` (it must end with `edge check: ok`).
4. Picture and sound: `python3 lib/build_clips.py`, `python3 lib/cursor_tracks.py`, `python3 lib/sfx.py`,
   `python3 lib/sfx_events.py`, `python3 lib/mix.py out/mix.wav`.
5. Render: `build/render_par.sh out/<slug>_v1.mp4 8 out/mix.wav`, `python3 lib/deliver.py <slug>_v1.mp4`.
   Then from the studio root `scripts/chrome.sh <slug> --stop`.

If a step fails, stop and tell them which part of the setup it points to (local tools, Chrome, voice, render), using
references/SETUP.md. Tell them after: the video is `jobs/<slug>/out/<slug>_v1.mp4` and the player with captions
is `jobs/<slug>/player.html` (offer `open jobs/<slug>/player.html`, or `start jobs/<slug>/player.html` on Windows); that it cost nothing; and that a real demo starts with
the interview and a voice audition, needs a demo environment they sign in to, and takes a few hours (a recent one took about 4). Offer to start it.

## Version in another language

When the person wants a finished job in another language ("an Italian version of my last video"), reuse its
screen capture: follow references/LOCALIZE.md. No interview, research, or recording; the approval points are the
translated talk track, the voice by ear, and the stills they name. Never change the original job.

## Step 1: interview

Follow references/INTERVIEW.md. Start by asking for the ask in their own words, then the rounds of questions.
Save answers to `jobs/<slug>/INTERVIEW.md` once the job exists (keep them in your notes until then). Read the
summary back and get a yes.

If the conversation already settled most answers (for example the person asked for a demo idea and you discussed
it), do not run the full rounds. Propose the story in plain words, ground it in the environment (Step 3), then ask
only the questions still open, each with a recommendation.

## Step 2: create the job

Create the job as soon as the product and environment are known, even before the story is settled, so every look
at the product happens in the job's own Chrome and the person signs in once.

1. `scripts/new-job.sh <slug>` (assigns a free Chrome port).
2. Fill `jobs/<slug>/job.json`: title, disclosure, hours, `app_url`, `app_match`, theme, respellings.
3. Write `INTERVIEW.md` in the job folder. Add a "Verified facts" section (exact names, values hidden behind
   variables or settings panels, which records exist, schedules, identities, each with where you saw it) and a
   "Still unverified" list that the builder's exploration must close before the storyboard.

## Step 3: research (in parallel with sign-in)

1. Launch the `demo-researcher` agent in the background with the product, the audience, the ask, and the job
   path. It writes `research/SOURCES.md` (verbatim quotes, URLs, availability, contradictions) and
   `research/PRODUCT_UNDERSTANDING.md` (problem, how it works, workflow with exact surface names, where the value
   comes from, must-not-claim list, demo moments).
2. Meanwhile start the job's Chrome with `scripts/chrome.sh <slug> <demo url>` and ask the person to sign in
   there. For dCloud, they reserve or open the instant demo first and paste its launch URL. Time-limited demos
   reward starting capture soon after sign-in. They sign in to every surface the story uses (references/INTERVIEW.md
   question 14), and sign out of single-session apps in any other browser first.
3. In the person's own environment, or whenever the story depends on specific configuration, do your
   reconnaissance in that same Chrome through `capture/tab.js` from the job folder, not in another browser. Look
   only; record what you confirm in INTERVIEW.md's "Verified facts". Take no screenshot until the page is signed in.

## Step 4: write the builder prompt

Copy the prompt from references/BUILDER_PROMPT_TEMPLATE.md into `jobs/<slug>/PROMPT.md` and fill every slot from
the interview and the research (for Cisco products also apply references/CISCO_CLAIM_RULES.md). Replace each slot
by its full `{{...}}` text, never by a key prefix: a script that matches `{{PRODUCT` also hits any longer slot that
starts with the same word. Check that no `{{` remains (`grep -n '{{' jobs/<slug>/PROMPT.md`). Tell the person in three or four lines what the builder will
do and that it will stop for their approval at the storyboard.

**Voice audition (before launch).** First the voice engine they picked in the interview (INTERVIEW.md question
11), then the voice itself by ear. You cannot hear audio, so the choice is theirs: ask them to play each sample
(`python3 lib/play.py audio/audition/<file>.wav`, or double-click the files in Finder or File Explorer). Each
audition command prints its play commands; `--text <file>` uses a line of their own script.

- **Kokoro** (free, on this computer, fast; the default). Run `python3 lib/audition.py`: one short sample in seven
  voices, each with its quality grade (`--list` shows all English voices; name voices to try others). Say plainly
  that Kokoro's best male voices grade C+ and its best female voices A and A- (`af_heart` A), so it is worth
  hearing both even if they asked for one. Offer a speed of 0.9 to 1.1 for the pick
  (`python3 lib/audition.py <voice> --speed 0.95`). Save as `"voice": {"engine": "kokoro", "name": ..., "speed": ...}`.
- **Chatterbox** (free, on a Mac, slow; not set up for Windows yet, so offer Kokoro there). Check that `scripts/setup-chatterbox.sh` ends with "CHATTERBOX OK";
  if it is not installed, tell them it downloads about 3.5 GB once, and run it only after they agree. Then
  `python3 lib/audition.py --engine chatterbox` (about a minute). It has one voice, `builtin`, read 6% slower by
  default (speed 0.94, picked by ear as less rushed than 1.0). It takes about 7 times real time on an M1 Pro, so
  a 4-minute script needs about 30 minutes per full take: count that in the time budget. Takes are not
  repeatable: the same settings give a slightly different read each run. Every file carries an inaudible
  watermark marking it as AI speech. Another voice means cloning a clip they have the rights to (about 10 s of
  clean speech, saved in the job folder, its path as `name`). Save as
  `"voice": {"engine": "chatterbox", "name": "builtin", "speed": 0.94}`.
- **OpenRouter** (paid, from their own account). Only if they chose it and have their own OpenRouter account.
  Tell them the script text goes to OpenRouter and the voice provider, and that it costs about $0.08 for a
  5-minute script. Walk them through the key (references/SETUP.md "OpenRouter voice (optional, paid)") and run
  `scripts/check-openrouter.sh`; never ask for the key in chat and never read `.env`. Then
  `python3 lib/audition.py --engine openrouter` (`Iapetus` and `Charon` on `google/gemini-3.8-flash-tts`, about
  1 cent each). Save as `"voice": {"engine": "openrouter", "model": "google/gemini-3.8-flash-tts", "name": "Iapetus",
  "budget_usd": 2}`; `budget_usd` caps this job's voice spend, and raising it needs their yes.

Save the pick in job.json and in PROMPT.md's voice slot and "Owner decisions". Never use `--engine say` for a
video: Apple licenses the macOS voices for personal, non-commercial use only (and `say` does not exist on Windows).

## Step 5: launch and supervise

Launch the builder from the studio root with `--model claude-opus-5-5`: as a NodeTerm session, or in a second
terminal window when NodeTerm is not installed or on Windows (both in references/SUPERVISING.md). Then supervise. Relay LOGIN NEEDED, OWNER DECISION NEEDED, and TOOL REQUEST messages, and relay OWNER
ACTION NEEDED at once (a take is waiting on it; when the demo must respond, only after the builder says its tested
responder is armed); present the storyboard in full at STORYBOARD READY and pass their
decision back; check the rough cut; give the final report.

## Rules that hold throughout

- The person's words in the interview outrank these defaults; write every change into PROMPT.md's "Owner
  decisions".
- Never type, read, or store passwords, one-time codes, cookies, or tokens.
- Never call a paid or remote AI service (OpenRouter, OpenAI, or any other). Everything except Claude runs on this
  computer. The one exception is the OpenRouter voice, through `lib/take.py` only, when the person picked it for this job.
- Never do tenant administration in a demo environment, except the specific changes the person allowed by name in
  the interview, each with its reset rule and logged; never touch another job's Chrome port.
- Never record, screenshot, or keep a sign-in, SSO, password, or one-time-code page. If a raw frame or screenshot
  shows one, delete the raw files (not just edit copies), log it, and ask the person to sign in again off camera.
- Opus 5.5 for every session and subagent. Do not pass a different `model` to the Agent tool.
- Keep "the video is done" separate from "the video is approved for customers". No brand, legal, SME, or human
  listening review happens here unless the person does it.

## References

- references/LOCALIZE.md: a finished job in another language, reusing its capture.

- references/INTERVIEW.md: the questions and how to ask them.
- references/SETUP.md: requirements, the local voice and Whisper, model and effort, disk.
- references/BUILDER_PROMPT_TEMPLATE.md: the builder's prompt.
- references/SUPERVISING.md: launching, watching, the storyboard checkpoint, the final report.
- references/PIPELINE.md: every toolkit command in order.
- references/LESSONS_LEARNED.md: the history behind each rule's (L7) citation; not required reading.
- references/CISCO_CLAIM_RULES.md: sourcing, wording, and branding for Cisco products.
- references/MODELS.md: Claude, the three voice engines (Kokoro with its grades, Chatterbox, OpenRouter), and Whisper.
- examples/cloud-control-se-demo/ (studio root): a finished 5-minute demo, end to end.
