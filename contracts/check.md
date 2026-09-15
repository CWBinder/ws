# Check contract

`ws check` validates state and reports findings. It does not repair, rewrite,
or delete canonical data. Validation is spelled `check`; there is no other
name for it.

A bare `ws check` covers every area.

The `cli` area validates the CLI's own discovery surface against
`contracts/cli.md`: every command carries a description, every visible flag
and positional carries help text, every positional shows a lexicon
placeholder, every command resolves to a governing contract, every writing
command declares its own effects, and no help text teaches a spelling that
no longer parses. It reads the parser and registry only — no workspace
state — so it is the one area that also passes on an empty workspace.

