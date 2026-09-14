"""The derivation, checked against a published reference rather than against itself.

`dev07-6-2-u3` warns that bespoke construction is where a protocol goes wrong quietly, and `ado6-sr2`
answers it by naming one: HKDF, RFC 5869. The answer is only worth anything if the implementation is
*verified* rather than merely intended — so the RFC's own test vectors are here, and they are what
makes implementing a published construction a different act from inventing one.
"""

import pytest

from plumb import identity


# -- RFC 5869 Appendix A ------------------------------------------------------------------------
#
# Vectors A.1–A.3, the SHA-256 cases. A.4–A.7 are SHA-1 and do not apply. Written out rather than
# generated, because a vector computed by the code it checks is not a vector.

RFC_5869 = [
    # A.1 — basic
    dict(
        ikm=bytes.fromhex("0b" * 22),
        salt=bytes.fromhex("000102030405060708090a0b0c"),
        info=bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
        length=42,
        prk=bytes.fromhex("077709362c2e32df0ddc3f0dc47bba63"
                          "90b6c73bb50f9c3122ec844ad7c2b3e5"),
        okm=bytes.fromhex("3cb25f25faacd57a90434f64d0362f2a"
                          "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
                          "34007208d5b887185865"),
    ),
    # A.2 — longer inputs and outputs
    dict(
        ikm=bytes.fromhex("".join(f"{i:02x}" for i in range(0x50))),
        salt=bytes.fromhex("".join(f"{i:02x}" for i in range(0x60, 0xb0))),
        info=bytes.fromhex("".join(f"{i:02x}" for i in range(0xb0, 0x100))),
        length=82,
        prk=bytes.fromhex("06a6b88c5853361a06104c9ceb35b45c"
                          "ef760014904671014a193f40c15fc244"),
        okm=bytes.fromhex("b11e398dc80327a1c8e7f78c596a4934"
                          "4f012eda2d4efad8a050cc4c19afa97c"
                          "59045a99cac7827271cb41c65e590e09"
                          "da3275600c2f09b8367793a9aca3db71"
                          "cc30c58179ec3e87c14c01d5c1f3434f"
                          "1d87"),
    ),
    # A.3 — zero-length salt and info
    dict(
        ikm=bytes.fromhex("0b" * 22),
        salt=b"",
        info=b"",
        length=42,
        prk=bytes.fromhex("19ef24a32c717b167f33a91d6f648bdf"
                          "96596776afdb6377ac434c1c293ccb04"),
        okm=bytes.fromhex("8da4e775a563c18f715f802a063c5a31"
                          "b8a11f5c5ee1879ec3454e5f3c738d2d"
                          "9d201395faa4b61a96c8"),
    ),
]


@pytest.mark.proves("ado6", depth="unit")
@pytest.mark.parametrize("vector", RFC_5869, ids=["A.1", "A.2", "A.3"])
def test_the_derivation_matches_the_rfcs_own_vectors(vector):
    """The one thing that separates implementing a published construction from inventing one.

    Both halves are exercised even though only `expand` is used in anger: a caller who one day has
    low-entropy input needs the standard step to reach for, and a step nothing checks is a step
    somebody will quietly get wrong when they finally need it.
    """
    prk = identity.hkdf_extract(vector["salt"], vector["ikm"])
    assert prk == vector["prk"], "HKDF-Extract disagrees with RFC 5869"
    okm = identity.hkdf_expand(prk, vector["info"], vector["length"])
    assert okm == vector["okm"], "HKDF-Expand disagrees with RFC 5869"


@pytest.mark.proves("ado6", depth="unit")
def test_a_label_carrying_a_separator_cannot_collide_two_purposes():
    """The encoding fault this replaced, stated as the thing it must not do.

    Joining a domain and a label with a separator gives one string for two different pairs the
    moment a label may contain it — and a label is the one part of this an adopter picks. The
    failure is silent and total: two purposes share a key and nothing anywhere reports it.
    """
    root = identity.new_root()
    # Under `f"{domain}:{label}"` these two are the same string.
    one = identity.derive(root, b"a", "b:c")
    two = identity.derive(root, b"a:b", "c")
    assert one != two, "two purposes derived the same key — the separator is ambiguous"


@pytest.mark.proves("ado6", depth="unit")
def test_labels_give_one_root_a_key_per_writer():
    """`ado6-sr2`'s reason for existing: a build matrix shares one secret and holds distinct keys,
    because a counter is a serialisation point and a matrix racing for one next value would refuse
    all but one of them."""
    root = identity.new_root()
    keys = {identity.derive(root, identity.SIGNING_DOMAIN, label)
            for label in ("default", "ci-linux", "ci-macos")}
    assert len(keys) == 3, "labels are what make several writers hold different keys"
    assert identity.derive(root, identity.SIGNING_DOMAIN, "default") == \
        identity.derive(root, identity.SIGNING_DOMAIN, "default"), "and derivation is stable"


@pytest.mark.proves("ado6", depth="unit")
def test_the_digest_key_is_not_a_signing_key():
    """Different purposes, different keys, from the one root — which is the whole of the node."""
    root = identity.new_root()
    assert identity.digest_key(root) != identity.derive(root, identity.SIGNING_DOMAIN, "default")


@pytest.mark.proves("ado6", depth="unit")
def test_a_root_is_generated_and_never_read_by_a_person():
    """`ado6-sr1`: 32 bytes from a CSPRNG, and the encoding exists for a secret store rather than
    for a sentence — so it round-trips exactly and says so when it does not."""
    root = identity.new_root()
    assert len(root) == identity.ROOT_BYTES
    assert identity.decode_root(identity.encode_root(root)) == root
    assert identity.new_root() != identity.new_root(), "generated, not derived from anything"

    with pytest.raises(ValueError) as refused:
        identity.decode_root("beef")
    assert "32 bytes" in str(refused.value), "a refusal names the shape it wanted"


@pytest.mark.proves("ado6", depth="unit")
def test_a_short_root_is_refused_rather_than_stretched():
    """There is no stretching left to do. A value too small to be a root is a mistake, and the one
    thing this must not do is quietly accept it and derive from it anyway."""
    with pytest.raises(ValueError):
        identity.derive(b"too short", identity.SIGNING_DOMAIN, "default")
