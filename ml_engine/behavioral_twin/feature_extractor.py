# Compute feature vector from raw browser events

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

import numpy as np


# ---------------------------------------------------------------------------
# Expected JSON payload schema (validated at runtime)
# ---------------------------------------------------------------------------
#
# {
#   "keydown":    [{"t": 1700000000123}, ...],          # epoch ms timestamps
#   "mousemove":  [{"t": ..., "x": 320, "y": 240}, ...],
#   "scroll":     [{"t": ..., "dy": 120}, ...],
#   "click":      [{"t": ..., "x": 512, "y": 300}, ...],
#   "session_start_ts": 1700000000000,                   # epoch ms (optional)
#   "transaction_ts":   1700000060000                    # epoch ms (optional)
# }
#
# All timestamp values ("t", "session_start_ts", "transaction_ts") must be
# numeric (milliseconds since Unix epoch).  Missing optional keys default to
# values derived from the event lists themselves.


class BehaviorPayload(TypedDict, total=False):
    keydown: List[Dict[str, Any]]
    mousemove: List[Dict[str, Any]]
    scroll: List[Dict[str, Any]]
    click: List[Dict[str, Any]]
    session_start_ts: float
    transaction_ts: float


# Feature vector index → name mapping (preserved for downstream labelling).
FEATURE_NAMES = [
    "avg_typing_speed",         # 0 — characters per second
    "typing_rhythm_variance",   # 1 — variance of inter-key intervals (ms²)
    "mouse_linearity",          # 2 — ratio of straight-line dist to path len
    "session_duration",         # 3 — total session length in seconds
    "idle_ratio",               # 4 — fraction of session with no events
    "transaction_speed",        # 5 — seconds from session start to first click
]

# Gap threshold (ms) above which a period is classified as "idle".
_IDLE_GAP_MS: float = 2_000.0


class BehaviorFeatureExtractor:
    """
    Converts a raw browser behavioral-event payload into a fixed-length
    numpy feature vector suitable for anomaly-detection models.

    Features (in order, matching ``FEATURE_NAMES``)
    ------------------------------------------------
    0. avg_typing_speed       — mean characters per second across all keydown
                                inter-arrival intervals.
    1. typing_rhythm_variance — variance of consecutive keydown inter-arrival
                                intervals in milliseconds squared.  High values
                                indicate irregular/stressed typing.
    2. mouse_linearity        — Euclidean distance between first and last
                                mouse position divided by the total path
                                length.  1.0 = perfectly straight; near 0 =
                                highly erratic movement.
    3. session_duration       — wall-clock length of the session in seconds.
    4. idle_ratio             — fraction of the session during which no events
                                occurred (inter-event gap > ``_IDLE_GAP_MS``).
    5. transaction_speed      — seconds elapsed between session start and the
                                first click event (proxy for decision speed).

    Usage
    -----
    extractor = BehaviorFeatureExtractor()
    vector = extractor.extract(payload_dict)   # shape: (6,), dtype float32
    """

    def __init__(self, idle_gap_ms: float = _IDLE_GAP_MS) -> None:
        """
        Parameters
        ----------
        idle_gap_ms : Inter-event gap in milliseconds that qualifies as idle.
        """
        self.idle_gap_ms = idle_gap_ms

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamps(events: List[Dict[str, Any]]) -> np.ndarray:
        """Extract sorted 't' timestamps (ms) from an event list."""
        if not events:
            return np.array([], dtype=np.float64)
        return np.sort(np.array([e["t"] for e in events], dtype=np.float64))

    @staticmethod
    def _intervals(ts: np.ndarray) -> np.ndarray:
        """Return consecutive differences of a sorted timestamp array."""
        if ts.size < 2:
            return np.array([], dtype=np.float64)
        return np.diff(ts)

    # --- Feature calculators -------------------------------------------

    def _avg_typing_speed(self, keydown: List[Dict[str, Any]]) -> float:
        """Characters per second based on keydown inter-arrival times."""
        intervals = self._intervals(self._timestamps(keydown))
        if intervals.size == 0:
            return 0.0
        mean_interval_s = float(np.mean(intervals)) / 1_000.0
        return 1.0 / mean_interval_s if mean_interval_s > 0 else 0.0

    def _typing_rhythm_variance(self, keydown: List[Dict[str, Any]]) -> float:
        """Variance of keydown inter-arrival intervals in ms²."""
        intervals = self._intervals(self._timestamps(keydown))
        if intervals.size == 0:
            return 0.0
        return float(np.var(intervals))

    def _mouse_linearity(self, mousemove: List[Dict[str, Any]]) -> float:
        """
        Ratio of straight-line distance to cumulative path length.
        Returns 1.0 when fewer than two points are recorded (degenerate case).
        """
        if len(mousemove) < 2:
            return 1.0

        coords = np.array([[e["x"], e["y"]] for e in mousemove], dtype=np.float64)
        diffs = np.diff(coords, axis=0)                   # (N-1, 2)
        segment_lengths = np.linalg.norm(diffs, axis=1)   # (N-1,)
        total_path = float(segment_lengths.sum())

        if total_path == 0.0:
            return 1.0

        straight_line = float(np.linalg.norm(coords[-1] - coords[0]))
        return min(straight_line / total_path, 1.0)

    def _session_duration(
        self,
        all_ts: np.ndarray,
        session_start: float,
        session_end: float,
    ) -> float:
        """Session length in seconds."""
        return max((session_end - session_start) / 1_000.0, 0.0)

    def _idle_ratio(self, all_ts: np.ndarray, duration_s: float) -> float:
        """
        Fraction of the session spent idle (no events for > idle_gap_ms).
        """
        if all_ts.size < 2 or duration_s == 0.0:
            return 0.0
        intervals = self._intervals(all_ts)
        idle_time_ms = float(intervals[intervals > self.idle_gap_ms].sum())
        idle_time_s = idle_time_ms / 1_000.0
        return min(idle_time_s / duration_s, 1.0)

    def _transaction_speed(
        self,
        click: List[Dict[str, Any]],
        session_start: float,
    ) -> float:
        """Seconds from session start to the first click event."""
        if not click:
            return 0.0
        first_click_ts = float(min(e["t"] for e in click))
        return max((first_click_ts - session_start) / 1_000.0, 0.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, payload: BehaviorPayload) -> np.ndarray:
        """
        Compute the 6-element feature vector from *payload*.

        Parameters
        ----------
        payload : Dict matching ``BehaviorPayload``.  All event list keys
                  default to empty lists when absent.  Timestamp keys default
                  to values derived from the event data.

        Returns
        -------
        np.ndarray, shape (6,), dtype float32
            [avg_typing_speed, typing_rhythm_variance, mouse_linearity,
             session_duration, idle_ratio, transaction_speed]
        """
        keydown:   List[Dict[str, Any]] = payload.get("keydown",   [])
        mousemove: List[Dict[str, Any]] = payload.get("mousemove", [])
        scroll:    List[Dict[str, Any]] = payload.get("scroll",    [])
        click:     List[Dict[str, Any]] = payload.get("click",     [])

        # Aggregate all event timestamps for session-level metrics.
        all_events = keydown + mousemove + scroll + click
        all_ts = self._timestamps(all_events)

        # Resolve session boundaries.
        if all_ts.size > 0:
            derived_start = float(all_ts[0])
            derived_end   = float(all_ts[-1])
        else:
            derived_start = derived_end = 0.0

        session_start = float(payload.get("session_start_ts", derived_start))
        session_end   = float(payload.get("transaction_ts",   derived_end))
        # Ensure end is never before start.
        session_end   = max(session_end, session_start)

        duration_s = self._session_duration(all_ts, session_start, session_end)

        features = np.array([
            self._avg_typing_speed(keydown),
            self._typing_rhythm_variance(keydown),
            self._mouse_linearity(mousemove),
            duration_s,
            self._idle_ratio(all_ts, duration_s),
            self._transaction_speed(click, session_start),
        ], dtype=np.float32)

        return features
