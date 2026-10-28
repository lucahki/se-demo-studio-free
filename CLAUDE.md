# Demo studio

This folder is a studio for recording narrated virtual SE product demos from a live, signed-in product.

- When someone asks to record, make, or build a demo (for example "help me record a demo"), to come up with a
  demo idea or scenario for a video, to continue a job in `jobs/`, or to make a finished job in another language,
  use the `record-demo` skill. It interviews them, sets up the job, launches the builder, and stops for their
  approval at the storyboard.
- Start sessions from this folder: the studio's agents in `.claude/agents` only register here.
- Run on Opus 5.5 at high effort (`claude-opus-5-5`, set in `.claude/settings.json`). If the session is on
  another model or effort, ask the person to run `/model claude-opus-5-5` and `/effort high` before continuing.
  Subagents and NodeTerm sessions use the same exact model id, never the `opus` alias.
- Never read `.env`, and never type or store passwords, codes, cookies, or tokens for the person. Never record
  or screenshot a sign-in page.
- Demo environments with fictional data only (dCloud, a lab, or the person's own sandbox). Never a customer's
  tenant or production system: its screens would go to Anthropic.
- This copy is the free, local mode (git branch `free-local`). The voice (Kokoro, or Chatterbox when picked) and
  word timing (Whisper) run on this Mac, music is only a track the person supplies, and Claude does the frame
  reviews itself. One exception: the narration voice may go through OpenRouter (paid) when the person explicitly
  picks it for a job and has put their own key in `.env`; only `lib/take.py` calls it. Never call OpenRouter for
  anything else, never call OpenAI or any other paid or remote AI service, and never add one during a job.
- Work for a job stays in `jobs/<slug>/`. Do not modify `toolkit/`, `examples/`, or `.claude/` during a job;
  improvements to the studio itself are a separate task the person asks for.
- Learner- and customer-facing copy: no em dashes, no slogan stacks, plain and specific.
- macOS and Windows. On Windows, commands run in Git Bash, and every `python3 ...` in these instructions is
  `python ...` there (`python3` on Windows is usually the Microsoft Store placeholder, which only prints an install
  message). The scripts in `scripts/` find Python on their own.
