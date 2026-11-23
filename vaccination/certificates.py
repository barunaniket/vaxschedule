"""FR-005 / NFR-001: HMAC-signed QR certificates and verification."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

import qrcode
import qrcode.image.svg

from .registration import get_citizen
from .rules import NotFoundError, RuleViolation, is_fully_vaccinated
from .scheduling import doses_taken

FULL = "FULLY VACCINATED"
PARTIAL = "PARTIALLY VACCINATED"


def _sign(secret, payload):
    key = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def issue_certificate(conn, secret, citizen_id):
    """Sign and store a certificate for the doses given so far."""
    citizen = get_citizen(conn, citizen_id)
    doses = doses_taken(conn, citizen_id)
    if not doses:
        raise RuleViolation("No doses recorded yet, so no certificate.")
    vaccine = doses[0]["vaccine"]
    body = {
        "cid": citizen["id"],
        "name": citizen["name"],
        "id_last4": citizen["id_number"][-4:],
        "vaccine": vaccine,
        "doses": [{"n": d["dose_number"], "date": d["date_given"],
                   "batch": d["batch"]} for d in doses],
        "status": FULL if is_fully_vaccinated(vaccine, len(doses))
        else PARTIAL,
    }
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    issued = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            "INSERT INTO certificates (citizen_id, payload, signature, "
            "issued_at) VALUES (?, ?, ?, ?)",
            (citizen_id, payload, _sign(secret, payload), issued))
    return cur.lastrowid


def latest_certificate(conn, citizen_id):
    """Most recent certificate, or ``NotFoundError``."""
    row = conn.execute(
        "SELECT * FROM certificates WHERE citizen_id = ? "
        "ORDER BY id DESC LIMIT 1", (citizen_id,)).fetchone()
    if row is None:
        raise NotFoundError("No certificate has been issued yet.")
    return row


def qr_token(cert_row):
    """``base64url(payload) + "." + signature`` (padding stripped)."""
    body = base64.urlsafe_b64encode(cert_row["payload"].encode())
    return body.decode().rstrip("=") + "." + cert_row["signature"]


def qr_svg(token):
    """Inline SVG QR code for the token."""
    img = qrcode.make(token, image_factory=qrcode.image.svg.SvgPathImage)
    return img.to_string(encoding="unicode")


def verify_token(secret, token):
    """Return the certificate data if the signature is valid, else None.

    Needs only the key, not the database.
    """
    token = (token or "").strip()
    body, _, signature = token.rpartition(".")
    if not body or not signature:
        return None
    try:
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        payload = payload.decode()
    except ValueError:  # bad base64 or bad UTF-8
        return None
    expected = _sign(secret, payload)
    if not hmac.compare_digest(expected.encode(), signature.encode()):
        return None
    return json.loads(payload)
