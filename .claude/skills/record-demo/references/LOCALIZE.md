# A version in another language

Use this when the person wants a finished job in another language, reusing its screen capture. Tested end to end on
2026-10-27 with the Italian version of a finished English demo (3:59, Kokoro `im_nicola`; the job's `IT_NOTES.md`
has every decision). Supported narration languages: English, Italian, Spanish, French,
Brazilian Portuguese (`LANGS` in `lib/common.py`).

The original job is never changed: no file in it is written, renamed, or rendered over. Check its final video's
checksum (`md5 -q`) at the start and the end, and say both in the final report.

## 1. Check the source job and make the new one

1. Confirm the job still has its raw takes (`capture/rec/`), the edit (`build/edit.py`, `build/story.js`,
   `build/scenes.js`), the music, and a final video. Tell the person which job it is and its final length.
2. Clone it next to the original, so nothing big is copied: APFS clones take no space until a file changes.
   `cp -cR` the folders `assets build capture lib script research`, plus `audio/music`, `audio/sfx`, `job.json`,
   `INTERVIEW.md`. Do not copy `.chrome-profile` (signed-in sessions), `capture/explore` (unredacted screenshots),
   `out/`, or `audio/takes/`. Name it `<slug>-<lang>` and keep the English script as `script/speech_en.txt`.
3. A job made before 2026-10-27 has old scripts in `lib/`: copy in the language-aware ones from
   `toolkit/job-template/lib/` (`common.py`, `take.py`, `stt.py`, `speech.py`, `timeline.py`, `deliver.py`,
   `audition.py`, `spoken.py`, `player_template.html`) and keep any job-specific script the edit needs.
4. job.json: `"slug"`, `"language"` (for example `"it"`), `"title"` and `"disclosure"` in the language, `"respell"`
   emptied (it is rebuilt in step 3), `"voice"` set after the audition.

## 2. Translate and approve the talk track

- One paragraph per segment of `script/segments.json`, in the same order, so each still lines up with its part of
  the capture. Natural and professional for the audience, not word for word. Product names stay in English.
  Button, tab, and stage names stay as the screen shows them, in quotes, unless the person asks otherwise (in the
  Italian job, a button kept its English label in quotes, and a stage name was translated at the owner's request).
- Count words against the original and warn early: Italian took longer per word than English. If the original is
  near the time limit, write the translation tighter from the start.
- Show the full text for approval before any audio. Save the approved text as `script/written.txt`.
- Translate segment `chapter` names too (player chapters).

## 3. Voice audition and respellings

- Kokoro voices by language (`python3 lib/audition.py --list` in the job): Italian `im_nicola` (man) and `if_sara`
  (woman), both C; French `ff_siwis` B-; Spanish `em_alex`, `ef_dora`, `em_santa` and Portuguese `pm_alex`,
  `pf_dora`, `pm_santa` are not graded. Kokoro's speed setting moves the pace less in Italian than in English
  (0.85 lengthened the read by about 12%). In the Italian test, Nicola read about 13% slower than Sara.
- Chatterbox Multilingual (`scripts/setup-chatterbox.sh --multilingual`, 3.2 GB once): one built-in voice (an
  English speaker), about 9 to 10 times slower than real time on an M1 Pro. In the Italian test it misread
  acronyms differently each run (MCP as "MacP", "Mi IP", "MHP"; HR as "Aircome"), with or without respellings, so
  Kokoro won for a script full of product names.
- Kokoro reads English names with the language's own letter sounds, so respell them in that language's spelling
  and check the phonemes before any take (`k.tokenizer.phonemize(text, 'it')` in `toolkit/.venv`). Italian forms
  that worked: Uèbex (Webex), Mìtings, Emme Ci Pi (MCP), Contròl Hab, divèloper pòrtal, scòup, sèndbox, bìsness,
  Clòd, Ciat Gi Pi Ti, Sìsco (Cisco).
- A word that must sound English goes in the spoken text as `[en:OAuth]`: Kokoro reads that word with English
  phonemes and the captions show the plain word.
- Put each respelling in job.json `"respell"` (spoken -> written) and run `python3 lib/spoken.py`: it writes
  `script/speech.txt` from `script/written.txt` and stops if the captions would not show the approved wording.
- Make 30 s samples of the first slide's paragraph over the music (the original job's levels) in each candidate
  voice, transcribe each with Whisper in the language (`lib/stt.py` uses job.json `"language"`), and tell the
  person what Whisper heard before they listen. They choose by ear.

## 4. Fit, check, and listen

- Make a full draft take as soon as the voice is chosen and build the timeline (`build_voice.py`, `build/edit.py`):
  it gives the real length. Compare each section with the original.
- Trim in this order, showing every wording cut for approval: pauses on slides and where the capture holds still;
  wording (the outcomes and recap paragraphs give the most); last, speed-ups. Keep every footage rate at or below
  the original edit's (`python3 -B build/edit.py` in the original job prints them without writing anything), and
  rerun the cursor-jump scan.
- Kokoro pitfalls found by ear in Italian: a word that ends a phrase can run into the next ("developer.webex.com e"
  was heard as "come"; "Note, le" as "Note e le"). Fix them in the spoken text only, with a comma or semicolon
  in the respelling, and confirm with Whisper. Kokoro is deterministic, so a fixed paragraph changes nothing else.
- Cut the changed lines into short clips for the person to check, rather than asking for a full listen each time.

## 5. Slides, captions, render

- Translate every on-screen string in `build/story.js` (slides, chapter chips, footer, speed-up label in
  `build/edit.py`) and switch its cue words to words of the new narration. Longer words can overflow fixed widths:
  render stills of every slide and fix layout in the job's `build/comp.html` (the Italian recap needed a wider
  heading column). Keep the template, fonts, colours, and the end slide. Ask about legal lines: the owner kept the
  English copyright line.
- Show stills of the slides the person names, then run the normal pipeline (PIPELINE.md steps 4 to 6). Captions
  come from Whisper's word timings on the new narration with the approved wording; check that no respelling or
  `[en:` marker shows in the `.srt`. Name the output with the language, for example `<slug>_IT_final.mp4`.
