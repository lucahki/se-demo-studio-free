// Record one long take of a native macOS app window (job.json "native", e.g. the Webex desktop app) while a
// take script drives it like a person. The app-window twin of rec.js; to record a Chrome tab and the app in the
// same take, use rec.js with --app instead.
// usage: node capture/rec_app.js <take_name> capture/takes/<script>.js
// The take script exports: async ({ app, mv, click, dblclick, rightClick, clickText, find, type, key, wheel, mark,
//   sleep, text, waitText }) => {}      (app holds the same helpers; coordinates are 1920x1080 frame pixels)
// Output: capture/rec/<take_name>/00000.jpg ... and log.json, the same format as a Chrome take, so the edit and
// build steps treat both alike. Frames arrive only when the window changes; lib/build_clips.py resamples them.
// There is no real cursor in the capture: the pointer path is logged here and drawn in the render.
// This moves the real pointer and keyboard: the owner keeps hands off until it prints the frame count.
// Sign-in screens are never recorded: it refuses to start on one (exit 2) and deletes a take that reaches one
// (exit 3). Exit 4: a macOS permission is missing. Exit 5: the window moved, so the take's clicks are off.
const N = require('./native'); const fs = require('fs'); const path = require('path');
(async () => {
  const name = process.argv[2]; const body = require(path.resolve(process.argv[3]));
  const dir = path.join(N.JOB, 'capture', 'rec', name);
  const h = await N.open(); const win = await N.ready(h);
  const first = await N.check(h);
  if (first.signin) { console.log(`LOGIN NEEDED: take ${name} not started, ${win.app} looks like a sign-in screen (${first.signin}). Sign in off camera, then rerun.`); await h.close(); process.exit(2); }
  if (win.scale < 2) console.log(`NOTE: ${win.app}'s window is on a display at ${win.scale}x; push-ins look sharper on a Retina display`);
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const log = { source: 'app', app: win.app, window: win, frames: [], cursor: [], marks: [] };
  const D = N.driver(h, log);
  let stop = '', busy = false;
  // one check at a time: a check of a busy app can take longer than the 2 s between them, and a queue of checks
  // would delay the take's own searches (find, clickText) behind it
  const guard = async () => { if (stop || busy) return; let c; busy = true; try { c = await N.check(h); } catch (e) { return; } finally { busy = false; } if (stop) return;
    if (c.signin) { stop = 'signin';
      await h.call('stop').catch(() => {}); fs.rmSync(dir, { recursive: true, force: true });
      try { fs.appendFileSync(path.join(N.JOB, 'logs', 'state_changes.md'), `| ${new Date().toISOString()} | Deleted raw take ${name} | capture/rec/${name} | A sign-in screen appeared in ${win.app} (${c.signin}); sign-in screens are never kept |\n`); } catch (e) {}
      console.log(`LOGIN NEEDED: take ${name} stopped and its raw frames deleted, a sign-in screen appeared in ${win.app} (${c.signin}). Sign in off camera, then rerun.`);
      await h.close(); process.exit(3); }
    if (c.moved) { stop = 'moved'; console.log(`WINDOW MOVED: take ${name} stopped (${c.moved}). Rerun it; nothing else needs to change.`); }
  };
  await D.home();
  const guardTimer = setInterval(guard, 2000);
  log.t0 = Date.now() / 1000;   // recording seconds count from here (the same clock as a Chrome take)
  await h.call('start', { dir, quality: Number(process.env.JPGQ || 90) });
  D.mark('start');
  // a stopped take makes every helper throw, so the script ends at its next step
  const api = new Proxy(D, { get: (o, k) => typeof o[k] === 'function' && !['mark', 'sleep', 'cur'].includes(k)
    ? async (...a) => { if (stop) throw new Error('take stopped: ' + stop); return o[k](...a); } : o[k] });
  try { await body({ app: api, ...api }); } catch (e) { console.log('TAKE SCRIPT ERROR', e.message); }
  D.mark('end'); await N.sleep(500); clearInterval(guardTimer); await guard();
  const r = await h.call('stop'); await h.close();
  log.frames = r.frames; fs.writeFileSync(path.join(dir, 'log.json'), JSON.stringify(log));
  if (r.error) console.log('CAPTURE ERROR', r.error);
  if (r.dropped) console.log(`note: ${r.dropped} frames dropped while the disk caught up`);
  console.log(name, 'frames', r.frames.length, 'secs', ((Date.now() / 1000 - log.t0)).toFixed(1), 'window', win.px.join('x'));
  console.log('check it: python3 lib/recsheet.py', name, '5 15 30 45 60');
  process.exit(stop === 'moved' ? 5 : 0);
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
