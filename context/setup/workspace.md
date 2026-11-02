EXPLAIN

The workspace is one folder that holds all of this. The ws software stays
apart from it. It starts empty: creating it imports no files, signs in to no
service and makes no records.

ASK

Where should it live? `~/workspace` is the default, and the right answer
unless they have a reason for another place.

RUN

    ws init
    ws init --root DIR
