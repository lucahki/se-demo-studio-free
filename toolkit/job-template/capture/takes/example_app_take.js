// Example take for a desktop app window: node capture/rec_app.js take1 capture/takes/example_app_take.js
// The app was put in its starting state off camera with capture/app.js; the take checks it instead of navigating.
// Coordinates are 1920x1080 frame pixels (read them off a shot() from capture/app.js); labels are steadier.
// Return sends in a chat box: read the box back before pressing it. See references/PIPELINE.md "Native app windows".
// To record the Chrome tab at the same moment, run it with rec.js --app and use app.click, app.type, ... for the app.
module.exports = async ({ mv, click, clickText, type, key, mark, sleep, text, waitText }) => {
  if (!/Messaging/.test(await text())) { mark('wrong_view'); return; }
  await sleep(2000); mark('ready');                    // a still stretch to cut in on
  await mv(960, 500, 900); await sleep(1200);          // the SE's pointer drifts toward what they are describing
  // await clickText(/^Search/, { role: 'AXTextField' }); await type('Design review');
  // await key('return'); mark('searched');
  // if (!(await waitText(/Design review/, 20))) { mark('no_result'); return; }
  // const msg = 'The draft is ready for review.';
  // await click(900, 1000); await type(msg);
  // if ((await text()).includes(msg)) await key('return');
  // mark('sent'); await sleep(3000);
  await sleep(1500);
};
