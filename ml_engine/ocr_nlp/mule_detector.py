"""
mule_detector.py
----------------
Offline mule-account detector for DhanRakshak.

Uses a local SQLite database to track address reuse across loan
applications.  No external API or internet required — fully air-gapped.

This catches the classic Canara Bank mule-account fraud pattern:
  • Multiple applicants list the same residential address
  • The address is rented to a "mule" who takes loans on behalf of
    a kingpin and immediately defaults / transfers funds

Classes
-------
MuleAccountDetector
    check_address(address, applicant_name, case_id)  →  risk dict
    register_address(address, applicant_name, case_id)
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

_DEFAULT_DB = (
    Path(__file__).resolve().parent.parent          # ml_engine/
    / "training" / "checkpoints" / "address_registry.db"
)

# ---------------------------------------------------------------------------
# Address normalisation helpers
# ---------------------------------------------------------------------------

# Common abbreviation expansions (applied BEFORE stripping punctuation)
_ABBREV: Dict[str, str] = {
    r"\bsect(?:or)?\b":   "sector",
    r"\bst\b":            "street",
    r"\brd\b":            "road",
    r"\bave?\b":          "avenue",
    r"\bnr\b":            "near",
    r"\bopp\b":           "opposite",
    r"\bapt\b":           "apartment",
    r"\bflr\b":           "floor",
    r"\bsoc(?:iety)?\b":  "society",
    r"\bnag(?:ar)?\b":    "nagar",
    r"\bcol(?:ony)?\b":   "colony",
    r"\bext(?:ension)?\b":"extension",
    r"\bph(?:ase)?\b":    "phase",
    r"\bdist\b":          "district",
    r"\bvil\b":           "village",
    r"\bblk\b":           "block",
    r"\bplt\b":           "plot",
    r"\bflat\b":          "flat",
    r"\bno\b":            "",           # "No." → drop
}

# State name aliases → canonical
_STATE_ALIASES: Dict[str, str] = {
    "up": "uttar pradesh", "mh": "maharashtra", "ka": "karnataka",
    "tn": "tamil nadu", "wb": "west bengal", "dl": "delhi",
    "rj": "rajasthan", "gj": "gujarat", "mp": "madhya pradesh",
    "hr": "haryana", "pb": "punjab", "br": "bihar",
    "od": "odisha", "or": "odisha", "jk": "jammu and kashmir",
    "ap": "andhra pradesh", "ts": "telangana", "kl": "kerala",
    "as": "assam", "jh": "jharkhand", "cg": "chhattisgarh",
    "hp": "himachal pradesh", "uk": "uttarakhand",
}


def _normalize_address(raw: str) -> str:
    """
    Return a canonical, comparable form of an address string so that
    variant spellings of the same address produce the same key.

    Pipeline
    --------
    1. Unicode → ASCII
    2. Lowercase
    3. Replace ALL separators (hyphen, dot, comma, slash) with spaces
       "A-12"      → "a 12"
       "Sector-5"  → "sector 5"
       "Sector5"   — kept as-is (no separator to split)
    4. Expand common abbreviations  (sect → sector, rd → road …)
    5. Drop state names / abbreviations (UP, Maharashtra …) — they appear
       inconsistently across submissions and would break equality.
    6. Drop pincodes — stored separately; don't pollute the key.
    7. Strip any remaining punctuation, collapse whitespace
    8. Sort tokens for order-independence
       "Flat 3 Block A" == "Block A Flat 3"
    """
    # 1. Unicode normalise → ASCII
    text = unicodedata.normalize("NFKD", raw)
    text = text.encode("ascii", "ignore").decode("ascii")

    # 2. Lowercase
    text = text.lower()

    # 3. Replace all common separators uniformly with spaces
    text = re.sub(r"[\-,./\\#|]", " ", text)

    # 3b. Insert a space at letter↔digit boundaries so that
    #     "a12" (no hyphen) becomes "a 12" matching "a-12" → "a 12"
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text)

    # 4. Expand abbreviations
    for pattern, replacement in _ABBREV.items():
        text = re.sub(pattern, " " + replacement + " ", text, flags=re.IGNORECASE)

    # 5. Drop state abbreviations and canonical state name tokens
    _DROP_TOKENS = (
        set(_STATE_ALIASES.keys())          # "up", "mh", "dl" …
        | {"uttar", "pradesh", "west", "bengal", "tamil", "nadu",
           "madhya", "andhra", "himachal", "jammu", "kashmir",
           "maharashtra", "karnataka", "rajasthan", "gujarat",
           "haryana", "punjab", "bihar", "odisha", "telangana",
           "kerala", "assam", "jharkhand", "chhattisgarh",
           "uttarakhand", "delhi"}
    )
    tokens = [tok for tok in text.split() if tok not in _DROP_TOKENS]
    text = " ".join(tokens)

    # 6. Drop 6-digit pincodes (handled by _extract_pincode separately)
    text = re.sub(r"\b[1-9]\d{5}\b", "", text)

    # 7. Strip remaining punctuation, collapse whitespace
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())

    # 8. Sort tokens for order-independence
    return " ".join(sorted(text.split()))


# ---------------------------------------------------------------------------
# Pincode validation (offline lookup — top 5 states + Delhi)
# ---------------------------------------------------------------------------
#
# Each Indian state has a distinct pincode prefix range.
# Source: India Post zone allocations (public domain).
#
# Structure: {state_canonical: [(start, end), ...]}

_PINCODE_RANGES: Dict[str, List[Tuple[int, int]]] = {
    "uttar pradesh":   [(200000, 285999)],
    "maharashtra":     [(400000, 445999)],
    "karnataka":       [(560000, 591999)],
    "tamil nadu":      [(600000, 643999)],
    "west bengal":     [(700000, 743999)],
    "delhi":           [(110000, 110099)],
    "rajasthan":       [(301000, 345999)],
    "gujarat":         [(360000, 396999)],
    "madhya pradesh":  [(450000, 488999)],
    "haryana":         [(121000, 136999)],
    "punjab":          [(140000, 160999)],
    "bihar":           [(800000, 855999)],
    "odisha":          [(751000, 770999)],
    "andhra pradesh":  [(500000, 535999)],
    "telangana":       [(500000, 509999)],
    "kerala":          [(670000, 695999)],
    "assam":           [(781000, 788999)],
    "jharkhand":       [(814000, 835999)],
    "chhattisgarh":    [(490000, 497999)],
    "himachal pradesh":[(171000, 177999)],
    "uttarakhand":     [(246000, 263999)],
}

_PINCODE_RE = re.compile(r"\b([1-9]\d{5})\b")


def _extract_pincode(address: str) -> Optional[str]:
    m = _PINCODE_RE.search(address)
    return m.group(1) if m else None


def _extract_state(address: str) -> Optional[str]:
    """Return canonical state name if detectable in raw address."""
    lower = address.lower()
    # Try full names first
    for canonical in _PINCODE_RANGES:
        if canonical in lower:
            return canonical
    # Try abbreviations
    words = re.findall(r"\b[a-z]+\b", lower)
    for w in words:
        if w in _STATE_ALIASES:
            return _STATE_ALIASES[w]
    return None


def _validate_pincode(pincode: Optional[str], state: Optional[str]) -> bool:
    """
    Return True if the pincode falls within the state's known range,
    or True when either value is unknown (can't disprove).
    """
    if not pincode or not state:
        return True   # insufficient info — assume valid
    try:
        pin_int = int(pincode)
    except ValueError:
        return True
    ranges = _PINCODE_RANGES.get(state)
    if not ranges:
        return True   # state not in our table — assume valid
    return any(lo <= pin_int <= hi for lo, hi in ranges)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

def _mule_score(count: int, pincode_valid: bool) -> float:
    """
    Continuous mule risk score in [0, 1].

    count = number of OTHER applicants at same address.
    """
    if count == 0:
        base = 0.0
    elif count == 1:
        base = 0.55
    elif count == 2:
        base = 0.80
    else:
        base = min(0.80 + 0.05 * (count - 2), 0.98)

    # Invalid pincode adds a penalty on top
    penalty = 0.10 if not pincode_valid else 0.0
    return round(min(base + penalty, 1.0), 4)


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.40:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# MuleAccountDetector
# ---------------------------------------------------------------------------


class MuleAccountDetector:
    """
    Offline mule-account detector backed by a local SQLite database.

    All operations are thread-safe via a per-instance lock.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  Created automatically if it
        does not exist.  Defaults to
        ``ml_engine/training/checkpoints/address_registry.db``.
    """

    _CREATE_SQL = """
        CREATE TABLE IF NOT EXISTS address_registry (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_address         TEXT    NOT NULL,
            normalized_address  TEXT    NOT NULL,
            pincode             TEXT,
            state               TEXT,
            applicant_name      TEXT    NOT NULL,
            case_id             TEXT    NOT NULL,
            registered_at       TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_norm_addr
            ON address_registry(normalized_address);
        CREATE INDEX IF NOT EXISTS idx_case_id
            ON address_registry(case_id);
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent writes
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(self._CREATE_SQL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_address(
        self,
        address: str,
        applicant_name: str,
        case_id: str,
    ) -> None:
        """
        Store an address in the registry for future duplicate detection.

        Idempotent: re-registering the same case_id updates the record
        rather than creating a duplicate.
        """
        normalized = _normalize_address(address)
        pincode    = _extract_pincode(address)
        state      = _extract_state(address)
        now        = datetime.utcnow().isoformat()

        with self._lock, self._connect() as conn:
            # Upsert by case_id — prevent double-counting retries
            existing = conn.execute(
                "SELECT id FROM address_registry WHERE case_id = ?", (case_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE address_registry
                       SET raw_address=?, normalized_address=?, pincode=?,
                           state=?, applicant_name=?, registered_at=?
                       WHERE case_id=?""",
                    (address, normalized, pincode, state, applicant_name, now, case_id),
                )
                logger.debug("Updated address for case_id=%s", case_id)
            else:
                conn.execute(
                    """INSERT INTO address_registry
                       (raw_address, normalized_address, pincode, state,
                        applicant_name, case_id, registered_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (address, normalized, pincode, state, applicant_name, case_id, now),
                )
                logger.debug("Registered address for case_id=%s", case_id)

    def check_address(
        self,
        address: str,
        applicant_name: str,
        case_id: str,
    ) -> Dict:
        """
        Check an address for mule-account risk, then auto-register it.

        Parameters
        ----------
        address:        Raw address string from the application.
        applicant_name: Full name of the current applicant.
        case_id:        Unique identifier for this loan application.

        Returns
        -------
        dict:
            mule_risk         : str   — LOW / MEDIUM / HIGH
            same_address_count: int   — other applicants at this address
            other_case_ids    : list  — [(case_id, applicant_name), ...]
            pincode_valid     : bool
            pincode           : str | None
            state_detected    : str | None
            mule_score        : float — 0 clean → 1 near-certain mule
            normalized_address: str   — for audit trail
            flags             : list[str]
        """
        normalized = _normalize_address(address)
        pincode    = _extract_pincode(address)
        state      = _extract_state(address)
        pin_valid  = _validate_pincode(pincode, state)

        flags: List[str] = []

        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """SELECT case_id, applicant_name
                   FROM address_registry
                   WHERE normalized_address = ?
                     AND case_id            != ?""",
                (normalized, case_id),
            ).fetchall()

        other_cases = [(r["case_id"], r["applicant_name"]) for r in rows]
        count       = len(other_cases)
        score       = _mule_score(count, pin_valid)
        level       = _risk_level(score)

        # Build flags
        if count >= 2:
            flags.append(
                f"HIGH: Address shared by {count} other applicant(s) — "
                f"strong mule account indicator"
            )
        elif count == 1:
            name = other_cases[0][1]
            flags.append(
                f"MEDIUM: Address already registered by '{name}' "
                f"(case {other_cases[0][0]})"
            )

        if not pin_valid:
            flags.append(
                f"MEDIUM: Pincode {pincode} does not match state "
                f"'{state}' — address may be fabricated"
            )

        # Auto-register so this case participates in future checks
        self.register_address(address, applicant_name, case_id)

        return {
            "mule_risk":          level,
            "same_address_count": count,
            "other_case_ids":     other_cases,
            "pincode_valid":      pin_valid,
            "pincode":            pincode,
            "state_detected":     state,
            "mule_score":         score,
            "normalized_address": normalized,
            "flags":              flags,
        }

    def list_all(self) -> List[Dict]:
        """Return all registered addresses (useful for admin / audit)."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM address_registry ORDER BY registered_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def reset_db(self) -> None:
        """
        Drop and recreate the registry.
        USE WITH CAUTION — deletes all history.
        """
        with self._lock, self._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS address_registry")
            conn.executescript(self._CREATE_SQL)
        logger.warning("address_registry.db has been reset.")
