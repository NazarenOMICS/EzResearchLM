# EZresearchLM

[Leer en español](README.es.md)

**EZ finds scientific articles on your question, loads them into your NotebookLM and hands
you what they say, with the passage and page behind every citation.** It does not answer
from memory: every claim comes from a PDF you can open.

> **Preview release.** It works end to end, but external validation is still pending
> (comparison with other tools, installs on clean machines). Check each passage in its PDF
> before citing it in a thesis or a paper.

## Get started

You need an AI agent on your computer, such as Codex or Claude Code, and a Google account
for NotebookLM. Paste this message to your agent:

> I want to do research with EZ: https://github.com/NazarenOMICS/EzResearchLM. Install it, read its AGENTS.md and guide me step by step.

The agent installs EZ and guides you step by step, one question at a time. You do not need
to type commands. EZ talks to you in your language. To pick up another day, in a new chat:

> I want to continue my research in EZ: https://github.com/NazarenOMICS/EzResearchLM

### For the agent

If someone gave you this link, they want to use EZ, even if they only asked you to download
or install it:

1. If `~/.ezresearch/install.json` exists, EZ is already installed: use the `ez` it names and
   do not clone again. Otherwise ask where to install it (suggest `Documents\EZresearchLM`;
   never your chat's temporary folder), clone it there and install it as [SETUP.md](SETUP.md) says.
2. Read [AGENTS.md](AGENTS.md) completely: your session started before the clone, so it did
   not load it. It tells you what else to read and when.
3. Start the first conversation of that guide right away: introduce yourself as EZ, say
   what they can ask you, and guide the setup one step at a time. Do not stop at
   "downloaded".

If you do not use agents in a terminal, there is an
[experimental Claude Desktop extension](desktop/README.md).

## What a research looks like

1. **Set up.** EZ installs what is missing. You sign in to NotebookLM with your Google
   account in your browser and, if you like, give a contact email to find more free articles.
2. **Ask.** You say what you want to research and why. EZ asks whether it belongs to one of
   your existing projects or starts a new one.
3. **Plan.** EZ shows you in a few lines what it will search for and how long it will take,
   and waits for your go-ahead.
4. **Bibliography.** EZ searches PubMed, Europe PMC, OpenAlex and Crossref, picks the
   relevant articles and tells you **before downloading anything** if a key one is
   paywalled. It gives you the title and a DOI link so you can get it through your library
   or by asking the authors. You drop it in the project inbox and EZ picks it up.
5. **Answer.** EZ loads the PDFs into your NotebookLM, asks its questions and delivers a
   report: the key findings first, every claim with its passage and page, and what could not
   be answered and why.
6. **Then.** You can have each claim verified one by one before writing, export the
   bibliography to Zotero, or ask another question in the same project, which reuses the
   articles already loaded.

## Where everything goes

```
~/.ezresearch/projects/<your project>/
├── README.md     index of your researches, with links
├── inbox/        drop your PDFs here
├── reports/      each report and its bibliography (.bib)
└── notes/        Obsidian vault: cited passages per article, claims per research
```

More in [where everything goes](docs/carpetas.md)
(Spanish).

## What was measured

Live runs in October 2026 on the project's test question (the effect of ethambutol on
*Corynebacterium glutamicum*):

| Measure | Result |
|---|---|
| Research from scratch (search, download, 4 questions) | 6.5 minutes |
| Question in a project with its PDFs already loaded (5 questions) | 6 to 7 minutes |
| Claims backed by their passage, 20 checked by hand | 18 supported, 2 partial, 0 unsupported |

Each NotebookLM question takes about a minute, the same as in its web app. A sample of 20 is
small: the true precision lies, with 95 % confidence, between 70 % and 97 %. Details are in
`gold_set_benchmark/` and the pending plan in the [roadmap](docs/roadmap.md) (Spanish).

## Limits

1. **NotebookLM's free plan** allows 50 sources per notebook and has a usage quota; every
   question uses it.
2. **Your PDFs are uploaded to your Google account**, inside NotebookLM.
3. **EZ relies on `notebooklm-py`, an unofficial library.** If Google changes NotebookLM, EZ
   may stop working until it is updated.
4. **Open access or your own PDFs only.** EZ does not use Anna's Archive or Sci-Hub and does
   not bypass access controls.
5. **Checking is automatic.** Claims are NotebookLM's sentences with the passages it cited
   itself; the optional verification is done by NotebookLM too. Neither is a human review.

## Installation (for the agent)

If you were given only the link to this repository, the person wants to use EZ and
probably does not know terminals. Do it yourself, without asking them for commands:

1. Check that Git and Python 3.10 or newer are present (`git --version`, `python --version`).
   If one is missing, explain in one sentence how to install it (on Windows:
   `winget install Git.Git Python.Python.3.12`) and wait.
2. Ask the person where to install it, suggesting `Documents\EZresearchLM`, and clone the
   repository there; never into your chat's temporary folder. If the link points to a branch
   (`.../tree/<branch>`), clone that branch.
3. Install EZ in an isolated environment inside the repository (here, the suggested folder):

   ```powershell
   cd $env:USERPROFILE\Documents\EZresearchLM
   python -m venv .venv
   .venv\Scripts\python -m pip install -c requirements.lock .
   .venv\Scripts\ez setup --check --json
   ```

   On macOS or Linux, use `.venv/bin/python` and `.venv/bin/ez`. Always call the
   environment's `ez`.
4. Read `AGENTS.md` and start the onboarding of `docs/ez-host-operator.md`: one
   step and one question at a time, without showing commands or JSON. Speak the person's
   language; the guide is written in Spanish. `ez setup --check` reports what is missing
   (install NotebookLM with `ez setup --install-notebooklm`, sign in, Unpaywall email).

## Documentation

The detailed guides are in Spanish for now.

1. [First-use guide](docs/ez-user-guide.md): what you can ask EZ.
2. [Agent guide](docs/ez-host-operator.md): how the agent talks to the person; the rest of the
   flow is in [docs/agent/](docs/agent/).
3. [Contracts and states](docs/ez-contracts.md) and [configuration](docs/configuration.md):
   technical details.
4. [Roadmap](docs/roadmap.md): what is done, what is missing and in which order.

## License

MIT.
