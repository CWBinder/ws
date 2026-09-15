# Data authority policy

Each durable fact has one canonical owner:

- domain YAML owns workspace object facts;
- `workspace/relations/*.yaml` owns cross-domain links;
- provider systems own connector data;
- provider credential stores own secrets;
- generated SQLite and Markdown own no canonical facts.

When two views disagree, fix the canonical owner and rebuild the derived view.
