"""
Crypto core — Argon2id for passphrases, AES-256-GCM for data.

Passphrase tokens (v3) wrap the vault key, the 2FA file, exports, and the
Encrypt tab. Entry fields use a fast v4 token: the data key is already high
entropy, so each field is AES-GCM only (no Argon2).
"""
import os, json, base64, string, re, secrets, hashlib, struct, math

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import C, ARG_ITERS, ARG_MEM, ARG_LANES, KEY_BYTES

_FIELD_AAD_PREFIX = b"LocalPasswordVault.field.v4\0"
_FILE_MAGIC = b"LPVF"
_FILE_VERSION = 1
_FILE_CHUNK = 1024 * 1024

_COMMON_PASSWORDS = {
    "password", "password1", "password123", "123456", "12345678", "123456789",
    "qwerty", "letmein", "admin", "welcome", "iloveyou", "monkey", "dragon",
    "master", "abc123", "trustno1", "passw0rd", "changeme", "secret",
}


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return Argon2id(
        salt=salt, length=KEY_BYTES,
        iterations=ARG_ITERS, lanes=ARG_LANES, memory_cost=ARG_MEM,
    ).derive(passphrase.encode())


def _encrypt(plaintext: str, passphrase: str) -> str:
    """Encrypt a string with Argon2id + AES-256-GCM. Opaque base64 token."""
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ct = AESGCM(_derive_key(passphrase, salt)).encrypt(nonce, plaintext.encode(), None)
    blob = {
        "v": 3, "kdf": "Argon2id", "alg": "AES-256-GCM",
        "i": ARG_ITERS, "m": ARG_MEM, "l": ARG_LANES,
        "s": base64.b64encode(salt).decode(),
        "n": base64.b64encode(nonce).decode(),
        "c": base64.b64encode(ct).decode(),
    }
    return base64.b64encode(json.dumps(blob).encode()).decode()


def _load_blob(token: str) -> dict:
    return json.loads(base64.b64decode(token.encode()))


def field_version(token: str) -> int | None:
    """Return the token version, or None if it is not a vault blob."""
    if not token:
        return None
    try:
        return int(_load_blob(token).get("v"))
    except Exception:
        return None


def _decrypt(token: str, passphrase: str) -> str:
    """Decrypt a v3 passphrase token produced by _encrypt."""
    blob = _load_blob(token)
    if int(blob.get("v", 0)) >= 4:
        raise ValueError("not a passphrase token")
    key = Argon2id(
        salt=base64.b64decode(blob["s"]), length=KEY_BYTES,
        iterations=blob["i"], lanes=blob["l"], memory_cost=blob["m"],
    ).derive(passphrase.encode())
    pt = AESGCM(key).decrypt(
        base64.b64decode(blob["n"]), base64.b64decode(blob["c"]), None,
    )
    return pt.decode()


def field_key(dek: str) -> bytes:
    """Map the high-entropy DEK string to a 32-byte AES key. Not a password KDF."""
    if not isinstance(dek, str) or len(dek) < 16:
        raise ValueError("invalid data key")
    return hashlib.sha256(_FIELD_AAD_PREFIX + dek.encode("utf-8")).digest()


def _field_aad(column: str) -> bytes:
    if not column or not re.fullmatch(r"[a-z0-9_]+", column):
        raise ValueError("invalid field")
    return _FIELD_AAD_PREFIX + column.encode("ascii")


def encrypt_field(plaintext: str, dek: str, column: str) -> str:
    """AES-256-GCM field token (v4). Column name is authenticated so blobs cannot be swapped."""
    key = field_key(dek)
    nonce = os.urandom(12)
    raw = (plaintext or "").encode("utf-8")
    body = struct.pack(">I", len(raw)) + raw
    pad = 32 - (len(body) % 32)
    body += bytes([pad]) * pad
    ct = AESGCM(key).encrypt(nonce, body, _field_aad(column))
    blob = {
        "v": 4, "alg": "AES-256-GCM",
        "n": base64.b64encode(nonce).decode(),
        "c": base64.b64encode(ct).decode(),
    }
    return base64.b64encode(json.dumps(blob).encode()).decode()


def decrypt_field(token: str, dek: str, column: str) -> str:
    """Decrypt a v4 field token, or a legacy v3 token keyed by the DEK string."""
    if not token:
        return ""
    blob = _load_blob(token)
    if int(blob.get("v", 0)) >= 4:
        key = field_key(dek)
        pt = AESGCM(key).decrypt(
            base64.b64decode(blob["n"]),
            base64.b64decode(blob["c"]),
            _field_aad(column),
        )
        if len(pt) < 4:
            raise ValueError("truncated field")
        n = struct.unpack(">I", pt[:4])[0]
        if n > len(pt) - 4:
            raise ValueError("bad field length")
        return pt[4:4 + n].decode("utf-8")
    return _decrypt(token, dek)


def _file_header(salt: bytes) -> bytes:
    return (
        _FILE_MAGIC
        + bytes([_FILE_VERSION])
        + struct.pack(">III", ARG_ITERS, ARG_MEM, ARG_LANES)
        + salt
    )


def encrypt_file(src: str, dst: str, passphrase: str) -> None:
    """Encrypt any file. One Argon2id pass, then 1 MiB AES-GCM chunks."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError("Input and output must be different files")
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    header = _file_header(salt)
    tmp = dst + ".partial"
    try:
        with open(src, "rb") as fin, open(tmp, "wb") as fout:
            fout.write(header)
            index = 0
            while True:
                chunk = fin.read(_FILE_CHUNK)
                last = len(chunk) < _FILE_CHUNK
                flags = 1 if last else 0
                nonce = os.urandom(12)
                aad = header + struct.pack(">IB", index, flags)
                ct = AESGCM(key).encrypt(nonce, chunk, aad)
                fout.write(bytes([flags]))
                fout.write(struct.pack(">I", index))
                fout.write(struct.pack(">I", len(ct)))
                fout.write(nonce)
                fout.write(ct)
                if last:
                    break
                index += 1
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def decrypt_file(src: str, dst: str, passphrase: str) -> None:
    """Decrypt a file produced by encrypt_file."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError("Input and output must be different files")
    tmp = dst + ".partial"
    try:
        with open(src, "rb") as fin:
            magic = fin.read(4)
            if magic != _FILE_MAGIC:
                raise ValueError("not an encrypted file")
            version = fin.read(1)
            if version != bytes([_FILE_VERSION]):
                raise ValueError("unsupported file version")
            iters, mem, lanes = struct.unpack(">III", fin.read(12))
            salt = fin.read(16)
            if len(salt) != 16:
                raise ValueError("truncated file header")
            header = magic + version + struct.pack(">III", iters, mem, lanes) + salt
            key = Argon2id(
                salt=salt, length=KEY_BYTES,
                iterations=iters, lanes=lanes, memory_cost=mem,
            ).derive(passphrase.encode())
            with open(tmp, "wb") as fout:
                index = 0
                while True:
                    flag_b = fin.read(1)
                    if not flag_b:
                        raise ValueError("truncated file")
                    flags = flag_b[0]
                    got_index = struct.unpack(">I", fin.read(4))[0]
                    ct_len = struct.unpack(">I", fin.read(4))[0]
                    nonce = fin.read(12)
                    ct = fin.read(ct_len)
                    if got_index != index or len(nonce) != 12 or len(ct) != ct_len:
                        raise ValueError("truncated or reordered file")
                    if ct_len > _FILE_CHUNK + 64:
                        raise ValueError("chunk too large")
                    aad = header + struct.pack(">IB", index, flags)
                    pt = AESGCM(key).decrypt(nonce, ct, aad)
                    fout.write(pt)
                    if flags & 1:
                        break
                    index += 1
                if fin.read(1):
                    raise ValueError("trailing data")
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def pw_strength(pw: str):
    """Heuristic score. Common passwords, repeats, and sequences are penalized."""
    if not pw:
        return 0, "—", C["subtext"]
    lower = pw.lower()
    folded = re.sub(r"[^a-z0-9]", "", lower)
    if lower in _COMMON_PASSWORDS or folded in _COMMON_PASSWORDS:
        return 5, "Very Weak", C["danger"]

    score = min(len(pw) * 2, 30)
    classes = 0
    for pat in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"):
        if re.search(pat, pw):
            classes += 1
    score += classes * 10
    if len(set(pw)) >= 8:
        score += 8
    if len(pw) >= 16:
        score += 8
    if len(pw) >= 24:
        score += 6
    if len(pw) < 10:
        score -= 12
    if re.search(r"(.)\1{2,}", pw):
        score -= 15
    if re.search(r"(012|123|234|345|456|567|678|789|abc|bcd|cde|qwe|asd|zxc)", lower):
        score -= 12
    half = len(pw) // 2
    if half >= 4 and pw[:half] == pw[half:half * 2]:
        score -= 20
    score = max(0, min(100, score))
    if score < 30:
        return score, "Very Weak", C["danger"]
    if score < 50:
        return score, "Weak", C["amber"]
    if score < 70:
        return score, "Fair", C["warning"]
    if score < 85:
        return score, "Strong", C["success"]
    return score, "Excellent", C["accent"]


def passphrase_entropy_bits(word_count: int, vocabulary: int) -> float:
    """Entropy of a uniform draw from a word list, in bits."""
    if word_count <= 0 or vocabulary <= 1:
        return 0.0
    return word_count * math.log2(vocabulary)


def gen_password(length=20, upper=True, lower=True,
                 digits=True, symbols=True, no_amb=True) -> str:
    pool, req = "", []
    amb = "0O1lI|"

    def add(chars):
        nonlocal pool
        if no_amb:
            chars = "".join(c for c in chars if c not in amb)
        pool += chars
        if chars:
            req.append(secrets.choice(chars))

    if lower:
        add(string.ascii_lowercase)
    if upper:
        add(string.ascii_uppercase)
    if digits:
        add(string.digits)
    if symbols:
        add("!@#$%^&*()-_=+[]{}|;:,.<>?")
    if not pool:
        pool = string.ascii_letters + string.digits
    length = max(int(length), len(req), 1)
    rest = [secrets.choice(pool) for _ in range(length - len(req))]
    pw = req + rest
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)
