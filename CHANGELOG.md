# Changelog

What changed in each studio version, newest first. Your version is in the `VERSION` file and on the first line
that `scripts/setup.sh` prints.

## 0.5.0 (2026-10-28)

- The studio runs on Windows 10 and 11 as well as on an Apple silicon Mac. Setup checks and installs the same way;
  word timing uses faster-whisper on the CPU there, with the same Whisper model. FREE-LOCAL-CHANGES.md section 11
  has the details.
- Not on Windows yet: the Chatterbox voice and the macOS-only `say` draft voice. Use Kokoro, the default.
- New `lib/play.py` plays an audition or take on either system; auditions print it as their play command.
- Setup no longer downloads the models again on every rerun when the file size check fails, and works on company
  networks that inspect TLS.
- The test run says "on this computer" instead of "on this Mac".

## 0.4.0 (2026-10-28)

The first version of the free, local studio (this repository). FREE-LOCAL-CHANGES.md has the full comparison
with the original.

- The voice and word timing run on your Mac with free, open models (Kokoro and Whisper), so no OpenRouter
  account or key is needed. Setup downloads them once, about 2.1 GB.
- You choose the voice by ear before the build (`lib/audition.py`), and at the rough cut you listen to a short
  list of lines, because Claude cannot hear audio.
- Three voice engines: Kokoro (the default), Chatterbox (a more natural read, slower, installed only when a job
  picks it), or the paid OpenRouter voice from your own key, capped per job by `budget_usd`.
- Narration and captions in Italian, Spanish, French, and Portuguese, set by job.json "language".
- Music is a track you supply. It runs under the whole video, lowered while the SE speaks, and its own ending
  lands at the end. Paragraph joins in the voice are cut at clean silences, so word endings are no longer clipped.
- The drawn cursor no longer jumps at cuts and speed-ups, and the builder checks for jumps before the final.
- Fixed: the repo checks reported "ok" when a check could not run (for example with no working `python3`), so a
  push could pass the secret scan without being scanned.
- Fixed: a crashed chunk in the parallel render was not noticed, which could give a shorter video with no error.
  The render now stops and shows that chunk's log.
- Fixed: the OpenRouter voice cap counted a call as free when OpenRouter did not report its cost. It now asks
  OpenRouter again, and stops if the cost is still unknown.
- Fixed: building clips failed when the studio folder name has an apostrophe in it, such as "Trey's demos".

## 0.3.1 (2026-10-19)

- The builder no longer reads the lessons file on every job; each lesson is stated once, at its step.
  `LESSONS_LEARNED.md` stays as the history behind each rule.
- The starter take script says not to load a page in apps with single sign-on, where the sign-in guard would end
  the take.
- The voice edge check notes its one false alarm: a number word transcribed as digits.

## 0.3.0 (2026-10-19)

- The builder's instructions now state what earlier jobs learned at the step where it applies, instead of
  leaving 27 of those lessons in a file the builder had to read and remember.
- Typing on camera now waits 80 to 150 ms per key, as intended; it could go as fast as 52 ms, which rich text
  boxes can drop.
- Stills and renders now warn when a camera push-in aims too close to the frame edge to center there.
- Voice assembly prints the loudness step at each join between takes, next to the same spot in the main take, so
  splices are judged by a number.

## 0.2.0 (2026-10-19)

- First time? Say "do a test run": a 50-second narrated video of a public Cisco page in about 5 to 10 minutes,
  for a few cents. It proves your setup before you book a demo environment.
- Fixed: on a fresh clone, creating a job failed because the template's empty folders were missing.
- Your jobs folder is never part of the repo now; it is created the first time you make a job.
- Updates: run `git pull`. Setup shows your version on its first line and reinstalls the tools when they change
  (once after this update, about 400 MB).
- The studio is licensed under Apache 2.0; the bundled fonts keep their own open font licenses.
- The model list no longer suggests a free test voice that OpenRouter removed.

## 0.1.0 (2026-10-19)

- First release: say "help me record a demo" and Claude interviews you, researches the product from official
  sources, explores your signed-in demo in Chrome, and asks you to approve a storyboard and talk track before it
  records.
- The finished job is a narrated video with an AI voice, captions, a player page, and a report of each claim with
  its source and what it cost.
- `scripts/setup.sh` checks your Mac, installs the capture and render tools, and checks your OpenRouter key and
  its spending limit.
- AI caller: for demos that need a live phone call into the product, ChatGPT voice plays the caller, with a guided
  one-time setup the first time you use it.
- Includes a finished 5-minute Cisco Cloud Control demo in `examples/` to show what a job produces.
