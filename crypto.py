"""
Crypto Core — Argon2id key derivation + AES-256-GCM encryption,
password strength scoring, and secure password generation.
"""
import os, json, base64, string, re, secrets

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import C, ARG_ITERS, ARG_MEM, ARG_LANES, KEY_BYTES

# ─────────────────────────── Crypto Core ───────────────────────────

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return Argon2id(salt=salt, length=KEY_BYTES,
                    iterations=ARG_ITERS, lanes=ARG_LANES,
                    memory_cost=ARG_MEM).derive(passphrase.encode())

def _encrypt(plaintext: str, passphrase: str) -> str:
    """Encrypt a string → opaque base64 token."""
    salt  = os.urandom(16)
    nonce = os.urandom(12)
    ct    = AESGCM(_derive_key(passphrase, salt)).encrypt(nonce, plaintext.encode(), None)
    blob  = {"v":3,"kdf":"Argon2id","alg":"AES-256-GCM",
             "i":ARG_ITERS,"m":ARG_MEM,"l":ARG_LANES,
             "s":base64.b64encode(salt).decode(),
             "n":base64.b64encode(nonce).decode(),
             "c":base64.b64encode(ct).decode()}
    return base64.b64encode(json.dumps(blob).encode()).decode()

def _decrypt(token: str, passphrase: str) -> str:
    """Decrypt a token produced by _encrypt."""
    b   = json.loads(base64.b64decode(token.encode()).decode())
    key = Argon2id(salt=base64.b64decode(b["s"]), length=KEY_BYTES,
                   iterations=b["i"], lanes=b["l"],
                   memory_cost=b["m"]).derive(passphrase.encode())
    pt  = AESGCM(key).decrypt(base64.b64decode(b["n"]),
                               base64.b64decode(b["c"]), None)
    return pt.decode()

# ─────────────────────────── Strength ───────────────────────────

def pw_strength(pw: str):
    if not pw: return 0, "—", C["subtext"]
    s = min(len(pw)*3, 30)
    for pat in [r'[a-z]',r'[A-Z]',r'\d',r'[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]']:
        if re.search(pat, pw): s += 10
    if len(set(pw)) > 10: s += 10
    if len(pw) >= 20:     s += 10
    if len(set(pw))*len(pw) > 500: s += 5
    s = min(s, 100)
    if s < 30: return s, "Very Weak",  C["danger"]
    if s < 50: return s, "Weak",       C["amber"]
    if s < 70: return s, "Fair",       C["warning"]
    if s < 85: return s, "Strong",     C["success"]
    return s,            "Excellent",  C["accent"]

# ─────────────────────────── Generator ───────────────────────────

def gen_password(length=20, upper=True, lower=True,
                 digits=True, symbols=True, no_amb=True) -> str:
    pool, req = "", []
    amb = "0O1lI|"
    def add(chars):
        nonlocal pool
        if no_amb: chars = ''.join(c for c in chars if c not in amb)
        pool += chars
        if chars: req.append(secrets.choice(chars))
    if lower:   add(string.ascii_lowercase)
    if upper:   add(string.ascii_uppercase)
    if digits:  add(string.digits)
    if symbols: add("!@#$%^&*()-_=+[]{}|;:,.<>?")
    if not pool: pool = string.ascii_letters + string.digits
    rest = [secrets.choice(pool) for _ in range(length - len(req))]
    pw = req + rest; secrets.SystemRandom().shuffle(pw)
    return ''.join(pw)
