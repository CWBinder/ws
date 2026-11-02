# The project taxonomy

The taxonomy holds the allowed values for a project's type, fields and
subfields. It is workspace data, kept next to the projects it describes:

```text
~/workspace/projects/project-taxonomy.yaml
```

Show it, or extend it:

```bash
ws projects taxonomy
ws projects add-type dataset
ws projects add-field economics
ws projects add-subfield physics optics
```

Editing the file directly works too, and the creation wizard offers to add
an unknown value when you type one.

The default type is the first value in the list. Fields and subfields
default to empty and are shared with literature. Fields are broad
disciplines; each subfield is stored under one field, and every subfield a
project chooses must belong to a field it chooses. Both may hold several
values. Keywords are free-form and live outside the taxonomy.

Organisations are never classifiers: relate the project to the organisation
instead (`ws help relate`).

A new type gets every setup question in the wizard until it is given its
own routing (`ws help create project`).
