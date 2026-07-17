import hashlib
import hmac

import pytest

from services import portale_allievi_tokens as tokens


def test_due_token_dello_stesso_allievo_non_sono_indovinabili():
    first = tokens.issue_portal_token(7, now=1_700_000_000)
    second = tokens.issue_portal_token(7, now=1_700_000_000)

    assert first != second
    assert tokens.verify_portal_token(first, now=1_700_000_001).allievo_id == 7
    assert tokens.verify_portal_token(second, now=1_700_000_001).allievo_id == 7


def test_emissione_usa_un_nonce_crittograficamente_casuale(monkeypatch):
    calls = []

    def fake_token_urlsafe(size):
        calls.append(size)
        return "nonce-csprng-controllato-1234567890"

    monkeypatch.setattr(tokens.secrets, "token_urlsafe", fake_token_urlsafe)

    token = tokens.issue_portal_token(7, now=1_700_000_000)

    assert calls == [24]
    assert tokens.verify_portal_token(token, now=1_700_000_001).allievo_id == 7


def test_token_scaduto_rifiutato():
    token = tokens.issue_portal_token(7, now=1_700_000_000, ttl_seconds=60)

    with pytest.raises(tokens.InvalidPortalToken, match="scaduto"):
        tokens.verify_portal_token(token, now=1_700_000_060)


def test_token_manomesso_rifiutato():
    token = tokens.issue_portal_token(7, now=1_700_000_000)
    version, payload, signature = token.split(".")
    tampered = f"{version}.{payload[:-1]}A.{signature}"

    with pytest.raises(tokens.InvalidPortalToken, match="firma"):
        tokens.verify_portal_token(tampered, now=1_700_000_001)


@pytest.mark.parametrize("malformed", ["é.eA.AA", "v1.é.AA"])
def test_token_unicode_malformato_rifiutato(malformed):
    with pytest.raises(tokens.InvalidPortalToken, match="malformato"):
        tokens.verify_portal_token(malformed, now=1_700_000_001)


def test_vecchio_token_deterministico_non_e_piu_accettato():
    old_token = hashlib.sha256(b"7mario@example.com19675").hexdigest()[:32]

    with pytest.raises(tokens.InvalidPortalToken):
        tokens.verify_portal_token(old_token, now=1_700_000_001)


def test_firma_confrontata_in_constant_time(monkeypatch):
    token = tokens.issue_portal_token(7, now=1_700_000_000)
    original_compare_digest = hmac.compare_digest
    calls = []

    def recording_compare_digest(received, expected):
        calls.append((received, expected))
        return original_compare_digest(received, expected)

    monkeypatch.setattr(tokens.hmac, "compare_digest", recording_compare_digest)

    assert tokens.verify_portal_token(token, now=1_700_000_001).allievo_id == 7
    assert len(calls) == 1
    assert isinstance(calls[0][0], bytes)
    assert len(calls[0][0]) == len(calls[0][1]) == 32


def test_firma_errata_attraversa_comunque_compare_digest(monkeypatch):
    token = tokens.issue_portal_token(7, now=1_700_000_000)
    version, payload, signature = token.split(".")
    invalid_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    original_compare_digest = hmac.compare_digest
    calls = []

    def recording_compare_digest(received, expected):
        calls.append((received, expected))
        return original_compare_digest(received, expected)

    monkeypatch.setattr(tokens.hmac, "compare_digest", recording_compare_digest)

    with pytest.raises(tokens.InvalidPortalToken, match="firma"):
        tokens.verify_portal_token(
            f"{version}.{payload}.{invalid_signature}", now=1_700_000_001
        )

    assert len(calls) == 1
    assert len(calls[0][0]) == len(calls[0][1]) == 32
