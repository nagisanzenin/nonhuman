---
name: nonhuman
description: Agent-first coding mode for any coding agent and language. Optimises for the next agent, not a human reader - fewest billed tokens (calls, output, context) per correct and secure result. Use for any implementation, bug-fix or refactor task.
---
# nonhuman

The code you write will be read and maintained by agents. Optimise for that: the fewest billed tokens per correct and secure result. Every model call re-reads the whole context, so the number of calls is the biggest cost; output tokens are the next. Correctness, performance and security are never traded. Human readability is optional.

## Fewer calls (most important)
- Put every independent tool call in the same turn: all searches together, all reads together, edits to different files together, work on independent tasks in parallel.
- Locate first (grep or the failing test), then read only the needed line ranges, all in one turn. Never re-read a file or range already in context.
- Make all changes to a file in one edit call when possible. Write each new file once.
- Verify once: after the edits, run the narrowest relevant tests; when they pass, run the full suite once at the end. Do not re-run passing tests or revise passing code.
- Stop when the task is done. No extra exploration, no optional refactors, no re-checking finished work.

## Less output
- Smallest correct diff; never re-print, rewrite or reformat unchanged code.
- No comments, docstrings, blank-line padding, debug prints or logging unless the task, API contract or an enforced linter needs them. Exception: a one-line comment for a non-obvious invariant or security reason the next agent could not infer.
- Keep type annotations on signatures; follow the codebase's typing convention.
- Reuse first: existing helper in the codebase > stdlib > installed dependency > new code. No new dependencies, options or abstractions nobody asked for.
- Tests: add at most one compact test per task, and only for new non-trivial logic that no existing test covers.
- Final reply: at most 3 lines (what changed, how verified, any risk). No preamble, no narration, no recap.

## Small tool output
Use quiet flags (`-q`), `| tail -n 30`, `| head`, grep for failures; never dump whole files, trees or logs, and never cut off the failing line.

## Never cut
Input validation at trust boundaries, authentication and ownership checks, parameterised queries and escaping, path-traversal guards, bounds/overflow/length checks, error handling that prevents data loss or leaks, resource limits. Reuse the codebase's existing guard helpers for every new entry point. If unsure whether a guard is needed, keep it.
