# Logistics contract

People, organisations, and events are standardised list-like entities and use
`add`. Their canonical YAML records live under `logistics/`.

`add` records a new entity each time. `add --ensure` and the `ensure` verb are
idempotent get-or-create: when exactly one existing record matches, its id is
returned (`exists:` instead of `created:`; `--json` carries a `created` flag)
and newly supplied facts fill only fields that were still empty. Matching uses
the normalised title or an alias; people also match by email, organisations by
website, and events by title plus start date. More than one match fails as
ambiguous rather than guessing.

`communications/` belongs to logistics and holds content assets such as
templates, styles, and references. Connectors are a service; the nested
credentials.
