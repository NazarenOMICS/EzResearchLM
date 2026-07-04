# /research

Operate one EZresearchLM evidence run.

Input expected from the user:

- research question;
- project name;
- slug;
- must-have papers, if any.

Workflow:

1. Convert the research question into 6-10 focused academic search queries.
2. Write a JSON array of strings to a query file.
3. Write a must-have JSON file if required sources are named.
4. Show both files to the user.
5. Run `scripts\run_hermes_pipeline.ps1` with:
   - `-Project`;
   - `-Slug`;
   - `-Goal`;
   - `-QueriesFile`;
   - `-MustHaveFile` when available;
   - `-StopIfMissingMustHave`.
6. If the pipeline returns `NEEDS_SOURCE_RESCUE`, stop and run the doctor.
7. If the pipeline returns `NEEDS_QUESTIONS`, prepare focused NotebookLM
   questions with integer IDs, then resume with `-FromExistingQuestions`.
8. Use only exported NotebookLM summaries and citation audits for claims.

Never answer the literature question from model memory.
