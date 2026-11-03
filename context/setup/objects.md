Everything the workspace knows is an object, of one of nine kinds:

    project       a piece of work, with its own folder
    task          something to do
    document      one file worth addressing: an invoice, a contract
    resource      a bundle of supporting files, such as receipts
    literature    a paper or book with a DOI, arXiv ID or ISBN
    person        someone you deal with
    organisation  an institution, company or group
    event         a conference, meeting or talk
    profile       one of your own career facts, for CVs

Each object has one REF, such as `project:thesis` or `person:jane-doe`. A relation
is a directed sentence between two of them:

    person:jane-doe  --works-at-->  organisation:oxford

The same few verbs work on all of them:

    ws create project Thesis        make something that starts here
    ws add person Jane Doe          bring in something from elsewhere
    ws show REF                     look at it, with its relations
    ws edit REF                     change it
    ws delete REF                   remove it and its relations
    ws relate REF to REF as WORDS   connect two of them

You make projects, tasks, resources and profile items with `create`, and add people,
organisations, events, documents and literature with `add`.
