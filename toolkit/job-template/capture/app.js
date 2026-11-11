// Explore the job's native app window (job.json "native"), the app-window twin of capture/tab.js.
// usage: node capture/app.js '<async JS body using app, shot(name), text(n), find(re, role), sleep(ms) and the
//                             take helpers mv, click, clickText, type, key, wheel>'
//        node capture/app.js --permissions   open the macOS requests for Screen Recording and Accessibility
//        node capture/app.js --status        only show whether the two permissions are on (asks and opens nothing)
//        node capture/app.js --list          running apps with windows (names only)
//        node capture/app.js --revoke        clean-up at the end of the job: turn both permissions back to how they
//                                            were before this job (logs/permissions.json), only after the owner's yes
// Example: node capture/app.js 'await shot("home"); return await text(3000)'
//          node capture/app.js 'return await find(/^Messaging$|^Calling$/)'     -> labels with their 1920x1080 boxes
// Every run brings the app to the front and sizes its window to 16:9 first. Screenshots are 1920x1080, in the
// same frame pixels the take scripts use, and are refused on a sign-in screen. This moves the real pointer and
// types on the real keyboard: tell the owner before a run that clicks or types. Never while a take records.
const N = require('./native'); const fs = require('fs'); const path = require('path'); const { execFileSync } = require('child_process');
(async () => {
  const a = process.argv[2] || '';
  const perms = () => JSON.parse(execFileSync(N.build(), ['check']).toString());
  const pane = k => `x-apple.systempreferences:com.apple.preference.security?Privacy_${k}`;
  // The permissions belong to the terminal app, not to this job. logs/permissions.json keeps how they were before
  // the job first asked for them, so the clean-up can put them back.
  const REC = path.join(N.JOB, 'logs', 'permissions.json');
  const TERMS = { Apple_Terminal: 'com.apple.Terminal', 'iTerm.app': 'com.googlecode.iterm2', vscode: 'com.microsoft.VSCode', ghostty: 'com.mitchellh.ghostty', WarpTerminal: 'dev.warp.Warp-Stable' };
  const terminal = process.env.__CFBundleIdentifier || TERMS[process.env.TERM_PROGRAM] || '';
  if (a === '--status') { const p = perms(); console.log(`Screen Recording: ${p.screen ? 'on' : 'off'}   Accessibility: ${p.accessibility ? 'on' : 'off'}`); process.exit(p.screen && p.accessibility ? 0 : 4); }
  if (a === '--revoke') {
    let rec = { before: { screen: false, accessibility: false } };   // no record: they were off before (the default)
    try { rec = JSON.parse(fs.readFileSync(REC, 'utf8')); } catch (e) {}
    const now = perms(), id = rec.terminal || terminal;
    const todo = [['screen', 'ScreenCapture', 'Screen Recording'], ['accessibility', 'Accessibility', 'Accessibility']].filter(([k]) => now[k] && !rec.before[k]);
    for (const [k] of [['screen'], ['accessibility']]) if (now[k] && rec.before[k]) console.log(`${k === 'screen' ? 'Screen Recording' : 'Accessibility'}: left on, it was already on before this job started`);
    if (!todo.length) { console.log('Nothing to turn off: the permissions are as they were before this job.'); process.exit(0); }
    if (!id) console.log('Could not tell which terminal app this is, so nothing was reset automatically.');
    else for (const [, svc, label] of todo) { try { execFileSync('tccutil', ['reset', svc, id], { stdio: 'ignore' }); } catch (e) { console.log(`tccutil could not reset ${label} for ${id}`); } }
    const after = perms(); const left = todo.filter(([k]) => after[k]);
    for (const [k, , label] of todo) console.log(`${label}: ${after[k] ? 'STILL ON' : 'off again'}`);
    rec.revoked = { at: new Date().toISOString(), still_on: left.map(x => x[2]) };
    try { fs.mkdirSync(path.dirname(REC), { recursive: true }); fs.writeFileSync(REC, JSON.stringify(rec, null, 1)); } catch (e) {}
    if (left.length) { for (const [, svc] of left) execFileSync('open', [pane(svc)]);
      console.log(`System Settings is open: switch the terminal app off under ${left.map(x => x[2]).join(' and ')} (or select it and click -).`); process.exit(4); }
    console.log('Done: the terminal app can no longer record the screen or control the mouse and keyboard. A later job that records a desktop app asks again.');
    process.exit(0);
  }
  if (a === '--permissions' || a === '--list') {
    if (a === '--permissions' && !fs.existsSync(REC)) {
      try { fs.mkdirSync(path.dirname(REC), { recursive: true });
        fs.writeFileSync(REC, JSON.stringify({ terminal, before: perms(), at: new Date().toISOString() }, null, 1)); } catch (e) {} }
    const out = execFileSync(N.build(), [a === '--list' ? 'list' : 'check', ...(a === '--permissions' ? ['--prompt'] : [])]).toString();
    if (a === '--list') { for (const x of JSON.parse(out).apps) console.log(`${x.app}  (${x.bundle})`); process.exit(0); }
    const p = JSON.parse(out);
    console.log(`Screen Recording: ${p.screen ? 'on' : 'OFF'}   Accessibility: ${p.accessibility ? 'on' : 'OFF'}`);
    // macOS shows a request window at most once per app, and often never for a program run from a terminal, so
    // open the System Settings page for each permission that is off
    if (!p.accessibility) execFileSync('open', [pane('Accessibility')]);
    if (!p.screen) { if (!p.accessibility) execFileSync('sleep', ['1']); execFileSync('open', [pane('ScreenCapture')]); }
    if (!p.screen || !p.accessibility) console.log('System Settings is open at the page for each permission that is OFF. Turn on the terminal app (Terminal, iTerm, ...) there; ' +
      'if it is not in the list, click + and pick it (Terminal is in Applications > Utilities). Then quit and reopen the terminal and claude, and rerun this.');
    process.exit(p.screen && p.accessibility ? 0 : 4);
  }
  const h = await N.open(); const win = await N.ready(h);
  const log = { cursor: [], marks: [] }; const D = N.driver(h, log);
  const shot = async (n, dir) => { const f = path.join(dir || path.join(N.JOB, 'capture', 'explore'), 'app_' + n + '.png');
    const r = await h.call('shot', { path: f });
    if (r.refused) { console.log(`LOGIN NEEDED: screenshot "${n}" not taken, ${win.app} looks like a sign-in screen (${r.refused})`); return null; }
    return f; };
  const fn = new Function('app', 'shot', 'text', 'find', 'sleep', 'mv', 'click', 'clickText', 'type', 'key', 'wheel', 'win', 'windows', 'place', `return (async()=>{ ${a} })()`);
  try { const r = await fn(D, shot, D.text, D.find, D.sleep, D.mv, D.click, D.clickText, D.type, D.key, D.wheel, win, D.windows, D.place);
    if (r !== undefined) console.log(typeof r === 'string' ? r : JSON.stringify(r, null, 1)); }
  catch (e) { console.log('ERR', e.message); }
  console.log('WINDOW', `${win.app} ${win.w}x${win.h} points at ${win.scale}x (${win.px.join('x')} pixels)`);
  await h.close(); process.exit(0);
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
