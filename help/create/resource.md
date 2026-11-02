# Creating a resource

```bash
ws create resource Workshop materials
```

This makes an empty bundle: the folder `resources/items/<key>/` with its
`resource.yaml`, and nothing else. The title's words are joined, so quotes
are optional. The key is the title in lowercase with hyphens, here
`workshop-materials`; when a key is taken, a number is appended. The
command prints the REF, and every later command needs that REF. What a
bundle is for is in `ws help resources`.

On a terminal, a missing title and a missing description are asked for.
Without a terminal, as when an agent runs ws, nothing is asked: pass the
description and provenance as flags.

`--ensure` returns the existing bundle whose name or one of whose aliases
matches the title, ignoring case, instead of creating a second one.
`ws resources ensure` does the same and prints only the REF.

## Putting files into the bundle

```bash
ws add resource:workshop-materials ~/Downloads/handouts --mode copy
ws add resource:workshop-materials ~/Downloads/hotel.pdf \
  --name receipts/hotel.pdf
```

`ws add resource:<key> PATH` takes a file or a whole folder. By default the
source moves into the bundle; `--mode copy` leaves the original where it
is. It lands at the top of the bundle under its own name, or under the
name `--name` gives, which may include subfolders; they are created as
needed. Any folder structure that helps is fine.

The add is refused, and nothing moves, when the destination already exists
in the bundle, and for the name `resource.yaml`, which is reserved for the
record. The files themselves get no records or REFs; the bundle's
`updated_at` records that its contents changed. Its flags are in
`ws help add resource`.

Check what the bundle now holds:

```bash
ws resources files resource:workshop-materials
```

## Connecting the bundle

Creating a bundle relates it to nothing. Relate it to what it serves, then
refresh the browse views, which creating and relating leave as they were:

```bash
ws relate resource:workshop-materials to project:<key> as supports
ws relate resource:workshop-materials to event:<key> as prepared-for
ws rebuild views resources
```

## Example

The receipts of one trip, collected as they arrive:

```bash
ws create resource Conference travel reimbursement \
  --description "Receipts and claim form for the September conference trip." \
  --source "booking emails" --observed-at 2026-09-20
ws add resource:conference-travel-reimbursement ~/Downloads/train.pdf \
  --name receipts/train.pdf
ws add resource:conference-travel-reimbursement ~/Downloads/claim-form.pdf
ws relate resource:conference-travel-reimbursement to event:<key> \
  as expense-for
```
