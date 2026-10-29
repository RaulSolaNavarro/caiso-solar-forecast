"""Shared helpers for the data pulls: paths, secrets, HTTP with retry, logging, CSV writing.

Secrets rule: API keys are read from .env and must never appear in output.
Every log line and every network error message passes through `redact()`,
which replaces any known key value with ***.
"""
import logging
import os
import sys
import time
from pathlib import Path

import truststore

# Use the Windows certificate store, so HTTPS works behind antivirus TLS scanning (Norton).
truststore.inject_into_ssl()

import requests  # noqa: E402  (import after truststore so it picks up the Windows store)
from dotenv import dotenv_values  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
# DATA_RAW_DIR lets a test run write to an empty folder instead of data/raw (see run_all.py).
RAW_DIR = Path(os.environ.get("DATA_RAW_DIR") or REPO_ROOT / "data" / "raw")
CACHE_DIR = RAW_DIR / ".cache"
LOG_DIR = CACHE_DIR / "logs"

START_DEFAULT = "2024-01-01"
END_DEFAULT = "2026-10-17"

_SECRET_NAMES = ("EIA_API_KEY", "NLR_API_KEY")
_secrets: list[str] = []


def _load_secrets() -> dict:
    values = dotenv_values(REPO_ROOT / ".env")
    for name in _SECRET_NAMES:
        v = values.get(name) or os.environ.get(name)
        if v and v not in _secrets:
            _secrets.append(v)
    return values


def get_key(name: str) -> str:
    """Return an API key from .env. Raises if missing, without showing any value."""
    v = _load_secrets().get(name) or os.environ.get(name)
    if not v:
        raise RuntimeError(f"{name} is not set in .env")
    return v


def redact(text) -> str:
    """Replace every known secret in text with ***."""
    s = str(text)
    if not _secrets:
        _load_secrets()
    for secret in _secrets:
        s = s.replace(secret, "***")
    return s


class _RedactFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class PullError(Exception):
    """A network or API failure, with any secret removed from the message."""


def _redacting_excepthook(exc_type, exc, tb):
    import traceback
    sys.stderr.write(redact("".join(traceback.format_exception(exc_type, exc, tb))))


def get_logger(name: str) -> logging.Logger:
    """Logger that writes to the console and to data/raw/.cache/logs/<name>.log, always redacted.

    Also makes uncaught crash reports pass through redact().
    """
    sys.excepthook = _redacting_excepthook
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        handler.addFilter(_RedactFilter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # urllib3's own debug and retry messages print full URLs (with keys); keep them quiet.
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    return logger


def http_get(url: str, params: dict | None = None, logger: logging.Logger | None = None,
             retries: int = 5, timeout: int = 120, backoff: float = 5.0) -> requests.Response:
    """GET with retry on 429, 5xx, timeouts and connection errors.

    Any exception raised is a PullError whose message has secrets replaced by ***.
    The original exception is not chained, because its text can contain the key.
    """
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        else:
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code != 429 and r.status_code < 500:
                break  # client error, retrying will not help
        wait = backoff * 2 ** (attempt - 1) if attempt < retries else 0
        if logger:
            logger.warning("attempt %d/%d failed (%s); waiting %.0f s", attempt, retries, redact(last), wait)
        time.sleep(wait)
    raise PullError(redact(f"GET {url} failed: {last}")) from None


def write_csv(df, path: Path, **kwargs) -> None:
    """Write a CSV (or .csv.gz) as UTF-8 with \\n line endings, via a temp file so partial writes never remain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    compression = "gzip" if path.suffix == ".gz" else None
    df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n", compression=compression, **kwargs)
    with open(tmp, "rb+") as fh:
        os.fsync(fh.fileno())
    tmp.replace(path)


def write_bytes_atomic(data: bytes, path: Path) -> None:
    """Write bytes via a temp file and rename, so an interruption never leaves a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def check_hourly(df, time_col: str, start: str, end: str, value_cols: list[str],
                 path: Path, group_cols: list[str] | None = None) -> tuple[str, list]:
    """Brief checks 1, 2, 3, 5 and 6 for an hourly UTC table.

    Returns a markdown check table and the list of missing UTC hours.
    Raw values are not changed: numbers are parsed on a copy, only to compute statistics.
    """
    import pandas as pd

    t = pd.to_datetime(df[time_col], utc=True, format="mixed")
    expected = pd.date_range(f"{start} 00:00", f"{end} 23:00", freq="h", tz="UTC")
    groups = [()] if not group_cols else list(df.groupby(group_cols).groups)
    n_groups = len(groups)
    if group_cols:
        dup = int(df.assign(_t=t).duplicated(group_cols + ["_t"]).sum())
    else:
        dup = int(t.duplicated().sum())
    missing = expected.difference(pd.DatetimeIndex(t.unique()))
    rows = [
        ("1. Rows / expected", f"{len(df):,} / {len(expected) * n_groups:,} ({len(expected):,} hours x {n_groups} series)"),
        ("1. Missing hours", f"{len(missing)} ({len(missing) / len(expected):.2%})"),
        ("2. Duplicate timestamps", f"{dup}"),
        ("3. First / last timestamp (UTC)", f"{t.min():%Y-%m-%d %H:%M} / {t.max():%Y-%m-%d %H:%M}"),
        ("3. Requested range (UTC)", f"{expected[0]:%Y-%m-%d %H:%M} / {expected[-1]:%Y-%m-%d %H:%M}"),
    ]
    for c in df.columns:
        nulls = int((df[c].isna() | (df[c].astype(str).str.strip() == "")).sum())
        rows.append((f"5. Nulls in `{c}`", f"{nulls}"))
    for c in value_cols:
        v = pd.to_numeric(df[c], errors="coerce")
        rows.append((f"5. `{c}` min / median / max", f"{v.min():,.1f} / {v.median():,.1f} / {v.max():,.1f}"))
        rows.append((f"5. `{c}` negative values", f"{int((v < 0).sum())}"))
    size = path.stat().st_size
    rows.append(("6. File size", f"{size / 1e6:.2f} MB ({size:,} bytes)"))
    table = "| Check | Result |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)
    return table, list(missing)


def add_date_args(parser) -> None:
    parser.add_argument("--start", default=START_DEFAULT, help="first day, YYYY-MM-DD (UTC)")
    parser.add_argument("--end", default=END_DEFAULT, help="last day, inclusive, YYYY-MM-DD (UTC)")
