"""Plumb — proof that a story is done."""

#: Reported in a manifest's provenance (``dev07-3-1``) so a reader can tell which build observed a
#: fact. Static pre-1.0 and deliberately not read from package metadata: this must work from a
#: source checkout, where no metadata exists.
#: What this line of work is heading for. The **only** place a version is authored: what a build
#: actually is gets derived from the commit it was cut at (`tools/product.Product.derived_version`)
#: and stamped into the artifact, because a version restated in three files is three facts that
#: drift and nothing compares them.
BASE_VERSION = "0.8.1"

try:  # written into the artifact at build time; absent in a checkout, which is not a build
    from plumb._built import VERSION as __version__
except ImportError:
    __version__ = BASE_VERSION
