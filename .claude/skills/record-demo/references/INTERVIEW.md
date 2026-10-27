# The interview

Goal: learn enough to fill every slot in BUILDER_PROMPT_TEMPLATE.md without guessing. Ask in rounds with
AskUserQuestion (up to four questions per round, a recommended option first, plain words, no jargon). Ask free-text
questions in chat when options would be artificial. Skip a question when an earlier answer already settles it.
Keep every answer in your notes as you go, quoting the person's own words where they gave them; they are written
to `jobs/<slug>/INTERVIEW.md` once the job exists (SKILL.md step 2).

Before round 1, ask in chat for one or two sentences on what they want, in their words. That sentence becomes
"The ask, in the owner's words". Do not paraphrase it.

Shortcut: when the conversation has already settled most answers, do not repeat them as rounds. Propose the story
in plain words, check it against the environment, then ask only what is still open, each question with a
recommended answer. Quote the person's words from the conversation in INTERVIEW.md and still read the summary back
for a yes.

## Round 1: what and who

1. **Product and demo environment.** Which Cisco product, and where it runs for the demo: a dCloud instant demo
   (ask for the demo name or link), a partner or Cisco lab, their own sandbox with fictional data, or a public
   site. Customer environments are not allowed: if the answer is a customer's tenant or production system, say
   so plainly and help them pick a demo environment instead. Also tell them, before the job is created, what
   leaves their Mac: Claude sees the product screens, page text, and the job's files. The voice and word timing
   run on their Mac, so the narration audio goes nowhere else, unless they pick the paid OpenRouter voice
   (question 11), which sends the script text to OpenRouter.
   If it is their own environment (a sandbox or lab they built), create the job right away and do your
   reconnaissance in the job's Chrome (SKILL.md Steps 2 and 3), so they sign in once and the facts you check land
   in INTERVIEW.md.
2. **Kind and length.** A virtual SE walkthrough (default, about 5 minutes), a short customer ad (60 to 90
   seconds), or an internal explainer. Ask whether it may run longer if the story needs it, and the hard ceiling. The template is built for the walkthrough; for an ad, also read
   `examples/cloud-control-se-demo/README.md` notes on how the 90-second ad differed (hook, reveal, more motion
   graphics, announcer-style voice).
3. **Audience.** Customers (which roles), partners, or internal SEs. What they should understand after watching,
   and what they should do next.
4. **Persona.** Default: an unnamed Cisco SE speaking to a generic customer, with a disclosure that the voice is
   AI-generated. Alternatives: a named clearly fictional SE, or a scenario built around one fictional customer.

## Round 2: story and scope

5. **Story.** Do they already have an incident, workflow, or use case in mind? If yes, get the specifics (site,
   user, alert, what should happen). If no, the builder picks the strongest story the demo data supports, and they
   approve it at the storyboard checkpoint.
6. **Must show / must avoid.** Features that must appear, and anything to keep out (unreleased features, a
   competitor, a product that is not connected in the demo).
7. **How far the demo may act.** "Look and ask" (navigate, search, ask the AI questions: safest), or "full
   control" (also run investigations, assign or resolve items, run demo workflows). Tenant administration is
   never allowed by default. If the story's strongest moment needs a configuration change, ask for that exact
   change by name (which setting, from what value to what value), when it is reset (default: after every take),
   and confirm it is logged. Allow nothing broader than what they name.
8. **Customer questions.** Which two or three questions a customer would ask during this demo ("Does this
   replace my controllers?", "Can the AI change my network on its own?", "What does this cost?"). Offer to pick
   them from the research.

## Round 3: guardrails

9. **Redaction.** Blur names, emails, and tenant identifiers (default), or none because the data is fictional
   and the video is internal. Also ask what else lives in the same environment: content belonging to other
   customers or projects, and test objects, stays off screen entirely (filter lists before they are visible, open
   records by direct link, avoid list pages). Their own identifiers count too, for example their phone number when
   it shows as a caller. Treat this answer as a starting scope: the storyboard lists the exact identifiers that will
   be visible, and they confirm the blur list against that (scope often narrows once they see it).
10. **Branding and distribution.** Internal draft (default), or intended for customers. Remind them that nothing
    here is brand, legal, or SME reviewed, and that customer-facing use is their decision after review.
11. **Voice.** Default "a calm, assured, technical demo voice, not a marketing voice". Any preference on gender,
    accent, or pace. Product names that are often mispronounced. Then which voice engine, with these trade-offs
    (default Kokoro):
    - **Kokoro**: free, on their Mac, fast (a 4-minute script in about a minute). Best voices are female
      (`af_heart` A); the best male voices only grade C+.
    - **Chatterbox**: free, on their Mac, a more natural read with one built-in voice. Slow: about 30 minutes
      per full take of a 4-minute script on an M1 Pro, and the first use downloads about 3.5 GB.
    - **OpenRouter**: paid from their own OpenRouter account (about $0.08 for a 5-minute script), and the script
      text leaves their Mac. Only for someone who already has, or wants, an account and a key.
    They pick the actual voice by ear in a short audition before the build (SKILL.md Step 4).
    Language: English by default; Italian, Spanish, French, or Brazilian Portuguese are supported (job.json
    `"language"`). In another language, Kokoro has one or two voices per language (Italian `im_nicola`, `if_sara`, grade
    C), Chatterbox needs its multilingual model (3.2 GB more), and English product names get respellings that they
    confirm by ear. A finished job in another language follows references/LOCALIZE.md instead of a new recording.
12. **Time and music.** The time limit (default 4 hours) and when they need it by. Music: none by default; if
    they want some, they supply a track they have the rights to.

## Round 4: sources (only if not obvious)

13. **Claim authority.** Official pages the claims must come from. Default: the researcher agent finds official
    Cisco docs, data sheets, and blog posts and quotes them verbatim. Ask if they have field guidance, a battle
    card, or positioning notes to include (these set positioning; they cannot authorize a technical claim the
    official sources do not support).

## Round 5: live environment (ask only what applies)

Ask this round right after round 2 when the environment is their own or the story needs something to happen live.

14. **Surfaces and identities.** Every app, console, or window the story uses; which identity signs in to each
    (check whether one covers all); which apps allow only one session at a time (sign out elsewhere first); and
    which open in a new tab.
15. **Live actions by the owner.** Recommend none unless the live event is the point of the story; a record the
    system already holds (a past call, an existing ticket) usually tells it as well and runs unattended (L2). Say
    plainly what live actions cost: they must be available within set time windows, they rehearse once with the
    builder, and they are asked "ready?" before every live take, so a cue never arrives while they are away. If
    they still want them: anything they must do in the real world during a take (place a call, send a message, tap
    a device), with the exact steps and when to do each, and what the demo must do in reply (answer, open,
    accept). The waiting is cut from the video; the screen shows something useful while it happens. The rehearsal
    comes first, so the reply is tested on the real event before they are cued for a recorded take.
16. **Time windows.** Schedules that limit when live takes can run (business hours, maintenance windows, a demo
    reservation ending), with the time zone. Everything else can run any time.
17. **Off-screen events.** Anything the screen recording cannot capture (phone audio, another device, an email
    inbox). Default: show the product's own log, trace, or history of the event instead.

## After the interview

Read the answers back in five to eight plain bullets, including the job name you will use (a short
lowercase slug such as `cloud-control-webex`), and ask for a yes before creating the job. The exception is the
person's own environment, where round 1 already created the job so they sign in once; then ask for the yes before
writing the builder prompt.

In `jobs/<slug>/INTERVIEW.md`, add "Verified facts" (what you confirmed in the environment, with where you saw it)
and "Still unverified" (what the builder's exploration must check before the storyboard).
