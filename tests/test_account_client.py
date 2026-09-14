

# -- the support receiver's account routes (wire v2) --------------------------------------------

def test_the_support_wire_signature_is_timestamped_and_self_naming():
    """The support wire signs METHOD·PATH·TIMESTAMP·sha256(body) and the header carries the
    public half beside the signature, because the receiver has no account yet to look one up in —
    which is the whole reason these routes are signed rather than credentialled."""
    import hashlib
    from plumb import account_client, identity

    secret = identity.new_root()
    who = identity.Identity(secret)
    body = b'{"public": "x", "email": "someone@example.org"}'

    headers = account_client.signed_wire2(who, "POST", "/account", body)

    public, _, signature = headers["Plumb-Signature"].partition(".")
    assert public == who.public, "the header names the key that signed"
    stamp = headers["Plumb-Timestamp"]
    assert stamp.endswith("Z") and "T" in stamp, "ISO-8601 UTC, the wire's own spelling"
    message = f"POST\n/account\n{stamp}\n{hashlib.sha256(body).hexdigest()}".encode()
    assert identity.verify(public, signature, message)


def test_the_series_scheme_and_the_support_scheme_stay_two_functions():
    """One function wearing two signature schemes is how a request carries the wrong one and
    reads as an attack; the seam is two names, checked here so it cannot quietly refold."""
    from plumb import account_client

    assert account_client.signed is not account_client.signed_wire2
    import inspect
    assert "Plumb-Counter" not in inspect.getsource(account_client.signed_wire2)
    assert "Plumb-Timestamp" not in inspect.getsource(account_client.signed)
