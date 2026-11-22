# /tg-explain

**It explains the last code change in plain words, in under 250 words.** Use it right after a dev block commits, when you want to know what was built and what to double-check {src:commands/tg-explain.md:3}. It takes no arguments {src:commands/tg-explain.md:13}.

## What it reads and writes

- Reads: the diff of the last commit (`git diff HEAD~1 HEAD`), or the staged diff (`git diff --staged`) if that returns nothing {src:commands/tg-explain.md:22} {src:commands/tg-explain.md:28}.
- Writes: nothing. It writes no file and sends nothing {src:commands/tg-explain.md:72}. It prints four short sections: what was built, how it works, what would break it, what to check in the diff {src:commands/tg-explain.md:40} {src:commands/tg-explain.md:45} {src:commands/tg-explain.md:50} {src:commands/tg-explain.md:56}.
- If both diffs are empty it says "No diff found. Commit or stage your changes first." and stops {src:commands/tg-explain.md:31}.
- If the diff is too large for 250 words, it focuses on the highest-risk mechanism and says so in one sentence at the top {src:commands/tg-explain.md:71}.

It uses no folder lookup, no search and no vault git.

## Hooks and gate lines

None. It is not a chain command and the gate does not check it.

## Example

After block 1 of ticket `T-001` is committed, type `/tg-explain`. You get four short sections about that commit, for example a failure mode such as "a missing input file stops the loader", and two functions to look at again {src:commands/tg-explain.md:51-61}.
