# /tg-think-calibrate

A weekly 5 to 10 minute check on how far ahead you reason, with one challenge to carry into the next week {src:commands/tg-think-calibrate.md:8-10}.

The command name is fixed: `/tg-think-calibrate` runs the full session {src:commands/tg-think-calibrate.md:47}.

## When to use

Once a week (the command says every Sunday), after you made a real prediction or decision {src:commands/tg-think-calibrate.md:9}.

## What it does

1. Loads the last session date, score, trend and challenge from the state file. With no state file it is session 1 and creates the file at the end {src:commands/tg-think-calibrate.md:53-59}.
2. Asks for one prediction or decision. It accepts one entry only and does not coach the wording {src:commands/tg-think-calibrate.md:71-77}.
3. Asks you to walk the reasoning chain, with one "and then what?" prompt if it stops early {src:commands/tg-think-calibrate.md:89-95}.
4. Scores the chain 2nd, 3rd or 4th order, and shows what the next order would add for your example {src:commands/tg-think-calibrate.md:107-114}.
5. Gives you one forced next-level question. It does not give the answer before your attempt {src:commands/tg-think-calibrate.md:123-135}.
6. Writes the dated entry and updates the state file, then reads the next-week challenge back {src:commands/tg-think-calibrate.md:141} {src:commands/tg-think-calibrate.md:185} {src:commands/tg-think-calibrate.md:208}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{knowledge}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-think-calibrate.md:3}.

- Reads: `{knowledge}/thinking-calibration/calibration-state.md` (the last score and challenge) {src:commands/tg-think-calibrate.md:13} {src:commands/tg-think-calibrate.md:53}.
- Writes: a dated entry `{knowledge}/thinking-calibration/YYYY-MM-DD.md` and the updated state file. The entry is required; the session does not close without it {src:commands/tg-think-calibrate.md:141} {src:commands/tg-think-calibrate.md:226}.
- It runs no search, no vault git line and no commit.

## Hooks and gate lines

No gate line applies. It is not part of the spec, arch, dev, qa chain, so the gate does not read it. The normal write guards still apply to any file it writes. Patient data never goes in the entry; abstract it first {src:commands/tg-think-calibrate.md:225}.

## Example

`/tg-think-calibrate`, you describe a call you made on T-001, it scores the chain as 2nd order, shows what 3rd order would add, and sets one question for next week {src:commands/tg-think-calibrate.md:107} {src:commands/tg-think-calibrate.md:181}.
