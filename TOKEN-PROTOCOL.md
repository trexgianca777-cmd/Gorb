# Token Protocol — minimizing orchestrator (Muse) token use

Every token the orchestrator reads is cost. These rules are mechanical, not
aspirational. They apply to all swarm scripts, engine scripts, and subagent
briefs.

## 1. Scripts: summaries to stdout, data to files

- stdout gets at most ~10 lines: what ran, the verdict, the file paths.
- Full output always goes to files under a run directory. Print each path once.
- Never print a full model response, log, or JSON blob to stdout.
- Already compliant: `swarm-call.sh` (one line per model + `timings.tsv`),
  `audit-target.sh` (one line per role + `finding-<role>.txt`).

## 2. Reading: target, don't dump

- `grep -n` / `sed -n 'A,Bp'` / `tail -N` for the section you need.
- `head -c N` caps on any curl output piped toward the orchestrator.
- Never re-read a file already in context; never `cat` a whole file "to check".

## 3. Subagents: briefs, not transcripts

- Return: verdict first, key numbers, file paths of evidence. No pasted dumps.
- If the evidence matters, write it to a file and cite the path.
- One subagent per independent task; the orchestrator reads one digest each.

## 4. Cache before compute

- `swarm-call.sh` caches exact and normalized prompt hits — check the cache
  before re-running an identical prompt.
- Before any expensive run, `ls` the expected output dir; don't redo done work.

## 5. Prompts: lean

- System prompts stay short (prompt v5: 755 -> 494 words). Cut ruthlessly;
  re-ablate after changes.
- Prefer `SWARM_MODE=smart` (4 models) over full-roster fan-out unless the
  task needs the breadth. Fewer models = fewer outputs to read.

## 6. Logs

- `tail` logs. `grep` for the error. Never dump a whole log into context.
