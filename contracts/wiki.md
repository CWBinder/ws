# Wiki contract

`ws wiki build` creates a derived view under `wiki/generated/`.
Generated notes may repeat labels and direct wikilinks for presentation, but
canonical facts and relations remain in their domain stores. Deleting and
rebuilding the generated wiki must not lose canonical information.
