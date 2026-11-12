# Pipeline: the toolkit, step by step

Every job folder (`jobs/<slug>/`) is a copy of `toolkit/job-template/`. Run commands from the job folder unless
a path starts with `scripts/` (studio root). Nothing calls a paid or remote service: the voice and Whisper run
on this computer, except `lib/take.py` when the owner picked a remote voice with their own key (OpenRouter, or
Gemini for the narration or a call). This order was tested end to end on 2026-09-28, with the local voice and Whisper on 2026-10-19, and on Windows on 2026-10-28.

## 0. Configure the job

`job.json`: `title`, `disclosure` (player page), `hours`, `chrome_port` (assigned by new-job.sh),
`app_url` (landing page for new tabs), `app_match` (URL fragment of the product tab), `theme` (`light`, `dark`,
or `null`), `respell` (spoken form to written form, e.g. `{"S D WAN": "SD-WAN"}`), `voice` (engine, voice, and speed, see
step 3), `dialogue` (a call between two people, see step 3), `music` (see step 5), and `native` (a desktop app window to record, empty `app` for none; see "Native app
windows" in step 1).

## 1. Browser, exploration, capture

| Step | Command |
|---|---|
| Start this job's Chrome (owner signs in) | `scripts/chrome.sh <slug>` (root); stop with `--stop` |
| Explore in your own tab | `node capture/tab.js <tag> '<async JS using page, C, shot, text, dtext, sleep>'` |
| Park a tab in a take's starting state (not recorded) | `node capture/park.js <name>` (states listed in its `PARK`) |
| Record a take | `TAG=rec node capture/rec.js <take> capture/takes/<script>.js` |
| Contact sheet of a take | `python3 lib/recsheet.py <take> 5 20 35 ...` (recording seconds) -> `review/sheet_<take>.jpg` |
| Frame at a recording time | `python3 lib/frameat.py <take> <seconds>` |

If the DevTools endpoint hangs (L12, L13): kill hung `node capture/...` processes, close runaway tabs with
`curl -s http://127.0.0.1:<port>/json/close/<id>`, and if it still does not answer (Chrome may have updated itself
while running), restart this job's Chrome with `scripts/chrome.sh <slug> --stop`, then `scripts/chrome.sh <slug>`.
The signed-in session survives a restart.

A take script (`capture/takes/example_take.js`) receives `page, C, mv, click, clickLoc, type, typed, wheel, mark,
sleep, dtext`. `mark('name')` drops a labeled timestamp into `log.json` that you can find later. Output:
`capture/rec/<take>/NNNNN.jpg` plus `log.json` (frame times, pointer track, clicks, keys). Move the pointer only
with `mv`, `click`, or `clickLoc`, never a bare `page.mouse` call or `locator.click()`, and before any wait that
will be sped up or cut, park it with `await mv(x, y)` on a neutral spot and leave it there until the result is on
screen (L66).

A link inside an embedded product page can open a new tab and break the single screen share: set `target=_self`
on the anchor before clicking (see `examples/cloud-control-se-demo/code/take_example.js`) (L17).

Canvas apps (L38, L54): start a drag pan on empty canvas (check `document.elementFromPoint(x, y)` is the
background before pressing); after a click, confirm the element you meant is the one selected; measure label
height at each app zoom step before choosing app zoom plus a push-in; the app's own search (type a name, press
Enter) is the most reliable way to bring an element on screen.

In apps with single sign-on, record in the long-lived signed-in tab (`TAG` = that tab's tag) and navigate by
in-app clicks: a `page.goto` or a brand-new tab can pass through the sign-in page and the guard ends the take
(L49). Park the tab first, and start each take script with a check instead of a navigation. Write each take's
starting state once in `PARK` in `capture/park.js`: the tab, an optional page load, in-app clicks by on-screen label,
and the address and text the start must show. `node capture/park.js <name>` gets there off camera and prints
`PARKED`, `WRONG_VIEW` (exit 1), or `LOGIN NEEDED:` (exit 2), and warns when a dialog is still open; a script that
runs several takes starts a take only after `PARKED`. The take checks the same entry:
`const { atStart } = require('../park'); if (!(await atStart(page, '<name>'))) { mark('wrong_view'); return; }`.
Parking helps in any app whose takes need a prepared view, not only with single sign-on.

Sign-in guard (L47; in jobs whose `capture/cdp.js` has `signInReason`): `rec.js` exits with code 2 and records
nothing if the page looks like a sign-in, SSO, password, or one-time-code page. It checks the address (common
sign-in and identity-provider patterns), a visible password or code field, a page whose only input asks for a
username or email, and a sign-in or verification page title. It can still miss an unusual sign-in page, so check
every take's contact sheet. If one appears mid-take it stops,
deletes that take's raw frames, adds a row to `logs/state_changes.md`, prints "LOGIN NEEDED:", and exits with code
3. `shot()` returns null instead of saving such a page. `SIGNIN_GUARD=off` is only for an owner-approved page with a
masked secret field that is not a sign-in.

Waiting for an owner action inside a take (L39). Print the marker before the take reaches this point, then:

```js
mark('owner_wait');
for (let t = 0; t < 300; t += 2) { if (/TEXT THAT PROVES IT HAPPENED/.test(await dtext(6000))) break; await sleep(2000); }
mark('owner_done');
```

Cut the span between the two marks out of the edit; the result shot starts at the first frame where the result
is listed, and the time in between shows something that follows the narration (L50). If the page needs a refresh
to show the result, refresh every 15 seconds or more and record at `JPGQ=75` (L32).

When the demo must respond to the action (L48), use the locator that matched the real event in the rehearsal
(role and name, a `page.frameLocator(...)` chain, or whatever the rehearsal proved; Playwright locators reach open
shadow DOM, plain `innerText` searches do not):

```js
const target = page.getByRole('button', { name: 'LABEL SEEN IN THE REHEARSAL' }).first();
mark('owner_wait');
for (let t = 0; t < 300; t++) {
  if (await target.isVisible().catch(() => false)) {
    await clickLoc(target); await sleep(3000);
    if (!(await target.isVisible().catch(() => false))) break;   // responded; also check the result you expect
    console.log('OWNER ACTION NEEDED: responder could not respond; tell the owner what to do now');
    throw new Error('responder failed');
  }
  await sleep(1000);
}
mark('owner_done');
```

### Native app windows (macOS and Windows)

A story can also show a desktop app, such as the Webex app, next to or instead of the Chrome tab. Set job.json
`"native": {"app": "Webex"}` (the app's name or bundle id; Webex is `Cisco-Systems.Spark`; on Windows its name,
program file, or window title, and "Webex" works on both). Optional: `"size":
[1440, 810]` (window size in points, 16:9; by default the largest of 1920x1080, 1600x900, 1440x810, 1280x720,
1120x630 that fits its display), `"mode": "window"` (only the main window; the default `"app"` captures all of the
app's windows cropped to the main window, so its menus, pop-ups, and call windows show and other apps do not),
and `"anchor": "bottom-right"` (the window goes in the bottom-right corner of the display's free area instead of
the center; use it when the story shows an incoming Webex call, so the call toast opens inside the recorded area
where Webex puts it and the take answers it there without moving it). Windows only: `"title": "<pattern>"` picks
the main window by its title when the app has several large windows open (otherwise the largest one is used;
closing the others is simpler).

| Step | Command |
|---|---|
| Request the two macOS permissions | `node capture/app.js --permissions`: opens the requests and the System Settings pages (exit 4 while one is missing); on Windows it says there are none and exits 0 |
| Only check them | `node capture/app.js --status` (asks and opens nothing; use it to confirm, for example after `--revoke`) |
| Running apps with a window | `node capture/app.js --list` |
| Clean-up at the end of the job (the default; also when it stops early) | `node capture/app.js --revoke`: the permissions back to how they were the first time this job touched the app (`logs/permissions.json`); after the owner's explicit "no", `node capture/app.js --keep` records that they stay on |
| Earlier jobs whose clean-up never ran | `scripts/pending-cleanup.sh` from the studio root (SKILL.md Step 0 item 4) |
| Explore the app | `node capture/app.js '<async JS using app, shot, text, find, sleep, mv, click, clickText, type, key, wheel>'` |
| Record an app-only take | `node capture/rec_app.js <take> capture/takes/<script>.js` |
| Record the Chrome tab and the app together | `TAG=rec node capture/rec.js <take> capture/takes/<script>.js --app` -> `capture/rec/<take>/` and `capture/rec/<take>_app/` |

How it differs from a Chrome tab:

- It needs Screen Recording and Accessibility for the terminal app that runs Claude Code (references/SETUP.md
  "Native app capture"). The helper `capture/native/nativecap.swift` is compiled on first use (about 30 s).
- Every run first brings the app to the front and sizes its main window to 16:9, centered on its display (or
  bottom-right with `"anchor"`).
  Coordinates are frame pixels: the window mapped to 1920x1080, the same space as Chrome takes, `shot()`
  pictures (1920x1080), the camera, and REDACT. Put the window on a Retina display; at 1x a push-in looks soft
  (rec_app.js prints a NOTE).
- It moves the real pointer and types on the real keyboard. Tell the owner before every run that clicks or
  types, and ask them to keep hands off the mouse and keyboard until it prints the frame count. A click or scroll
  is refused when another app's window covers the point, and typing is refused unless the app is in front, so a
  take stops rather than click, scroll, or type into another app. Turn on Do Not Disturb (macOS Focus) for the takes: other apps'
  notifications are not recorded in `"app"` mode, but a banner over the app blocks clicks under it.
- There is no DOM. `text()` returns the app's visible text from its accessibility tree (the twin of `dtext()`),
  `find(/label/, role)` returns matching elements with their 1920x1080 boxes, and `clickText(/label/, { role })`
  clicks one. Prefer `clickText` to coordinates, as with on-screen labels in Chrome. Check what the tree exposes
  first (`node capture/app.js 'return await find(/./)'`); where it lacks a label, use coordinates from a `shot()`.
- `type()` takes no line breaks. Press keys with `key('return')`, `key('return', ['shift'])` (a new line in a
  chat box), or `key('k', ['cmd'])`. In a chat app, Return sends: read the box back with
  `(await text()).includes(...)` before pressing it, as `typed()` does in Chrome.
- `wheel(dy)` scrolls like Chrome's (positive is down), in frame pixels.
- No page loads: put the app in each take's starting state off camera with `node capture/app.js` (in-app clicks),
  and start the take script with a check, e.g.
  `if (!/Messaging/.test(await text())) { mark('wrong_view'); return; }`.
- The sign-in guard reads the accessibility tree: a sign-in address in an embedded web view, a password field, an
  email-first step, or a sign-in window title or heading stops the take as in Chrome (exit 2 before, exit 3 with the
  raw frames deleted during). Without the Accessibility permission it cannot check, so it refuses to start. Exit 5
  (rec_app.js and rec.js --app) means the window moved or changed size mid-take: rerun it. Exit 1 with CAPTURE
  ERROR (APP CAPTURE ERROR in rec.js) means the app recording stopped on its own and the clip is cut short: rerun it.
- The app must be signed in with a demo identity (a dCloud or lab user, a sandbox org), never the owner's everyday
  account: its spaces, contacts, and messages would be recorded and sent to Anthropic in frame reviews.

On Windows (the helper is `capture/native/nativecap.cs`, built on first use with the C# compiler that comes with
Windows, about 10 s; same commands, same take helpers, same log), the differences are:

- No permissions: nothing to request, check, or clean up at the end of the job.
- The recording is the screen area under the app's window. Another app's window or a notification over that area
  would be recorded, so the take refuses to start (exit 2) or stops and deletes its raw frames (exit 3), printing
  `COVERED:` with that app's program name; `shot()` refuses too. Close or move that window and rerun. Turn on Do
  Not Disturb (Settings, System, Notifications) before the takes. `"mode": "window"` records only the main window
  (slower, and without the app's pop-ups); it is not stopped by other windows.
- `size` is in points, as on a Mac: on a display at 150% the window is 1.5 times as many pixels. At 100% the clip
  is at most 1920x1080 pixels and rec_app.js prints a NOTE; push-ins are sharper on a display at 150% or more.
- `key()` modifiers are `ctrl`, `shift`, `alt`, `win`; `cmd` means Ctrl, so a take written on a Mac
  (`key('k', ['cmd'])`) runs as it is, but check the app's Windows shortcuts.
- Roles: UI Automation control types come back under their macOS names (`Button` as `AXButton`, `Edit` as
  `AXTextField`, `Text` as `AXStaticText`, `ListItem` as `AXRow`, `Document` as `AXWebArea`), with the Windows name
  in `uia`; `find()` and `clickText()` take either. Only elements inside the recorded area are read (or inside
  each window with `{ anywhere: true }`), which keeps a walk of the Webex app near two seconds.
- `wheel()` is about 100 screen pixels per notch; the app decides how far that scrolls, so check it in a rehearsal.
- The app must not run as administrator (Windows blocks the pointer and keyboard; the studio stops and says so).
- The Webex app on Windows is Qt with embedded Chrome views (its message list); both show in the tree. Its left
  rail items are Qt custom controls (`AXUnknown`, `uia` `Custom`) labeled like `Calling menu item, 3 of 12`:
  click them by label without a role, `clickText(/^Calling menu item/)`. A walk of its window took under a second.

Pop-ups such as an incoming-call toast and a call window are windows of their own, and can open outside the
recorded area or on another display. `windows()` lists the app's windows in frame pixels (the main window is
`main: true`; anything outside 0..1920 by 0..1080 is off camera), `waitWindow(secs, test)` waits for a new one,
`place(id)` moves a window over the recorded area and sizes it to fill it, and `place(id, [x, y])` moves it without
resizing. `find`, `clickText`, `text`, and `waitText` take `{ anywhere: true }` to look outside the recorded area.

Incoming call recipe (tested on the Webex app, 2026-11-11, with a call placed from outside):

```js
const answerBtn = async () => (await find(/\b(answer|accept)\b/i, 'AXButton', { anywhere: true }))[0];
const endBtn = async () => (await find(/^end call$/i, 'AXButton', { anywhere: true }))[0];
await mv(1300, 600, 900);                 // the pointer on the app window: Webex opens the toast on that display
console.log('OWNER ACTION NEEDED: place the call now');
mark('owner_wait'); let a; while (!(a = await answerBtn())) await sleep(700); mark('ringing');
const inside = (b, w) => b.x >= w.x && b.y >= w.y && b.x + b.w <= w.x + w.w && b.y + b.h <= w.y + w.h;
const toast = (await windows()).find(w => !w.main && inside(a, w));
if (toast) await place(toast.id, [1920 - toast.w - 40, 90]);            // fully in view, top right (skip with "anchor")
await sleep(2500); a = (await answerBtn()) || a; await click(a.x + a.w / 2, a.y + a.h / 2, 900); mark('answered');
let e; while (!(e = await endBtn())) await sleep(1000); mark('connected');
const call = (await windows()).find(w => !w.main && w.w > 300 && inside(e, w));
if (call) await place(call.id);           // the call window over the recorded area, filling it
```

To show the toast where Webex opens it, bottom right of the display, instead of moving it: set job.json
`"native": {"anchor": "bottom-right", ...}`, leave out the `place(toast...)` line, and stop with OWNER DECISION
NEEDED if the toast or its answer button is outside 0..1920 by 0..1080 (tested on the Webex app, 2026-11-12: the
toast opened inside the frame at bottom right and was answered there).

On Windows the recipe has not yet been run against a live call: in a rehearsal, check where the toast opens,
whether it is a window of its own in `windows()`, and whether `"anchor": "bottom-right"` puts it inside the
recorded area, before the first take.

What the test showed: the toast opens on the display where the pointer is, and `place` cannot move it to another
display, so keep the pointer on the app window while waiting (hands off). If `a` is outside 0..1920 by 0..1080
after `place`, the click still answers but the ringing is off camera: print a warning and retake. With a device
paired (a desk video device), the button reads "Answer on my computer" and the call took about 40 s to connect; with no
device it connected in 2 s. First-time tips (such as "Real-time closed captions" with "Got it") are windows of
their own that stay where they opened: dismiss them in a rehearsal call. The toast also answers to Control+Shift+C
(`key('c', ['ctrl', 'shift'])`), a fallback when its button has no label.

A take script for `rec_app.js` receives `app` and the same helpers spread out (`mv, click, dblclick, rightClick,
clickText, find, type, key, wheel, mark, sleep, text, waitText, windows, waitWindow, place`). With `rec.js --app` it receives the page
helpers as usual plus `app` with the app's own (`app.click(...)`, `app.text()`); the page pointer is virtual and
the app pointer real, and each clip logs its own cursor.

Both clips of a `rec.js --app` take share one clock (log.json `t0`): the same recording second is the same
moment in both, so a cut from the Chrome clip to the app clip at matching keys shows one moment from two screens.
In `build/edit.py`, read marks with `rec_marks('<take>')` (from `common`), which counts from `t0` when the log has
one; `L['frames'][0]['t']` is only right for Chrome-only takes. Over an app clip the frame bar shows the app's name
instead of an address (`appLabel` in `build/story.js` frame to change it).

## 2. Talk track

- `script/speech.txt`: the exact text for the voice model, one paragraph per segment, blank line between.
  Respellings go here ("S D WAN"), never in style instructions.
- Many respellings, or a language other than English: write the approved text in `script/written.txt`, the
  respellings in job.json `"respell"` (spoken -> written), and run `python3 lib/spoken.py`; it writes
  `script/speech.txt` and stops if the captions would not show the approved wording. `[en:word]` in the spoken text
  reads one word with English pronunciation (Kokoro). Versions in another language: references/LOCALIZE.md.
- `script/segments.json`: one entry per paragraph, same order: `name` (used in the edit), `gap` (seconds of
  silence after it, room for typing, loading, reading), `chapter` (player chapter label). Also `intro_seconds`
  (silence before the first word, under the title) and `tail_seconds` (after the last word). A segment with
  `"call": "<name>"` is followed by that call (step 3, "Calls"), then `call_gap` seconds (default 0.8).
- `script/calls/<name>.txt` (only with a conversation on screen): one turn per line, `Anna: ...` /
  `Paolo: ...`, plus an optional first line `style: a relaxed phone call between two colleagues`
  (format in `lib/dialogue.py`; `**Anna:**` from a meeting script also works). Amounts in words.

## 3. Voice

| Step | Command |
|---|---|
| Narration language | job.json `"language"` (`en` default; `it`, `es`, `fr`, `pt`). take.py, audition.py, stt.py, captions, and the player follow it |
| Install Chatterbox (once, only if picked) | `scripts/setup-chatterbox.sh` (root; about 3.5 GB); add `--multilingual` for another language (3.2 GB more) |
| Check the OpenRouter key (only if picked) | `scripts/check-openrouter.sh` (root; prints usage and limit, never the key) |
| Check the Gemini key (only if picked) | `scripts/check-gemini.sh [--library it-IT]` (root; free requests only: prints ok, the speech models, and the custom voices of the key's project with their IDs, never the key; `--library` also lists Google's Extended Voice Library for a language) |
| Kokoro voices and grades | `python3 lib/audition.py --list` (the job's language) |
| Audition (the owner picks by ear) | Kokoro: `python3 lib/audition.py [voice ...] [--text FILE] [--speed 1.0]`, then `python3 lib/play.py audio/audition/A_<voice>.wav`. Chatterbox: `python3 lib/audition.py --engine chatterbox [--speed 0.94]`. OpenRouter (paid): `python3 lib/audition.py --engine openrouter [Iapetus Charon ...]`. Gemini: `python3 lib/audition.py --engine gemini [Iapetus Charon ...] [--style S]`. A call: `python3 lib/audition.py --call [--engine kokoro\|gemini] [Kore+Puck ...] [--text FILE] [--phone Paolo\|none]`. Each prints its play commands |
| Full take | `python3 lib/take.py T1` (engine, voice, and speed from job.json), or override: `python3 lib/take.py T2 af_heart --speed 0.95` |
| Redo some paragraphs | put just those paragraphs in a file and `python3 lib/take.py T3 --text FILE`; `check_take.py T3` then lists the other paragraphs as unaligned, which is expected; join with `build_voice.py T1 segment=T3` |
| Word timestamps | `python3 lib/stt.py audio/takes/T1.wav` (local Whisper large-v3-turbo, in the job's language; `--language it` overrides) |
| Wording check vs script | `python3 lib/check_take.py T1 [T2 ...]` |
| Voice joins | `python3 lib/join_scan.py` after build_voice: every paragraph must start and end in silence or a fade (below -50 dB), with nothing in the gaps. build_voice cuts each paragraph at the take's own 0.7 s silences, so its natural decay is kept (a word-based cut clipped word endings on 2026-10-20); OpenRouter takes have no such silences and keep word-based cuts |
| Assemble narration | `python3 lib/build_voice.py T1 [segment=T2 ...]` -> `audio/voice.wav`, `build/cues.json`; it ends with an edge check, and any `EDGE MISMATCH` means a paragraph lost its first or last word (L55), except when a number word was transcribed as digits ("three" as "3"): check those by ear. Decide a join by its `JOIN` numbers (L56). Missing or misread words show in `check_take.py`; pronunciation and artifacts are for the owner's listen (`review/LISTEN.md`) |

job.json `"voice"` by engine (a job without `"engine"` is Kokoro):

| Engine | Fields (defaults) | Notes |
|---|---|---|
| `kokoro` | `name` (`am_michael`), `speed` (1.0) | Free, on this computer, about 4 times faster than real time (Apple silicon or a Windows laptop CPU). No style field, only speed (0.5 to 2.0; 0.9 to 1.1 sounds natural). The same text and settings give a byte-identical take: to change a read, change the words, punctuation, or speed. |
| `chatterbox` | `name` (`builtin`, or a reference clip's path in the job folder), `speed` (0.94), `seed` (1), `exaggeration` (0.5), `cfg_weight` (0.5) | Free, on a Mac (Mac GPU), about 7 times slower than real time on an M1 Pro. Not set up for Windows yet. Speed is a pitch-preserving stretch after the read. Lower `cfg_weight` (0.3) slows the pacing; higher `exaggeration` is more expressive but faster. Reads vary run to run even with the same seed. Paragraphs over 90 words are read in parts split at sentence ends (it stops after about 40 s per call). Every take carries an inaudible Perth watermark. |
| `gemini` | `model` (`gemini-3.8-flash-tts`), `name` (`Iapetus`, any of the 30 built-in voices, or a custom voice ID `voice_...` from the key's Google project), `style` (`""`), `speed` (1.0), `budget_usd` (2) | The owner's Google AI Studio key in the studio `.env` (free tier, or paid); the whole text in one call (about $0.07 for 5 minutes at paid-tier prices, logged at that price in `logs/costs.jsonl` even on the free tier, stopped at `budget_usd`). `style` is a short delivery note sent apart from the text ("calm and assured"); keep it short, long ones make the voice drift. Speed is a stretch after the read. |
| `openrouter` | `model` (`google/gemini-3.8-flash-tts`), `name` (`Iapetus`), `speed` (1.0), `budget_usd` (2) | Paid, from the owner's key in the studio `.env`; the whole text goes in one call (about $0.08 for 5 minutes), logged in `logs/costs.jsonl` and stopped at `budget_usd`. `Charon` suits ads better. Speed is a stretch after the read. |

Kokoro, Chatterbox, and `say` read each paragraph on their own and join them with `--gap` seconds of silence
(default 0.7), so cuts land in clean gaps; OpenRouter and Gemini read the text in one call and the cuts use their own pauses.

### Calls (a conversation between two people)

| Step | Command |
|---|---|
| Record a call | `python3 lib/take.py <name> --dialogue script/calls/<name>.txt` -> `audio/calls/<name>.wav` (with the phone filter), `<name>_raw.wav` (as read), `<name>_lines.json` (each line's speaker, text, and timing), `<name>.log`. It prints any wording difference per line (numbers written as digits by Whisper are not errors). Together: rerun to redo the whole call. Per line: a rerun asks Google again only for lines whose text or settings changed, or those named with `--redo 3,7`; the others stay exactly as approved. A word the voice misreads (it said "UVA" for "IVA") is written as said ("iva") with a job.json `"respell"` pair (`{"più iva": "più IVA"}`) so the captions show the written form |
| Phone filter on any file | `python3 lib/phone.py IN.wav OUT.wav` (8 kHz, 400 to 3000 Hz, +4 dB at 1800 Hz, hard compression, light bit crush) |
| Place it | `"call": "<name>"` on the segment it follows in `script/segments.json`, then `build_voice.py`: the narration has a silent hole for it, `cues.json` "calls" has its place and lines, `mix.py` plays it as its own layer (as loud as the narration, plus `level_db`), with the music ducked, and `deliver.py` captions each turn with the speaker's name. In `build/edit.py`, `CS('<name>')` / `CE('<name>')` (from `timeline`) give its start and end |

job.json `"dialogue"`:

| Field (default) | Meaning |
|---|---|
| `engine` (`kokoro`) | `kokoro`: free, on this computer, each line read with its speaker's Kokoro voice, `gap` (0.35) seconds apart; or `gemini`, only when the owner picked it for this job (the call text goes to Google) |
| `mode` (`auto`) | Gemini only. `together`: the whole call in one request, the two voices reacting to each other (at most two speakers; Google allows only its 30 built-in voices there). `per_line`: one request per line, `gap` (0.35) seconds apart, which lets a custom voice ID speak, without the reactions. `auto`: together when every voice is built in, else per_line |
| `model` (`gemini-3.8-flash-tts`) | Gemini only |
| `speakers` | speaker name, as written in the call file -> voice: a Gemini voice (`"Charon"`, or a custom `"voice_..."`), or a Kokoro voice (`"im_nicola"`, or `{"name": "im_nicola", "speed": 1.1}`) |
| `style` (`""`) | Gemini only: one short tone for the whole call, unless the call file has a `style:` line |
| `phone` (`[]`) | the speakers who sound as if on the phone, only on their own lines (a list, or one name; a name that is not a speaker in the call stops with a message) |
| `speed` (1.0) | Gemini only: a pitch-preserving stretch of the whole call |
| `level_db` (0) | the call's loudness against the narration in the mix |
| `budget_usd` (2) | Gemini only: stops when the job's total remote voice spend would pass it |
`--engine say` (macOS voices, Mac only) is for drafts only: Apple licenses those voices for personal, non-commercial use.

## 4. Picture

| Step | Command |
|---|---|
| Map takes to narration time | edit `build/edit.py` (CLIPS, RAMPS, SHOTS) using `S()`, `E()`, `W()` |
| Build 30 fps clips | `python3 lib/build_clips.py` -> `assets/clips/<clip>/`, `build/footage.json` |
| Blur redaction regions | `python3 lib/redact.py [clip ...]` (regions in `build/edit.py` REDACT; rerun after every `build_clips.py`, which rebuilds clips from the raw frames) |
| Add cursor, clicks, keys | `python3 lib/cursor_tracks.py` -> `build/footage.js`, `build/cues.js` |
| Words and camera | edit `build/story.js` (title, agenda, frame shots/urls/chapters/camera, value, close) |
| Check frames | `node build/render.js stills review/stills 3 42.5 118` then look at them (`python3 lib/grid.py`) |

At every cut, look at the incoming clip's first frames (`python3 lib/frameat.py <take> <seconds>`); if a spinner or
"Loading" is still up, move that clip's first key later, to where the screencast stops sending frames (L21).

Rerun `lib/cursor_tracks.py` after any change to cues or clips; the page reads `footage.js` and `cues.js`.

The drawn cursor must never jump (L66). `lib/cursor_tracks.py` ends by walking the timeline frame by frame
through `SHOTS` and prints:
- `CURSOR JUMP <time>`: the cursor moves more than 150 capture pixels in one frame inside a shot, usually a
  speed-up over a moving cursor or a cut inside a take. Park the cursor before that wait and re-record, or move
  the ramp's keys so it covers only frames where the cursor is still.
- `CURSOR CUT <time>`: the cursor lands more than 40 pixels away at a change of shot. Add `[time, time]` to
  `cursorOff` in `build/story.js` (the cursor fades out over 0.25 s before and back in over 0.25 s after), or
  cover the cut with a short push-in.

It works in capture pixels from the footage tracks, so it does not see fades or push-ins: render stills either
side of each listed time and look at them. "cursor check: no jumps" is the clean result.

Treat these printed warnings as errors (L57): `WARNING <clip>: key ... dropped` (a cue word matched too early),
`WARNING shots: ... gap` and `WARNING shots: ... holds still` (from `build_clips.py`). A RAMPS label names what was
compressed ("about 80 seconds of waiting"); a duration stated as fact comes from the system's timestamps (L51).

Key camera moves near a click to that take's recorded click times (`FOOT.<take>.clicks`, readable in `build/story.js`,
in timeline seconds), not to word times: word-keyed moves drift onto the wrong click when a take is re-recorded (L28).

## 5. Sound and mix

| Step | Command |
|---|---|
| Click and key sounds | `python3 lib/sfx.py` (once) |
| Sound cue sheet | `python3 lib/sfx_events.py` |
| Music (optional, off by default) | No generator. Put a track the owner has the rights to in `audio/music/` and set job.json `music` |
| Music bed (run by mix.py when needed) | `python3 lib/music_bed.py` -> `audio/music/bed.wav`, `bed.json`: the track fitted to the video so its own ending lands at the end (no jump, one skip forward, or one or two bar-aligned jumps back, crossfaded over a bar). It stops with a message when a track cannot be fitted |
| Mix and master | `python3 lib/mix.py out/mix.wav` (-16 LUFS, -1.5 dBTP); prints and saves `build/mix_levels.json` (voice-to-music difference under speech, between phrases, in the intro). `--from S --to S` renders an excerpt, e.g. a 30 s sample |

job.json `music` (defaults): `{"file": "", "level_db": -20, "duck_db": -6, "intro_boost_db": 11}`. An empty `file`
means no music. With a track, the music runs under the whole video: `level_db` sets the bed against the voice's
measured loudness, `duck_db` lowers it further while the SE speaks (held through pauses under 1.2 s, so it does not
pump), `intro_boost_db` makes it louder while it plays alone before the first word and eases it down over 0.8 s just
before it, and it fades out after the last word (`end_slide_seconds` to set the fade). For a music lead-in, set
`script/segments.json` `intro_seconds` so the first word lands on `bed.json` `beat_near_3s` (on a beat; check
`build/cues.json` `words[0].t` after build_voice). Measured on the 2026-10-20 demo, approved by ear: music 26 dB under the
voice under speech, 20 dB between phrases, 12.6 dB in the intro.

## 6. Render and deliver

| Step | Command |
|---|---|
| Full render with audio | `build/render_par.sh out/<slug>_v1.mp4 8 out/mix.wav` (prints any page errors) |
| Captions and player | `python3 lib/deliver.py <slug>_v1.mp4` -> `out/*.srt`, `out/*.vtt`, `player.html` |

## Review helpers

- Frame review by Claude: render stills (`node build/render.js stills ...`), make contact sheets with
  `lib/grid.py`, and read the images directly. For the second round, give a fresh general-purpose subagent only
  the review package and the questions, not the script-writing history.
- `lib/grid.py out.jpg 3 files...`: contact sheet of any images.
- The `claim-checker` agent: checks the talk track and on-screen text against `research/SOURCES.md`.

## Tested

A smoke job on 2026-09-28 ran every step above against a public page with a free voice model: capture, take,
alignment, voice assembly, clips, cursor, sound effects, mix, stills, an 8-chunk render (39.7 s, 1920x1080, 30
fps, AAC audio), captions, and the player.

The free, local mode was tested with the test run on 2026-10-19 on an Apple Silicon Mac: Kokoro `am_michael`
read the 5-paragraph script (44.6 s of speech) in 11 s, local Whisper timed all 119 words in 7 s with no
wording differences, `build_voice.py` ended with `edge check: ok`, and the 55.4 s render, captions, and player
completed with no music. Voice and word timing ran from the files in `toolkit/models`.

Windows was tested with the same test run on 2026-10-28 on a Windows 11 laptop (Intel Core i7-13800H, CPU only):
Kokoro read the 44.6 s script in 12 s, faster-whisper timed all 119 words in 26 s with no wording differences,
`edge check: ok`, and the 8-chunk render of the 55 s video took 97 s.
