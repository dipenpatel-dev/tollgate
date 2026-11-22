# /tg-learn

**It teaches you one concept at a time and leaves a learning note behind.** Use it to build a real mental model of your own systems. It asks first, corrects, challenges and makes you teach it back {src:commands/tg-learn.md:5} {src:commands/tg-learn.md:228-231}.

The command name is fixed: `/tg-learn`. With no argument it asks what to work on, or suggests a topic from the learning state {src:commands/tg-learn.md:24}.

## What it does

- `/tg-learn {topic}`: probe, correct, teach with real code, challenge, apply, teach-back, connect {src:commands/tg-learn.md:18} {src:commands/tg-learn.md:87} {src:commands/tg-learn.md:101} {src:commands/tg-learn.md:107} {src:commands/tg-learn.md:120} {src:commands/tg-learn.md:134} {src:commands/tg-learn.md:140} {src:commands/tg-learn.md:146}.
- `/tg-learn continue`: picks up from the "Next" pointer in your learning state {src:commands/tg-learn.md:19} {src:commands/tg-learn.md:81}.
- `/tg-learn map`: shows what is solid, in progress, a gap, or untouched. It reads the learning state first and does not build the map from memory {src:commands/tg-learn.md:20} {src:commands/tg-learn.md:154}.
- `/tg-learn trace {bug or feature}`: follows data through each layer. You predict first, Claude writes the query, you run it. A query is never run before a prediction, and a surprise stops the loop until it is understood. Protected or personal data never enters Claude's context {src:commands/tg-learn.md:21} {src:commands/tg-learn.md:54-56} {src:commands/tg-learn.md:61-65}.

Each session ends with one question, "what changed your mental model today", then it updates the learning state and writes a session note {src:commands/tg-learn.md:179} {src:commands/tg-learn.md:181} {src:commands/tg-learn.md:214}.

## What it reads and writes

Folders are not fixed paths. The command looks up `{vault}`, `{education}` and `{conversations}` at run time with `$TOLLGATE_HOME/scripts/core/tg_path <name>`. If that prints `not set up`, it stops and tells you to run setup {src:commands/tg-learn.md:3}.

- Reads: `{education}/learning-state.md`. If it does not exist the command says so, asks for your background and goals, and creates it at the end of the session {src:commands/tg-learn.md:73}.
- Search: for topic and trace modes only (not `continue` or `map`) it runs `$TOLLGATE_HOME/scripts/search/tg-search query "{topic or bug keywords}" --top 8` and reads results scoring 0.5 or higher. If it prints `not set up`, it says so in one line and goes on {src:commands/tg-learn.md:74-78}.
- Writes: the learning state and a session note at `{conversations}/YYYY/MM/YYYY-MM-DD-{topic_slug}.md` {src:commands/tg-learn.md:181} {src:commands/tg-learn.md:214}. Trace mode also writes one diagnostic query file per bug in your scripts folder and a root-cause note in the ticket folder {src:commands/tg-learn.md:67}.
- Vault git: it never commits, and runs and prints no vault git line. Conversation notes stay local {src:commands/tg-learn.md:234-235}.

## Hooks and gate lines

Both notes carry frontmatter that passes the vault frontmatter hook (`type: learning_state` or `learning_session`, upper case `status`, a real `date`, no empty strings) {src:commands/tg-learn.md:181} {src:commands/tg-learn.md:185-188}. No gate line applies.

## Example

```
/tg-learn trace T-001
```

You predict what the data looks like at the first layer, run the query it gives you, and compare. A mismatch is the lesson {src:commands/tg-learn.md:54-57}.
