# Isolation Forest anomaly detection model

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Optional, Union

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler


# ---------------------------------------------------------------------------
# Environment-variable driven defaults
# ---------------------------------------------------------------------------
# Set DHANRAKSHAK_IF_CONTAMINATION to a float in (0, 0.5] or the string
# "auto" to override the default at runtime without changing source code.
# Example:  $env:DHANRAKSHAK_IF_CONTAMINATION = "0.05"
_ENV_CONTAMINATION = "DHANRAKSHAK_IF_CONTAMINATION"
_DEFAULT_CONTAMINATION: Union[float, str] = "auto"


def _parse_contamination(raw: Optional[str]) -> Union[float, str]:
    """Parse the env-var string into a float or keep 'auto'."""
    if raw is None:
        return _DEFAULT_CONTAMINATION
    raw = raw.strip().lower()
    if raw == "auto":
        return "auto"
    value = float(raw)
    if not 0.0 < value <= 0.5:
        raise ValueError(
            f"{_ENV_CONTAMINATION} must be in (0, 0.5] or 'auto', got {value!r}"
        )
    return value


class BehavioralAnomalyDetector:
    """
    Wraps scikit-learn IsolationForest for behavioral anomaly detection.

    The raw decision-function score is min-max scaled to [0, 1] so that
    ``predict()`` always returns a normalised anomaly probability:
      * score ≈ 0  →  normal / expected behavior
      * score ≈ 1  →  highly anomalous / potential fraud / duress

    The contamination rate (expected fraction of outliers in training data)
    is read from the ``DHANRAKSHAK_IF_CONTAMINATION`` environment variable,
    falling back to ``"auto"`` (sklearn default) when the variable is unset.

    Usage
    -----
    detector = BehavioralAnomalyDetector()
    detector.train(feature_matrix)          # np.ndarray shape (N, 6)
    score = detector.predict(feature_vec)   # float in [0, 1]
    detector.save_model("model.pkl")
    detector.load_model("model.pkl")
    """

    def __init__(
        self,
        n_estimators: int = 100,
        random_state: int = 42,
        contamination: Optional[Union[float, str]] = None,
    ) -> None:
        """
        Parameters
        ----------
        n_estimators  : Number of trees in the forest.
        random_state  : Reproducibility seed.
        contamination : Expected fraction of outliers. When None the value is
                        read from ``DHANRAKSHAK_IF_CONTAMINATION`` env var,
                        defaulting to ``"auto"`` if unset.
        """
        if contamination is None:
            contamination = _parse_contamination(os.environ.get(_ENV_CONTAMINATION))

        self.contamination = contamination
        self._forest = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        # Scaler fitted alongside the forest so scores are always in [0, 1].
        self._scaler = MinMaxScaler(feature_range=(0.0, 1.0))
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, feature_matrix: np.ndarray) -> None:
        """
        Fit the IsolationForest on *feature_matrix*.

        Parameters
        ----------
        feature_matrix : shape (N, F) float array where N ≥ 1 and F is the
                         number of behavioral features (6 from
                         BehaviorFeatureExtractor).
        """
        if feature_matrix.ndim != 2 or feature_matrix.shape[0] < 1:
            raise ValueError(
                "feature_matrix must be a 2-D array with at least one sample."
            )
        self._forest.fit(feature_matrix)

        # Fit the scaler on the raw decision scores of the training set so
        # that future predict() calls are calibrated against the same range.
        raw_scores = self._forest.decision_function(feature_matrix).reshape(-1, 1)
        self._scaler.fit(raw_scores)
        self._fitted = True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, feature_vector: np.ndarray) -> float:
        """
        Return a normalised anomaly score for a single feature vector.

        Parameters
        ----------
        feature_vector : 1-D array of shape (F,) or 2-D of shape (1, F).

        Returns
        -------
        float in [0, 1].
            0 → indistinguishable from normal training data.
            1 → maximally anomalous relative to the training distribution.

        Raises
        ------
        RuntimeError : If the model has not been trained or loaded yet.
        """
        self._check_fitted()

        vec = np.asarray(feature_vector, dtype=np.float32)
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        elif vec.shape[0] != 1:
            raise ValueError(
                "predict() accepts a single feature vector; "
                "pass a 1-D array or shape (1, F)."
            )

        raw_score = self._forest.decision_function(vec).reshape(-1, 1)   # (1, 1)
        # Clip to the scaler's fitted range before transforming to avoid
        # out-of-range extrapolation.
        raw_score = np.clip(raw_score, self._scaler.data_min_, self._scaler.data_max_)
        normalised = float(self._scaler.transform(raw_score)[0, 0])

        # IsolationForest decision_function is positive for inliers and
        # negative for outliers, so we invert: high score = high anomaly.
        return round(1.0 - normalised, 6)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_model(self, path: str) -> None:
        """
        Persist the fitted forest and scaler to *path* using pickle.

        Parameters
        ----------
        path : Destination file path (e.g. ``"checkpoints/if_model.pkl"``).

        Raises
        ------
        RuntimeError : If the model has not been trained yet.
        """
        self._check_fitted()
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "forest": self._forest,
            "scaler": self._scaler,
            "contamination": self.contamination,
        }
        with dest.open("wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)

    def load_model(self, path: str) -> None:
        """
        Restore a previously saved model from *path*.

        Parameters
        ----------
        path : Path to the ``.pkl`` file written by ``save_model()``.

        Raises
        ------
        FileNotFoundError : If *path* does not exist.
        """
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(f"Model file not found: {src}")
        with src.open("rb") as fh:
            payload = pickle.load(fh)  # noqa: S301 — trusted internal checkpoint
        self._forest = payload["forest"]
        self._scaler = payload["scaler"]
        self.contamination = payload["contamination"]
        self._fitted = True

    # ------------------------------------------------------------------
    # Internal guard
    # ------------------------------------------------------------------

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError(
                "Model is not fitted. Call train() or load_model() first."
            )
