# The owner

```bash
ws owner
```

The owner is the person whose workspace this is. Two records say who that
is, and `ws owner` prints them both:

```text
the person labelled owner    private facts: every address, what to call them,
                             and the relations around them
the profile identity         public facts: the name, headline and contact
                             details a CV may show
```

Relations stay out of the output; `ws show person:<key>` lists them. With
neither record it prints nothing and succeeds, so anything may call it. With
one of the two it prints that one. `--json` prints `null` when there is no
owner, since a program expects to parse something.

## Making the records

`ws setup` asks you for both (`ws help setup`). By hand:

```bash
ws create profile Alex Example --type identity --email alex@example.org
ws add person Alex Example --owner --email alex.private@example.org
```

For someone already on record:

```bash
ws edit person:<key> --owner
```

At most one person is the owner, and a second is refused until the first is
cleared with `ws edit person:<key> --no-owner`. The identity needs no label of
its own: its type is the label, and there is at most one (`ws help profile`).
Merging an owner into another person carries the label over.

## In the briefing

Every briefing inside the workspace names the owner, and points here for the
rest (`ws help context`). The name is looked up each time a briefing is built,
so it follows the records and needs no setting:

```text
[workspace · owner]
  This is the workspace of Alex Example. For their details: ws owner
```

Without an owner the line is left out.
