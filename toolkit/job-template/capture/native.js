// Record and drive a native macOS app window (for example the Webex desktop app) next to the Chrome tab.
// Settings come from job.json "native": { "app": "Webex", "size": [1440, 810], "mode": "app" }
//   app   the app's name or bundle id (Webex is "Cisco-Systems.Spark")
//   size  optional window size in points (16:9); by default the largest of 1920x1080, 1600x900, 1440x810,
//         1280x720 that fits the display the window is on
//   mode  "app" (default: all of the app's windows, cropped to the main window, so menus and pop-ups show) or
//         "window" (only the main window)
// The helper (capture/native/nativecap.swift) is compiled here on first use. Coordinates are frame pixels: the
// app window mapped to 1920x1080, the same space as Chrome takes, the edit, the camera, and redaction.
// Unlike a Chrome tab, this moves the real pointer and types on the real keyboard: hands off the mouse and
// keyboard while it runs. A click is refused if another app's window covers the point, and typing is refused
// unless the app is in front.
const { spawn, execFileSync } = require('child_process');
const crypto = require('crypto'); const fs = require('fs'); const path = require('path'); const readline = require('readline');
const JOB = path.resolve(__dirname, '..');
const CFG = JSON.parse(fs.readFileSync(path.join(JOB, 'job.json'), 'utf8'));
const NAT = CFG.native || {};
const SRC = path.join(__dirname, 'native', 'nativecap.swift');
const BIN = path.join(__dirname, 'native', '.build', 'nativecap');
const sleep = ms => new Promise(r => setTimeout(r, ms));

function build() {
  if (process.platform !== 'darwin') throw new Error('Native app capture runs on macOS only (it uses ScreenCaptureKit).');
  const hash = crypto.createHash('sha256').update(fs.readFileSync(SRC)).digest('hex');
  const stamp = BIN + '.sha256';
  if (fs.existsSync(BIN) && fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8') === hash) return BIN;
  fs.mkdirSync(path.dirname(BIN), { recursive: true });
  console.log('Building the native capture helper (once per job, about 30 seconds)...');
  try { execFileSync('swiftc', ['-O', '-swift-version', '5', '-o', BIN, SRC], { stdio: ['ignore', 'ignore', 'inherit'] }); }
  catch (e) { throw new Error('Could not build capture/native/nativecap.swift. If swiftc is missing, install the Command Line Tools: xcode-select --install'); }
  fs.writeFileSync(stamp, hash); return BIN;
}

// Start the helper for the job's app. Returns { call(op, args), close(), info }.
async function open(opts = {}) {
  const app = opts.app || NAT.app;
  if (!app) throw new Error('No app set: add "native": {"app": "Webex"} to job.json');
  const p = spawn(build(), ['serve', '--app', app, '--mode', opts.mode || NAT.mode || 'app'], { stdio: ['pipe', 'pipe', 'inherit'] });
  const waiting = new Map(); let next = 1; let dead = null;
  readline.createInterface({ input: p.stdout }).on('line', l => {
    let m; try { m = JSON.parse(l); } catch (e) { return; }
    if (!m.id) { dead = m.error || 'helper stopped'; for (const w of waiting.values()) w.reject(new Error(dead)); waiting.clear(); return; }
    const w = waiting.get(m.id); if (!w) return; waiting.delete(m.id);
    m.ok ? w.resolve(m) : w.reject(new Error(m.error));
  });
  p.on('exit', c => { dead = dead || 'native helper exited (' + c + ')'; for (const w of waiting.values()) w.reject(new Error(dead)); waiting.clear(); });
  const call = (op, args = {}) => new Promise((resolve, reject) => {
    if (dead) return reject(new Error(dead));
    if ('id' in args || 'op' in args) return reject(new Error(`helper call ${op}: "id" and "op" are reserved`));   // they would hide the reply
    const id = next++; waiting.set(id, { resolve, reject }); p.stdin.write(JSON.stringify({ id, op, ...args }) + '\n');
  });
  const close = async () => { if (!dead) { try { p.stdin.end(); } catch (e) {} } await new Promise(r => { if (p.exitCode !== null) r(); else p.on('exit', r); }); };
  await call('check');   // fails here if the app is not running
  return { call, close };
}

// Permissions, then the app in front with its window sized to 16:9. Prints what is missing and exits 4.
async function ready(h) {
  const perm = await h.call('check');
  const miss = [!perm.screen && 'Screen Recording', !perm.accessibility && 'Accessibility'].filter(Boolean);
  if (miss.length) {
    console.log(`PERMISSION NEEDED: ${miss.join(' and ')} for the terminal app that runs Claude Code (System Settings > Privacy & Security). ` +
      'Run node capture/app.js --permissions to open the requests, turn the terminal on in each list, then quit and reopen the terminal.');
    await h.close(); process.exit(4);
  }
  const size = NAT.size || [];
  return h.call('prep', size.length === 2 ? { w: size[0], h: size[1] } : {});
}

// Take helpers for the app, the same shape as rec.js has for a Chrome tab. log gets cursor and marks; every move,
// click, and key is logged for the drawn cursor and the click and key sounds.
function driver(h, log) {
  let cur = { x: 1700, y: 900 };
  const ease = k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
  const put = async (x, y) => { cur = { x, y }; await h.call('move', { x, y }); log.cursor.push({ t: Date.now() / 1000, x, y }); };
  // natural pointer move: eased quadratic curve with a small bow, then a short settle
  const mv = async (x, y, ms = 700) => { const a = { ...cur }; const dx = x - a.x, dy = y - a.y, d = Math.hypot(dx, dy);
    if (d < 2) return; const bow = (Math.random() < .5 ? -1 : 1) * Math.min(90, d * .12);
    const mx = a.x + dx / 2 - dy / d * bow, my = a.y + dy / 2 + dx / d * bow; const steps = Math.max(10, Math.round(ms / 16));
    for (let i = 1; i <= steps; i++) { const k = ease(i / steps), u = 1 - k;
      await put(u * u * a.x + 2 * u * k * mx + k * k * x, u * u * a.y + 2 * u * k * my + k * k * y); await sleep(ms / steps); }
    await sleep(60 + Math.random() * 90); };
  const press = async (opts = {}) => { log.marks.push({ t: Date.now() / 1000, k: 'click', x: cur.x, y: cur.y });
    await h.call('down', opts); await sleep(70); await h.call('up', opts); };
  const click = async (x, y, ms) => { await mv(x, y, ms); await sleep(120); await press(); };
  const dblclick = async (x, y, ms) => { await mv(x, y, ms); await sleep(120); await press({ count: 1 }); await sleep(90); await press({ count: 2 }); };
  const rightClick = async (x, y, ms) => { await mv(x, y, ms); await sleep(120); await press({ button: 'right' }); };
  // accessibility search: elements whose title, value, description, or placeholder matches, in frame pixels.
  // { anywhere: true } also searches the app's windows outside the recorded area (an incoming-call toast).
  const find = async (pattern, role, { anywhere = false } = {}) => (await h.call('find', { pattern: pattern instanceof RegExp ? pattern.source : pattern, anywhere, ...(role ? { role } : {}) })).hits;
  // click the n-th element whose label matches (role e.g. 'AXButton'); prefer this to coordinates, which break
  // when the layout shifts
  const clickText = async (pattern, { role, n = 0, ms, anywhere = false } = {}) => { const hits = await find(pattern, role, { anywhere }); const b = hits[n];
    if (!b) throw new Error(`nothing on screen matches ${pattern}${role ? ' (' + role + ')' : ''}`); await click(b.x + b.w / 2, b.y + b.h / 2, ms); return b; };
  // human typing, as in rec.js: 80 to 150 ms per key with jitter; no line breaks (use key('return'))
  const type = async (str, d = 95) => { for (const ch of str) { await h.call('type', { text: ch }); log.marks.push({ t: Date.now() / 1000, k: 'key' });
      let w = d * (.85 + Math.random() * .7); if (ch === ' ') w += Math.random() < .25 ? 140 : 30; if (/[.,?]/.test(ch)) w += 180; await sleep(w); } };
  // one key with optional modifiers: key('return'), key('k', ['cmd']), key('return', ['shift']) for a new line
  const key = async (name, mods = []) => { await h.call('key', { key: name, mods }); log.marks.push({ t: Date.now() / 1000, k: 'key' }); };
  const wheel = async (dy, steps = 30, ms = 1500) => { for (let i = 0; i < steps; i++) { await h.call('scroll', { dy: dy / steps }); await sleep(ms / steps); } };
  const mark = k => log.marks.push({ t: Date.now() / 1000, k });
  // the app's visible text from its accessibility tree (what dtext() is for a Chrome tab)
  const text = async (max = 20000, { anywhere = false } = {}) => (await h.call('text', { max, anywhere })).text;
  // wait until the text matches, polling every second; returns false after `secs`
  const waitText = async (re, secs = 60, { anywhere = false } = {}) => { for (let i = 0; i < secs; i++) { if (re.test(await text(200000, { anywhere }))) return true; await sleep(1000); } return false; };
  // the app's visible windows, front to back, in frame pixels: [{ id, title, layer, main, x, y, w, h }]. A toast
  // or a call window is its own window and can sit outside the recorded area (x or y outside 0..1920, 0..1080).
  const windows = async () => (await h.call('windows')).windows;
  // wait for a window that was not there before (an incoming-call toast, a call window); `test` filters them
  const waitWindow = async (secs = 60, test = () => true, before) => { const had = new Set((before || await windows()).map(w => w.id));
    for (let i = 0; i < secs * 2; i++) { const w = (await windows()).find(w => !had.has(w.id) && test(w)); if (w) return w; await sleep(500); } return null; };
  // move a window of the app (by id) into the recorded area: place(id) fills it (a call window), place(id, [x, y])
  // moves it there without resizing (a toast), place(id, [x, y, w, h]) both; in frame pixels
  const place = async (id, box) => h.call('place', { window: id, ...(box ? { box } : {}) });
  const home = async () => put(cur.x, cur.y);
  return { mv, click, dblclick, rightClick, clickText, find, type, key, wheel, mark, text, waitText, windows, waitWindow, place, sleep, home, cur: () => cur };
}

// For takes: why the app looks like a sign-in screen ('' if not), whether the window moved, and whether it is in front.
async function check(h) { const g = await h.call('guard'); return { signin: g.reason, moved: g.moved, front: g.front }; }

module.exports = { open, ready, driver, check, build, CFG, NAT, JOB, sleep };
