So far this has been about storing things. The brain has a second job, which is to
tell your agent what it needs to know.

A model is the same for everyone. It knows nothing about you, beyond a few crumbs
that made it into its training data, and each session starts from nothing. The only
thing you can change is what it reads. That is what makes an agent yours. OpenClaw
works the same way: your agent there is a set of Markdown files and a memory, read
into a fresh model each time it starts.

Here, a session that starts inside the workspace runs `ws context`, and ws tells it
where it is, the rules there, what the place is for, what is due and what last
happened. A program puts this together from your records and notes, so it comes out
the same way every time. Then the model takes it from there: deterministic memory
hands over to latent space.

That is why the workspace, each store, and each project, resource and paper can hold
a `.context/` folder. A deeper place adds to the ones above it, so an agent in a
project gets the workspace's rules, the project's own rules, its purpose, its log and
what it is connected to. It starts with what this place needs, not with everything,
and it can search and follow relations for the rest.
