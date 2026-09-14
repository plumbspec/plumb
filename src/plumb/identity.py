"""The identity a self-provisioned account is named by (``ado6``).

An identity is **one root key**: 32 bytes from a CSPRNG, generated once. Everything else an account
uses derives from it under a label — a signing key per concurrent writer, and the key that
pseudonymises a history. So a host rebuilt every build is handed one secret and derives its own
signing key from it: nothing to distribute, nothing to commit, nothing to regenerate.

**It is a key and not a passphrase, and that is the whole of what changed here.** This module used
to generate a passphrase and stretch it with scrypt into a root. Both halves of that were
compensating for a human choosing badly — a work factor and a salt exist to make a low-entropy guess
expensive — and nothing here is chosen by a human. The stretching therefore defended nobody while
costing every unattended run, and the derivation sat outside primitives that are named and tested.

**HKDF, and implemented rather than imported.** RFC 5869 is a published construction with published
test vectors, so an implementation can be *checked* rather than trusted because it was written
carefully — which is the distinction `dev07-6-2-u3` turns on when it warns against bespoke assembly. It is
implemented here over stdlib HMAC because `cryptography` is a compiled package that cannot enter the
single-file artifact (`ado1`), and pulling it into the derivation path would make pseudonymising a
history depend on a wheel that has to build.

**Purposes are length-prefixed, never joined.** A label that contained the separator would otherwise
collide two purposes into one key — an encoding fault wearing crypto's clothes, and the kind that
reads as correct right up until it does not.

**Ed25519 is not in the standard library**, and this package declares no runtime dependencies — a
claim that is load-bearing, because it is what makes a single-file zipapp viable. So the *signing*
back end is an optional extra, and its absence is reported as this installation's own fault with the
command that repairs it (``ado1``), never as a fault in the adopter's project.
"""

import hashlib
import hmac
import secrets

#: The root's size. 256 bits from the OS, which is what HKDF is being handed and what an Ed25519
#: private key is built from — one number rather than three that have to agree.
ROOT_BYTES = 32

#: Domain separation for what derives from the root (``ado6-sr2``). Settled **before** anything is
#: registered: a label enters the wire contract the moment it names a key somebody holds, and
#: changing one afterwards orphans every key derived under it.
SIGNING_DOMAIN = b"plumb-signing-v2"
DIGEST_DOMAIN = b"plumb-digest-v2"

#: The label a signing key carries when the adopter names none. Fixed, so the ordinary
#: single-writer case needs no vocabulary at all.
DEFAULT_LABEL = "default"


class Unavailable(RuntimeError):
    """The signing back end is not installed. Plumb's own fault to name, not the project's."""


def _backend():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as missing:  # pragma: no cover - exercised by an install without the extra
        raise Unavailable(
            "plumb: this installation cannot sign, so it cannot use a self-provisioned account.\n"
            "  The signing back end ships as an extra, because Plumb's runtime declares no\n"
            "  dependencies and Ed25519 is not in the standard library.\n"
            "  Repair it with:  pip install 'plumbspec[account]'\n"
            "  Nothing about your project is wrong; this is Plumb's own install."
        ) from missing
    return ed25519


# -- RFC 5869 ---------------------------------------------------------------------------------

def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """RFC 5869 §2.2. Present so the vectors can exercise it, and so a future caller with
    low-entropy input has the standard step to reach for rather than inventing one."""
    return hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int = 32) -> bytes:
    """RFC 5869 §2.3."""
    if length > 255 * 32:
        raise ValueError("HKDF-Expand: length exceeds 255 * HashLen")
    out, block, counter = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def _purpose(domain: bytes, label: str) -> bytes:
    """``info`` for one derived key, encoded so two purposes cannot collide.

    Length-prefixed rather than joined by a separator: `f"{domain}:{label}"` gives the same bytes
    for two different pairs the moment a label may contain the separator, and a label is the one
    part of this an adopter chooses.
    """
    name = label.encode("utf-8")
    return bytes([len(domain)]) + domain + len(name).to_bytes(2, "big") + name


def derive(root: bytes, domain: bytes, label: str = "") -> bytes:
    """One purpose's own 32 bytes, from the root and nothing else (``ado6-sr2``).

    **Expand without extract**, which RFC 5869 §3.3 permits and this case satisfies: extraction
    exists to concentrate entropy that is unevenly spread, and the root is already 32 uniformly
    random bytes from the OS. Running it anyway would be ceremony, not strength.
    """
    if len(root) < ROOT_BYTES:
        raise ValueError(f"a root is {ROOT_BYTES} bytes; got {len(root)}")
    return hkdf_expand(root, _purpose(domain, label))


# -- the identity -------------------------------------------------------------------------------

def new_root() -> bytes:
    """The one secret. Generated, never chosen, and never shown to anybody by default."""
    return secrets.token_bytes(ROOT_BYTES)


def encode_root(root: bytes) -> str:
    """The form a root travels in when somebody deliberately asks for it (``ado6-ur5``).

    Hex, because it survives a config file, an environment variable and a terminal without anything
    helpfully re-encoding it — and because nobody has to read it aloud, so the encoding is ours to
    pick for the machine rather than for a person.
    """
    return root.hex()


def decode_root(text: str) -> bytes:
    """A root back from the form it travelled in, or ``ValueError`` naming what is wrong."""
    raw = bytes.fromhex(text.strip())
    if len(raw) != ROOT_BYTES:
        raise ValueError(f"a root is {ROOT_BYTES} bytes ({ROOT_BYTES * 2} hex characters); "
                         f"this is {len(raw)}")
    return raw


class Identity:
    """A keypair derived from the root. The private half never leaves this process.

    ``label`` selects **which** signing key, so several concurrent writers share one root and still
    hold distinct keys — which is what per-key counters need and what a build matrix has by default
    (``ado6-sr2``).
    """

    def __init__(self, root: bytes, label: str = DEFAULT_LABEL):
        ed25519 = _backend()
        self.label = label
        self._private = ed25519.Ed25519PrivateKey.from_private_bytes(
            derive(root, SIGNING_DOMAIN, label))
        self.public = public_hex(self._private)

    def sign(self, message: bytes) -> str:
        return self._private.sign(message).hex()


def digest_key(root: bytes) -> bytes:
    """The key a series pseudonymises with (``dev07-6-2``), derived **once** at creation.

    Derived here and *carried* by whoever holds the account rather than recomputed on every run
    (``ado6-sr3``). Two events can replace a root and they want opposite things: one rotated on
    compromise should reset the pseudonym, because a compromised root has already lost it; one
    replaced because the old is gone should not, because nothing was breached and resetting renames
    every subject in an adopter's own history for nothing.
    """
    return derive(root, DIGEST_DOMAIN)


def public_hex(private) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return raw.hex()


def verify(public: str, signature: str, message: bytes) -> bool:
    """Whether this key signed this message. The only question a verifying end asks (``ado6-nfr2``)."""
    ed25519 = _backend()
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public))
        key.verify(bytes.fromhex(signature), message)
        return True
    except Exception:
        # Any failure is one answer — invalid signature, malformed key, wrong length. Telling them
        # apart tells a caller which half to vary, and none of them is a different outcome here.
        return False


def token(key: bytes, value: str, account: str = "") -> str:
    """An adopter's own name, replaced by something that keeps its identity (``dev07-6-2``).

    Keyed rather than hashed, because test names are compositional English from a small space and a
    bare digest is a dictionary away from the plaintext. Salted with the account so the same name in
    two projects does not collide into one token — free, given the key is already per-adopter, and
    it removes the question rather than leaving it to be reasoned about.
    """
    return hashlib.blake2b(f"{account}:{value}".encode(), key=key, digest_size=16).hexdigest()


def canonical(method: str, path: str, holder: str, counter: int, body: bytes) -> bytes:
    """What a signature covers, in a form both ends build the same way (``ado6-nfr2``).

    Three bindings and each closes a different hole. The **body**, by digest, so an intermediary
    cannot alter what was sent under a valid identity. The **holder**, so a request captured by
    one cannot be presented to another. And the **counter** — this key's place in its own sequence,
    strictly increasing — so a request cannot be replayed. The counter is deliberately not a clock:
    a timestamp needs the two ends to agree about the time, which a runner is entitled to be wrong
    about, and the failure then presents as a refusal indistinguishable from an unknown identity.
    """
    digest = hashlib.blake2b(body, digest_size=32).hexdigest()
    return "\n".join([method.upper(), path, holder, str(counter), digest]).encode()
