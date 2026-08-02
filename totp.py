"""
App-level 2FA: RFC 6238 TOTP engine, recovery-code helpers, and the
TwoFactorManager that owns localpasswordvault.2fa.
"""
import os, json, base64, time, hmac, hashlib, struct, secrets

from config import TFA_FILE, APP_TITLE
from crypto import _encrypt, _decrypt

# ─────────────────────────── TOTP Engine (RFC 6238) ───────────────────────────

def _totp_code(secret_b32: str, ts: int = None) -> str:
    """
    Generate a 6-digit TOTP code from a base32 secret.
    Pure stdlib — no pyotp needed.
    Returns the code string, seconds remaining in this window, and progress 0-1.
    """
    secret_b32 = secret_b32.upper().strip()
    # Pad to valid base32 length
    pad = (8 - len(secret_b32) % 8) % 8
    secret_bytes = base64.b32decode(secret_b32 + "=" * pad)
    now      = ts if ts is not None else int(time.time())
    step     = 30
    counter  = now // step
    # HMAC-SHA1 of the 8-byte big-endian counter
    msg      = struct.pack(">Q", counter)
    h        = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset   = h[-1] & 0x0F
    code_int = struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF
    code     = str(code_int % 1_000_000).zfill(6)
    remaining = step - (now % step)
    progress  = remaining / step
    return code, remaining, progress

def _totp_valid(secret_b32: str) -> bool:
    """Return True if the secret looks like a valid base32 TOTP secret."""
    try:
        secret_b32 = secret_b32.upper().strip().rstrip("=")
        if not secret_b32: return False
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
        if not all(c in valid_chars for c in secret_b32): return False
        pad = (8 - len(secret_b32) % 8) % 8
        base64.b32decode(secret_b32 + "=" * pad)
        return len(secret_b32) >= 16   # minimum sensible secret length
    except Exception:
        return False

# ─────────────────────────── Recovery Code Helpers ───────────────────────────

def _gen_recovery_codes(n: int = 10) -> list:
    """Generate n recovery codes in A3KP-9XMZ-Q72W format (3 groups of 4, alphanumeric)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    codes = []
    seen  = set()
    while len(codes) < n:
        parts = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
        code  = "-".join(parts)
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _hash_recovery_code(code: str) -> str:
    """Store a SHA-256 hash of the normalised code so originals aren't in DB."""
    normalised = code.upper().replace("-", "").strip()
    return hashlib.sha256(normalised.encode()).hexdigest()


def _check_recovery_code(code: str, stored_hashes: list) -> int:
    """
    Check a user-supplied code against stored hashes.
    Returns index of matching hash, or -1 if no match.
    """
    normalised = code.upper().replace("-", "").strip()
    h = hashlib.sha256(normalised.encode()).hexdigest()
    for i, stored in enumerate(stored_hashes):
        if hmac.compare_digest(h, stored):
            return i
    return -1


# ─────────────────────────── App-level 2FA Manager ───────────────────────────

class TwoFactorManager:
    """
    Manages the localpasswordvault.2fa file and all app-level 2FA operations.

    File format (JSON, AES-256-GCM encrypted with master password):
    {
      "v": 1,
      "totp_secret": "<base32 secret>",
      "recovery_hashes": ["<sha256>", ...],    # hashed, not plaintext
      "recovery_used": [false, false, ...],     # parallel array
      "codes_enabled": true,
      "account_name": "LocalPasswordVault"
    }

    The file is encrypted with the master password using _encrypt()/_decrypt(),
    so an attacker needs: .db file + .2fa file + master password.
    """

    def __init__(self):
        self._secret: str | None  = None   # base32 TOTP secret, in RAM only after unlock
        self._data:   dict | None = None   # full decrypted JSON payload

    # ── File presence ──

    @staticmethod
    def enabled() -> bool:
        """2FA is active only when a completed setup file exists."""
        if not os.path.exists(TFA_FILE):
            return False
        try:
            return os.path.getsize(TFA_FILE) > 32
        except OSError:
            return False

    @staticmethod
    def discard_file():
        """Remove the .2fa file (disable app-level 2FA on disk)."""
        try:
            os.remove(TFA_FILE)
        except FileNotFoundError:
            pass

    def cancel_setup(self):
        """Abandon an in-progress setup wizard — no 2FA file should remain."""
        self.unload()
        self.discard_file()

    # ── Setup (deferred write until wizard finishes) ──

    def begin_setup(self) -> tuple:
        """
        Generate TOTP secret + recovery codes in memory only.
        Does NOT write localpasswordvault.2fa — call commit_setup() after the wizard completes.
        Returns (totp_secret, recovery_codes_plaintext, qr_uri).
        """
        secret = base64.b32encode(os.urandom(20)).decode().rstrip("=")
        codes  = _gen_recovery_codes(10)
        hashes = [_hash_recovery_code(c) for c in codes]
        self._secret = secret
        self._data   = {
            "v": 1,
            "totp_secret": secret,
            "recovery_hashes": hashes,
            "recovery_used": [False] * 10,
            "codes_enabled": True,
            "account_name": APP_TITLE,
            "setup_complete": False,
        }
        uri = self._build_uri(secret, APP_TITLE)
        return secret, codes, uri

    def commit_setup(self, master: str) -> bool:
        """Persist 2FA after the user finishes the setup wizard."""
        if not self._data or not self._secret:
            return False
        self._data["setup_complete"] = True
        self._write(self._data, master)
        return True

    def is_committed(self, master: str) -> bool:
        """True when a finished 2FA setup is on disk (not an abandoned wizard)."""
        if not self.enabled():
            return False
        try:
            with open(TFA_FILE, "r") as f:
                token = f.read().strip()
            payload = json.loads(_decrypt(token, master))
            return bool(payload.get("setup_complete"))
        except Exception:
            return False

    # ── Unlock / load ──

    def load(self, master: str) -> bool:
        """Decrypt and load .2fa file. Returns False if missing, incomplete, or wrong password."""
        if not self.enabled():
            return False
        try:
            with open(TFA_FILE, "r") as f:
                token = f.read().strip()
            payload = json.loads(_decrypt(token, master))
            if not payload.get("setup_complete"):
                # Incomplete / abandoned setup — do not block login
                self.discard_file()
                self.unload()
                return False
            self._data   = payload
            self._secret = payload["totp_secret"]
            return True
        except Exception:
            return False

    def unload(self):
        self._secret = None
        self._data   = None

    # ── TOTP verification ──

    def verify_totp(self, code: str) -> bool:
        """Accept code for current window ±1 (30s grace)."""
        if not self._secret:
            return False
        code = code.strip().replace(" ", "")
        now = int(time.time())
        for delta in (-1, 0, 1):
            expected, _, _ = _totp_code(self._secret, now + delta * 30)
            if hmac.compare_digest(code, expected):
                return True
        return False

    # ── Recovery code verification ──

    def verify_recovery_code(self, code: str, master: str) -> bool:
        """
        Consume a recovery code (one-time use).
        Marks it used, persists immediately. Returns True on success.
        """
        if not self._data:
            return False
        if not self._data.get("codes_enabled", True):
            return False
        hashes = self._data.get("recovery_hashes", [])
        used   = self._data.get("recovery_used", [])
        idx    = _check_recovery_code(code, hashes)
        if idx < 0:
            return False
        if idx < len(used) and used[idx]:
            return False   # already consumed
        # Consume
        used[idx] = True
        self._data["recovery_used"] = used
        self._write(self._data, master)
        return True

    def recovery_codes_remaining(self) -> int:
        if not self._data:
            return 0
        used = self._data.get("recovery_used", [])
        return sum(1 for u in used if not u)

    # ── Settings operations (all require fresh TOTP verification) ──

    def regenerate_recovery_codes(self, master: str, totp_code: str) -> list | None:
        """Regenerate all 10 codes. Returns new plaintext codes, or None on bad code."""
        if not self.verify_totp(totp_code):
            return None
        codes  = _gen_recovery_codes(10)
        hashes = [_hash_recovery_code(c) for c in codes]
        self._data["recovery_hashes"] = hashes
        self._data["recovery_used"]   = [False] * 10
        self._data["codes_enabled"]   = True
        self._write(self._data, master)
        return codes

    def disable_recovery_codes(self, master: str, totp_code: str) -> bool:
        """Disable recovery codes entirely. Returns True on success."""
        if not self.verify_totp(totp_code):
            return False
        self._data["codes_enabled"] = False
        self._write(self._data, master)
        return True

    def enable_recovery_codes(self, master: str, totp_code: str) -> list | None:
        """Re-enable (and regenerate) recovery codes."""
        if not self.verify_totp(totp_code):
            return None
        codes  = _gen_recovery_codes(10)
        hashes = [_hash_recovery_code(c) for c in codes]
        self._data["recovery_hashes"] = hashes
        self._data["recovery_used"]   = [False] * 10
        self._data["codes_enabled"]   = True
        self._write(self._data, master)
        return codes

    def disable_2fa(self, master: str, totp_code: str, confirm_word: str) -> bool:
        """
        Fully disable 2FA — deletes the .2fa file.
        Requires valid TOTP code AND confirm_word == 'DISABLE'.
        Returns True on success.
        """
        if confirm_word.strip().upper() != "DISABLE":
            return False
        if not self.verify_totp(totp_code):
            return False
        try:
            os.remove(TFA_FILE)
        except FileNotFoundError:
            pass
        self.unload()
        return True

    # ── QR / transfer ──

    def get_transfer_uri(self) -> str | None:
        """Return otpauth:// URI for QR code display (no auth needed — already unlocked)."""
        if not self._secret:
            return None
        return self._build_uri(self._secret, "LocalPasswordVault")

    def get_secret(self) -> str | None:
        return self._secret

    def codes_enabled(self) -> bool:
        if not self._data:
            return False
        return self._data.get("codes_enabled", True)

    # ── Internal ──

    def _write(self, data: dict, master: str):
        token = _encrypt(json.dumps(data), master)
        # Write atomically via temp file
        tmp = TFA_FILE + ".tmp"
        with open(tmp, "w") as f:
            f.write(token)
        os.replace(tmp, TFA_FILE)

    @staticmethod
    def _build_uri(secret: str, account: str) -> str:
        import urllib.parse
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        return (f"otpauth://totp/{urllib.parse.quote(account)}"
                f"?secret={padded}&issuer={urllib.parse.quote(APP_TITLE)}"
                f"&algorithm=SHA1&digits=6&period=30")


tfa = TwoFactorManager()
