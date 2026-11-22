# Overview

Tollgate is a governed agentic workflow system. Human in the loop at every approval checkpoint.

---

## The Problem

Claude without structure is a general assistant. Every session starts cold. Outputs are inconsistent. Context disappears at the end of the conversation. You spend the first ten minutes of every ticket recapping what you already know, and the output still drifts based on how the question was phrased.

This system solves that. It turns Claude into a structured thinking partner with a defined role, consistent standards, and a memory that persists across sessions.

---

## What This System Does

It gives Claude three things it does not have by default:

**A role for each phase of work.** Each skill file is a department head with a specific job and a defined handoff. `/tg-ticket` is the intake coordinator. `/tg-spec` is the product manager. `/tg-arch` is the architect. `/tg-dev` is the engineer. `/tg-qa` is the adversary. You do not ask the architect to write code or the engineer to set requirements. Each skill does its job and stops.

**State that carries forward.** A ticket state file at `02-tickets/{KEY}/{KEY}-state.md` holds everything the next skill needs to start. When `/tg-dev` reads the state file, it knows the root cause, the approved design, and the open assumptions. It does not ask you to recap. A session can end and pick up the next day without losing a single decision. The gate and the commands also find `02-tickets/PREFIX/KEY/` (prefix matched without case).

**Standards that apply everywhere.** Three documents govern every word and every line of code Claude produces: a voice standard, a technical standard, and a pipeline standard. The five chain skills (`/tg-support`, `/tg-spec`, `/tg-arch`, `/tg-dev`, `/tg-qa`) read all three at Step 0; a few other commands read the voice standard only. The voice standard applies to a Jira comment the same way it applies to a design document.

---

## What It Is Not

It does not run autonomously. No skill starts without you invoking it. Nothing posts to Jira or sends a Slack message, and no command commits your vault: it prints the git lines and you run them. Code commits happen only on a feature branch during `/tg-dev`, and a hook asks you first. Every output is a draft. You send.

It does not replace your judgment. The skills produce orientation, structure, and drafts. You approve designs. You confirm root causes. You send communications. The gates in each skill are where your judgment replaces Claude's output.

It is not a shortcut for small tasks. The chain takes more steps than ad hoc use. The payoff is on complex tickets that span multiple sessions, where the state file and the vault let any session pick up exactly where the last one left off.

---

## The Skill Chain at a Glance

Most tickets follow one of these patterns. Every command starts with the fixed prefix `tg-`:

**Coordination** (investigation, decision, or status update with no code change):
```
/tg-start → /tg-ticket [ID] → /tg-close
```

**Bug** (wrong data, trace root cause from source to output):
```
/tg-start → /tg-ticket [ID] → /tg-support [ID] → /tg-spec [ID] → /tg-arch [ID] → [approve] → /tg-dev [ID] → /tg-qa [ID] → /tg-close
```

**Build** (new feature or new pipeline):
```
/tg-start → /tg-ticket [ID] → /tg-spec [ID] → /tg-arch [ID] → [approve] → /tg-dev [ID] → /tg-qa [ID] → /tg-close
```

See [Walkthrough](walkthrough.md) for a complete bug ticket worked from a Slack message to a merged fix with client communication.

---

## The Session Frame

Every work block has the same bookends.

`/tg-start` opens the session. It checks your environment, checks vault health, flags blockers, recaps yesterday, and tells you what to work on. You see the full picture before you pick up anything.

`/tg-close` ends the session. It writes a session log to the vault, updates the ticket state file, and surfaces any corrections or decisions as memory candidates. Nothing is left floating.

Between those bookends, you invoke skills as the work requires. The chain does not run itself.

---

## The Standards

Three documents govern all output. The five chain skills read all three at Step 0; a few other commands read the voice standard only.

**`standards/voice-standard.md`**: how Claude writes. Conclusion first. Bracket test (remove any word that loses nothing if cut). Active voice. No intensifiers. No template filler. These rules apply to a Jira comment and a system design document equally.

**`standards/technical-standards.md`**: how Claude codes. Type hints on every function. Functions at 40 lines or fewer. No magic numbers. No secrets in code. Explicit write modes and null handling. Verify before using any method or path.

**`standards/pipeline-standards.md`**: how pipelines are built. Layer boundaries. Write semantics. Idempotency at every layer. Null handling explicit at every join. Schema lineage from source through output.

---

## Memory

When you correct Claude's approach, that correction does not disappear. `/tg-close` surfaces it as a memory candidate. You approve it. It is saved as a memory file in your Claude project memory folder (`~/.claude/projects/<project>/memory/`). {src:commands/tg-close.md:186}

The next session, the correction is applied without you repeating it. Memory files accumulate into a picture of how you work, what has gone wrong, and what has been validated.

---

## Full Documentation

| Document | Read it to... |
|---|---|
| [Prerequisites](prerequisites.md) | Know what to install and collect before setup |
| [Setup](setup.md) | Get from clone to first session |
| [Skill Chains](skill-chains.md) | Know which chain to run for which ticket type |
| [Walkthrough](walkthrough.md) | See the system working on a real ticket |
| [System Design](system-design.md) | Understand the architecture and how to adapt it |
| [File Structure](structure.md) | See where everything lives and why |
