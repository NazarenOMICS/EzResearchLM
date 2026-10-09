# EZresearchLM Agent Guide

EZresearchLM is a NotebookLM-centered evidence pipeline for academic research.
It discovers papers, acquires PDFs, builds a traceable source set, asks
NotebookLM focused questions, exports cited answers, and keeps enough run state
to debug or resume interrupted work.

## Non-Negotiable Rules

These hold for the whole conversation, including after context compaction. Every JSON
answer from `ez` repeats them in `operator_reminder`.

1. Every statement about the literature comes from EZ and carries its `[EZ:<id>]` marker.
2. Answer a follow-up question from the claims already delivered or with
   `ez ask "<question>" --project <project>`. New papers come only through `ez research`.
3. Never use web search or model memory for bibliographic claims, nor to complete an EZ
   answer. When the user explicitly asks for external data (for example a UniProt entry),
   give it separately, labelled «fuente externa, no del corpus» (external source, not from the corpus).
4. Draft only with `ez draft` and check with `ez draft <run> --check <file>`.
5. Build the plan with `ez plan` and the screening with `ez screen`. Never write or edit run
   files by hand (`research-contract.json`, `sources.json`, `state.json`, …) or write scripts
   that generate them.
6. Do not read `docs/history/`: it describes earlier versions and their obsolete formats.

## Operator Model

EZ is the single user-facing operator. Claude Code, Codex, Hermes, or another
host agent supplies its planning and synthesis without an additional model API.
Read `docs/ez-host-operator.md` before operating the new `ez` interface. The host
prepares contracts and, in verified delivery, QA reviews on the user's behalf; do not
ask users to edit JSON. New contracts default to `plan.delivery: "direct"`: EZ delivers
NotebookLM's cited sentences right after QA, without a host review or a second query.
Choose `"verified"` when the user will draft from the claims. Runs of one project share
the project's NotebookLM notebook.

NotebookLM remains the evidence engine. The current implementation is an internal
candidate; authenticated E2E and closed beta are still required before release.

## Core Rules

- NotebookLM is the evidence and QA engine. Local search is a recall and acquisition
  helper, not an answer engine.
- If evidence is missing, report the state EZ gives (`NEEDS_CORPUS`, `NEEDS_MORE_QA`,
  `NEEDS_SOURCE_RESCUE`, …) and its next action.
- Acquisition uses only open-access routes and PDFs the user imports. Anna's
  Archive and Sci-Hub are not supported; never automate access challenges.
- Do not commit real PDFs, notebooks, tokens, cookies, source exports, or run
  artifacts.

## Drafting

Draft academic prose only from `ez draft` claims, keep their `[EZ:<id>]` markers and
the reported gaps, and check the draft with `ez draft <run> --check <file>`.

- Answer the question asked, in clear prose; use lists or tables only when the user
  asks for them.
- Separate reported evidence from interpretation, and mark interpretation as such.
- Do not mix organism, population, method, dose, time or context across sources
  without saying that the link is an inference.
- Do not claim mechanism, magnitude, causality or generality beyond what the cited
  passage supports. State uncertainty and indirect evidence explicitly.
- If a claim's passage does not support a sentence, remove the sentence or mark the gap.

## File Integrity Checks

Before committing edits to long-lived Markdown or index files:

- Re-read the complete edited file with the agent's file-read tool when one is
  available. Do not rely only on shell views such as `cat`, `tail`, or `wc`,
  because a sandboxed shell can show stale or truncated content.
- Confirm the file ends at the expected final section or sentence.
- Review `git diff --stat` and the full `git diff` for the edited file before
  staging. Unexpected large deletions or mid-word endings are blockers.

## Repository Layout

| Resource | Path |
|---|---|
| EZ package | `packages/ez/` |
| Literature search providers | `packages/paper_search/` |
| Operator and user guides | `docs/` |
| Tests | `tests/`, `packages/paper_search/tests/` |
| Claude Desktop extension | `desktop/` |
| Benchmark and gold set | `gold_set_benchmark/` |

Runs live outside the repository, in `~/.ezresearch/runs` by default
(`EZRESEARCH_RUNS_ROOT` overrides it). Projects, inboxes and reports are described in
`docs/carpetas.md`.

## Main Commands

`ez setup`, `ez context`, `ez projects`, `ez research`, `ez plan`, `ez screen`,
`ez continue`, `ez status`, `ez ask`, `ez rescue`, `ez draft`, `ez export`, `ez verify`
and `ez doctor`. See `docs/ez-host-operator.md` for the host workflow. Runs created by
the PowerShell wrappers of earlier versions can be inspected with
`ez doctor <path> --migration-preview --json`; apply only the reviewed preview hash.
Original files are preserved.

## Acquisition Order

1. direct PDF URL
2. PMC OA PDF or archive
3. EuropePMC/OpenAlex source-native OA
4. Unpaywall
5. CORE/OpenAIRE and repository locations

When every route fails, the source stays `manual_needed`. The user can drop the PDF in
the project inbox or import it with `ez rescue <run> --source <id> --import <pdf>`; its
origin is recorded.

## Validation

Before committing:

```powershell
python scripts/validate.py
```
