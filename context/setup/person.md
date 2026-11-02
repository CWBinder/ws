EXPLAIN

The person object is the private side. Everyone they deal with gets a person
record; this one is labelled as the owner, so that agents can find it. Facts
that do not belong on a CV go here, such as every address they use and how
they like to be called. Relations attach to it later: the papers they
co-authored, the organisations they belong to, the events they attended.

Public facts stay in the identity, private ones here. Agents read both with
`ws owner`.

ASK

- What should agents call them?
- Every email address and phone number worth knowing.
- A sentence or two on who they are and what they do.

RUN, with the name from their identity, leaving out what they skipped

    ws search people NAME

If that finds their own record, label it:

    ws edit person:KEY --owner --source "ws setup" --observed-at {today}

Otherwise make it:

    ws add person NAME --owner --preferred-name NAME \
      --email EMAIL --phone PHONE --description "..." \
      --source "ws setup" --observed-at {today}
