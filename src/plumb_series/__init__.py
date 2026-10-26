"""The run history, mounted into the one CLI as a module (``dev08-1-1``–``dev08-1-4``).

**The first module, and it is a real one.** Its verbs reach the CLI through the published mount
and nowhere else: `plumb.cli` names none of them, and removing this package's entry point removes
`plumb series` from the tool without touching the core.

It consumes the core's **series interface** (`plumb.core.series`, version 1) — the format, the
extent, what a read refuses. That is a documented surface with a version it declares against, which
is what `dev08-1-1-ur1` asks of every module.

**What is not yet a surface, said plainly.** Pushing and pulling a history needs the transport the
support client also uses — `plumb.transmit`, and the enrolment and signing under it — and that is
not published, not versioned, and not documented. This module imports it anyway, because the
alternative was carrying a second copy of somebody's credential handling. So this is `dev08-1-1-ur1`
met for the series interface and owed for the transport, which is the next thing to settle and the
reason this module exists before the support one does.
"""

from plumb.core.series import SERIES_VERSION
from plumb.footprint import Wrote
from plumb.modules import Argument, Declaration, Verb

__version__ = "1.0.0"

PROJECT_HELP = "the project whose plumb.toml names the series (default: this directory)"
ENROLMENT_HELP = "the enrolment file to push with (default: the installed one)"


def _push(args) -> int:
    from plumb.cli import cmd_series_push

    return cmd_series_push(args)


def _show(args) -> int:
    from plumb.cli import cmd_series_show

    return cmd_series_show(args)


def _pull(args) -> int:
    from plumb.cli import cmd_series_pull

    return cmd_series_pull(args)


#: What this module says about itself before any of it is mounted (``dev08-1-2``).
DECLARATION = Declaration(
    name="series",
    version=__version__,
    # One surface, one version. The transport it also uses is not on this list because the core
    # publishes no version for it — stated as an absence rather than papered over with a number.
    surfaces={"series": SERIES_VERSION},
    verbs=(
        # One name this module owns, and three commands under it — `plumb series push`, exactly
        # as before. The core never names any of them.
        Verb("series", "the run history a manifest deliberately is not", verbs=(
            Verb("push", "send what the holder has not been given yet", _push, (
                Argument(("file",), {"help": "the series to push"}),
                Argument(("--dry-run",), {"action": "store_true",
                                          "help": "print exactly what would be sent, and send "
                                                  "nothing"}),
                Argument(("--project",), {"metavar": "DIR", "help": PROJECT_HELP}),
                Argument(("--enrolment",), {"help": ENROLMENT_HELP}),
            )),
            Verb("show", "read a history back — when it changed, when we last looked", _show, (
                Argument(("file",), {"help": "the series to read"}),
                Argument(("--subject",), {"help": "one subject's transitions, oldest first, "
                                                  "instead of the summary over all of them"}),
            )),
            Verb("pull", "fetch the history the holder keeps for you", _pull, (
                Argument(("file",), {"help": "where to write it"}),
                Argument(("--subject",), {"help": "which series to ask for (default: "
                                                  "plumb.toml's)"}),
                Argument(("--project",), {"metavar": "DIR", "help": PROJECT_HELP}),
                Argument(("--enrolment",), {"help": ENROLMENT_HELP}),
            )),
        )),
    ),
    # Named where `plumb footprint` will print it, so somebody deciding what to protect sees a
    # history this module wrote even though the core no longer knows it exists. The path is not
    # knowable here — it is whatever the command was given — so `where` says which file it is.
    writes=(
        Wrote("the series file named on the command line",
              "every transition, losslessly — a run that is not recorded cannot be recovered "
              "from a later one", keep=True, irreplaceable=True),
        Wrote("its `.sent` mark, beside it",
              "how far that history has been handed over; a lost mark re-sends what already "
              "arrived, and the holder stores the repeat", keep=True),
    ),
    network=True,
)
