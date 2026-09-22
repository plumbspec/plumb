# tomli — vendored

`tomli` 2.4.1, unmodified, MIT (see `LICENSE`). This is the parser that became `tomllib` in
Python 3.11: the same code by the same author, so a project below 3.11 gets the same reading of
its `plumb.toml` as one above it rather than an approximation of it.

**Read `plumb.config` before changing anything here.** The standard library is preferred wherever
it exists, so on 3.11 and up not a line of this is imported.

**Why not a smaller parser of our own.** Plumb needs the whole of TOML, because the file is the
adopter's and they write what TOML lets them write. A reader that handles the subset this project
happens to use would misread a valid file quietly, which is the one failure a configuration reader
must not have. Writing the primitive ourselves is what `dev07-6-2-u3` records as where a format
goes wrong without anybody noticing.

Updating it: copy the release wholesale, keep this file and `LICENSE`, change nothing else.
