# /doctor

Act as EZ. Use the run ID or path already available in the conversation and run
`ez doctor <corrida> --json`. Explain what is verifiable, what failed and the next
action in the user's language. Do not infer academic validity from a local PASS.
If the run is legacy, inspect it without implicit migration; show a migration
preview only when relevant. Follow `docs/ez-host-operator.md` for recovery.
