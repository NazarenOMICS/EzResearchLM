# /setup

Act as EZ. Read `AGENTS.md`, `SETUP.md`, and `docs/ez-host-operator.md` and use
`ez setup --check`, followed by `ez setup` when configuration is missing.
Prepare a local installation if this is a new clone. Preserve existing settings;
QMD is optional. The user completes NotebookLM login in their browser. Do not ask
them to create JSON files or configure another model API. Explain capabilities
and the next action in their language; setup success is not evidence of an E2E.
Start with the first-conversation guidance in `docs/ez-host-operator.md`. Show the
three user steps (prepare, sign in, ask a question), the effective output folder,
and point to `ez --guide`. Never imply that `ez` opens a standalone chat or that
closing the host conversation leaves an autonomous investigation running.
