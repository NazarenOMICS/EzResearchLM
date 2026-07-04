# /research

Operate one EZresearchLM evidence run.

Input expected from the user:

- research question;
- project name;
- slug;
- must-have papers, if any.

Workflow:

1. Run setup readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

2. Convert the research question into 6-10 focused academic search queries.
3. Write a JSON array of strings to:
   `runs\<project>\<slug>\queries-<slug>.json`
4. Write a must-have JSON file if required sources are named:
   `runs\<project>\<slug>\must-have-<slug>.json`
5. Show both files to the user.
6. Run `scripts\run_hermes_pipeline.ps1` with:
   - `-Project`;
   - `-Slug`;
   - `-Goal`;
   - `-QueriesFile`;
   - `-MustHaveFile` when available;
   - `-StopIfMissingMustHave`.
7. If the pipeline returns `NEEDS_SOURCE_RESCUE`, stop and run the doctor.
8. If the pipeline returns `NEEDS_QUESTIONS`, prepare focused NotebookLM
   questions with integer IDs, then resume with `-FromExistingQuestions`.
9. Use only exported NotebookLM summaries and citation audits for claims.

Never answer the literature question from model memory.
