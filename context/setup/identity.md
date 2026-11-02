EXPLAIN

Everything in ws is an object, and this is the first one. The profile is the
domain for career facts: degrees, positions, talks, publications. CVs are
generated from it. Its first object is the identity: who they are in public,
meaning the name, headline and contact details a CV may show. There is only
ever one. Private details come next, in a separate object.

ASK

- Their full name, as a CV should show it.
- A one-line professional headline.
- The email, phone and postal address a CV should show.
- Any public links, such as a website, and their ORCID if they have one.

RUN, leaving out what they skipped

    ws create profile NAME --type identity --ensure \
      --headline "..." --email EMAIL --phone PHONE --address "..." \
      --link URL --orcid ORCID --source "ws setup" --observed-at {today}
