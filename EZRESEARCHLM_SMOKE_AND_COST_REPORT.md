# EZresearchLM Smoke And Cost Report

Date: 2026-07-04

## Executive Verdict

EZresearchLM is in a deliverable state for GitHub as a local/agent-operated
research pipeline. The reproducible smoke suite passed 9/9 checks on this
machine.

Claude is not a replacement for Hermes. The best architecture is:

- Claude Code as the operator and UX layer.
- Hermes/EZresearchLM as the deterministic pipeline.
- NotebookLM as the evidence and citation engine.
- QMD as local recall over already imported outputs.

Claude is better than plain Hermes for user-facing operation because it can
guide setup, create query/must-have files, interpret doctor output, and recover
from run states conversationally. Hermes is better than Claude alone for
research correctness because it preserves stages, artifacts, acquisition
provenance, rescue queues, and NotebookLM gates.

## Smoke Results

Command:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" `
  -IncludeClaude `
  -IncludeFullPipelinePreflight `
  -ReportPath ".\runs\smoke-runs\latest-smoke-report.json"
```

Result: 9 passed, 0 failed.

| Smoke | Result | What It Proves |
|---|---:|---|
| `setup-search-only` | PASS | Python and package import work; search/acquisition can run without NotebookLM auth. |
| `setup-claude-state` | PASS | Claude Code is detected even when it is not in PATH. |
| `powershell-parse` | PASS | All 8 PowerShell scripts parse. |
| `python-compile` | PASS | Core Python entrypoints compile. |
| `unit-tests` | PASS | 15 paper-search tests pass. |
| `doctor-nonexistent-run` | PASS | Doctor handles missing run artifacts and prints a resume command. |
| `search-scout-crossref` | PASS | Discovery/scout mode writes candidate, rescue, and missing-source artifacts without downloading PDFs. |
| `resolve-must-have-rescue` | PASS | Missing required sources become `manual_needed` in `source-rescue.json`. |
| `pipeline-preflight-auth-gate` | PASS | Pipeline stops before QA when NotebookLM auth is expired. |

Important current machine state:

- `claude_cli_ok=true`
- `claude_auth_ok=false`
- `claude_workspace_trusted=true`
- `notebooklm_cli_ok=true`
- `notebooklm_auth_ok=false`
- `ready_for_search=true`
- `ready_for_full_pipeline=false`

This is the right failure mode: the repo is operable for setup/search smoke, but
real NotebookLM QA and real Claude `/setup` require interactive login.

## What Still Requires Human Login

Claude Code:

```powershell
& "C:\Users\Administrator\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\2.1.197\claude.exe" auth login
```

NotebookLM:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
```

After both logins:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

Then test Claude:

```powershell
cd C:\Users\Administrator\Documents\EZresearchLM
claude
/setup
```

## Cost Model

### Claude Code

Claude Code is valuable for operating the repo, but it is not intrinsically
cheap if used as the whole research engine. Anthropic states that Claude Code
charges by API token consumption for API usage, while Pro/Max subscribers see
usage through plan limits. Anthropic's cost guide says enterprise deployments
average about $13 per developer active day and $150-250 per developer per
month, with 90% below $30 per active day:

Source: https://code.claude.com/docs/en/costs

Claude plan pricing on the official pricing page:

- Pro: $20/month or $200/year, includes Claude Code.
- Max: from $100/month.

Source: https://claude.com/pricing

Claude model API pricing from Anthropic docs:

- Opus 4.8: $5 / input MTok, $25 / output MTok.
- Sonnet 5: standard $3 / input MTok, $15 / output MTok; introductory $2 / $10 through 2026-08-31.
- Haiku 4.5: $1 / input MTok, $5 / output MTok.

Source: https://platform.claude.com/docs/en/about-claude/models/overview
Source: https://www.anthropic.com/claude/sonnet

### NotebookLM / Google AI

NotebookLM is the strongest cost argument for EZresearchLM. Google documents a
free Standard tier with 100 notebooks, 50 sources per notebook, and 50 daily
chats. It also documents higher limits for Plus, Pro, and Ultra plans.

Source: https://support.google.com/notebooklm/answer/16269187
Source: https://support.google.com/notebooklm/answer/16213268

Google AI plan prices vary by plan and region; Google's US Google One page
lists:

- Google AI Plus: $4.99/month.
- Google AI Pro: $19.99/month.
- Google AI Ultra: from $99.99/month.

Source: https://one.google.com/intl/en_us/about/google-ai-plans/

### OpenAI / GPT Alternative

OpenAI API pricing is competitive for orchestration and batch work, especially
with mini/nano models, but direct model calls still charge per token. Official
OpenAI pricing lists, for standard short-context usage:

- GPT-5.5: $5 input / $30 output per 1M tokens.
- GPT-5.4: $2.50 input / $15 output per 1M tokens.
- GPT-5.4-mini: $0.75 input / $4.50 output per 1M tokens.
- GPT-5.4-nano: $0.20 input / $1.25 output per 1M tokens.

Source: https://developers.openai.com/api/docs/pricing

## Claude vs Hermes

### Claude Alone

Strengths:

- Best human-facing interface.
- Good at guiding setup and explaining state.
- Good at editing repo files, debugging scripts, and interpreting logs.
- Good for generating query files and question files when constrained by the repo contract.

Weaknesses:

- Can drift into answering from model memory.
- Expensive if it repeatedly reads large exports, PDFs, or raw source notes.
- Lacks built-in structured acquisition provenance unless the repo enforces it.
- Requires login, workspace trust, and plan/API budget.

### Hermes/EZresearchLM Alone

Strengths:

- Deterministic stages: discover, resolve, acquire, rescue, notebook, QA, audit.
- Explicit source state in `source-rescue.json`.
- Hard gate before NotebookLM QA if must-have sources are missing.
- Anna fallback is auditable and separated from answer generation.
- Cheaper at scale because search/acquisition are local/scripted and NotebookLM absorbs evidence QA.

Weaknesses:

- Raw CLI UX is harder for new users.
- Recovery after partial failures is less obvious without an agent.
- Needs good prompts/queries from a human or operator model.
- NotebookLM auth remains an external brittle point.

### Best Combined Design

Use Claude as an operator, not an evidence engine.

Claude should:

- run `/setup`;
- create `queries-*.json` and `must-have-*.json`;
- call official wrappers only;
- run doctor after crashes/timeouts;
- read `STATUS.md`, `run-state.json`, `source-rescue.json`, summaries, and citation audits;
- stop at `NEEDS_SOURCE_RESCUE`, `NEEDS_CORPUS`, or expired auth.

Claude should not:

- invent bibliographic claims;
- replace NotebookLM QA;
- manually scrape papers unless explicitly requested;
- read huge NotebookLM exports as a default workflow.

## Cost Recommendation

The cheapest trustworthy workflow is not "Claude instead of Hermes"; it is
"Claude plus Hermes plus NotebookLM."

Recommended operating model:

1. Use NotebookLM as the expensive reasoning substitute because its free/Google
   AI tiers are better aligned with source-grounded QA.
2. Use Hermes/EZresearchLM to minimize repeated model context by storing
   structured state and resumable artifacts.
3. Use Claude Code only for orchestration, debugging, and user guidance.
4. Use smaller/cheaper models or no model at all for deterministic stages.
5. Keep QMD as a recall index so future questions avoid rebuilding context.

Practical cost hierarchy:

1. Lowest cost: Hermes/EZresearchLM + NotebookLM Standard + occasional Claude
   operator usage.
2. Good paid setup: Hermes/EZresearchLM + Google AI Pro/NotebookLM higher
   limits + Claude Pro/Max as operator.
3. Higher cost: Claude Code doing broad repo/paper reading directly.
4. Highest avoidable cost: agentic Claude/OpenAI loops over raw PDFs and giant
   exports without rescue queues or NotebookLM gates.

## Delivery Status

Deliverable:

- Reproducible smoke runner added: `scripts/run_smoke_tests.ps1`.
- Latest smoke run: 9/9 pass.
- Repo remains clean of `.env`, `.venv`, PDFs, and run artifacts.

Not fully validated yet:

- Real Claude `/setup` after `claude auth login`.
- Real NotebookLM upload/QA after NotebookLM re-auth.
- Real Anna fallback download, intentionally not executed during delivery smoke.

Next recommended command after login:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_smoke_tests.ps1" `
  -IncludeClaude `
  -IncludeFullPipelinePreflight
```

Then run one tiny real corpus with a known OA paper and `-StopIfMissingMustHave`.
