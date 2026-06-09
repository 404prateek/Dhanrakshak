# SHAP-based human-readable risk explanation

from __future__ import annotations

from typing import Any, List, Literal, Sequence, TypedDict

import numpy as np
import shap


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

Direction = Literal["increases_risk", "decreases_risk"]


class FeatureContribution(TypedDict):
    feature: str
    impact: float       # absolute SHAP value, rounded to 6 d.p.
    direction: Direction


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

class SHAPExplainer:
    """
    Wraps the SHAP library to produce top-N human-readable feature
    contributions for any sklearn-compatible model.

    Explainer selection
    -------------------
    * ``TreeExplainer``   — used automatically for tree-based models
      (IsolationForest, RandomForest, GradientBoosting, XGBoost, LightGBM).
    * ``LinearExplainer`` — used for linear models (LogisticRegression, Ridge …).
    * ``KernelExplainer`` — universal fallback; requires a background dataset
      passed to ``explain()`` (or pre-set via ``set_background()``).

    Positive SHAP values push the prediction *higher* (increases risk).
    Negative SHAP values push the prediction *lower* (decreases risk).

    Usage
    -----
    explainer = SHAPExplainer(top_n=3)
    contributions = explainer.explain(
        model=isolation_forest_model,
        feature_vector=np.array([...]),
        feature_names=BehaviorFeatureExtractor.FEATURE_NAMES,
    )
    # [
    #   {"feature": "typing_rhythm_variance", "impact": 0.312, "direction": "increases_risk"},
    #   {"feature": "transaction_speed",      "impact": 0.198, "direction": "decreases_risk"},
    #   {"feature": "idle_ratio",             "impact": 0.091, "direction": "increases_risk"},
    # ]
    """

    # sklearn class-name substrings that map to a specific SHAP explainer.
    _TREE_MODELS = (
        "IsolationForest", "RandomForest", "GradientBoosting",
        "ExtraTree", "DecisionTree", "XGB", "LGBM", "CatBoost",
    )
    _LINEAR_MODELS = (
        "LogisticRegression", "LinearSVC", "Ridge", "Lasso",
        "ElasticNet", "SGD",
    )

    def __init__(self, top_n: int = 3) -> None:
        """
        Parameters
        ----------
        top_n : Number of top contributing features to return.
        """
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        self.top_n = top_n
        self._background: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Optional background dataset for KernelExplainer
    # ------------------------------------------------------------------

    def set_background(self, background: np.ndarray) -> None:
        """
        Provide a background (reference) dataset for KernelExplainer.
        Not needed for tree or linear models.

        Parameters
        ----------
        background : 2-D array of shape (N, F) representing typical inputs.
        """
        arr = np.asarray(background, dtype=np.float32)
        if arr.ndim != 2:
            raise ValueError("background must be a 2-D array of shape (N, F).")
        self._background = arr

    # ------------------------------------------------------------------
    # Explainer factory
    # ------------------------------------------------------------------

    def _build_explainer(
        self, model: Any, feature_vector_2d: np.ndarray
    ) -> shap.Explainer:
        """Choose the most appropriate SHAP explainer for *model*."""
        class_name: str = type(model).__name__

        if any(name in class_name for name in self._TREE_MODELS):
            return shap.TreeExplainer(model)

        if any(name in class_name for name in self._LINEAR_MODELS):
            background = (
                self._background
                if self._background is not None
                else feature_vector_2d  # single-point masker fallback
            )
            return shap.LinearExplainer(model, background)

        # Universal fallback — KernelExplainer requires a background dataset.
        if self._background is None:
            raise RuntimeError(
                f"KernelExplainer is required for {class_name!r} but no background "
                "dataset has been set. Call set_background(X_train_sample) first."
            )
        return shap.KernelExplainer(model.predict, self._background)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(
        self,
        model: Any,
        feature_vector: np.ndarray,
        feature_names: Sequence[str],
    ) -> List[FeatureContribution]:
        """
        Compute SHAP values for *feature_vector* and return the top-N
        most impactful features with human-readable direction labels.

        Parameters
        ----------
        model          : Any fitted sklearn-compatible estimator.
        feature_vector : 1-D array of shape (F,) or 2-D of shape (1, F).
        feature_names  : Sequence of F feature name strings.  Must match
                         the order used during model training.

        Returns
        -------
        List of up to ``top_n`` ``FeatureContribution`` dicts, sorted by
        descending absolute SHAP impact.

        Raises
        ------
        ValueError   : If feature_vector length != len(feature_names).
        RuntimeError : If KernelExplainer is needed but no background is set.
        """
        vec = np.asarray(feature_vector, dtype=np.float32)
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        elif vec.shape[0] != 1:
            raise ValueError(
                "feature_vector must be a single sample: shape (F,) or (1, F)."
            )

        n_features = vec.shape[1]
        if n_features != len(feature_names):
            raise ValueError(
                f"feature_vector has {n_features} features but "
                f"feature_names has {len(feature_names)} entries."
            )

        explainer = self._build_explainer(model, vec)
        shap_values = explainer.shap_values(vec)

        # shap_values may be:
        #   - ndarray (n_samples, n_features)          — regression / single output
        #   - list of ndarrays                          — multi-class / multi-output
        # For binary classifiers we take class-1 (positive/risk class).
        if isinstance(shap_values, list):
            raw = np.asarray(shap_values[-1])   # last class = positive class
        else:
            raw = np.asarray(shap_values)

        values: np.ndarray = raw.flatten()[:n_features]  # (F,)

        # Rank by absolute magnitude descending, keep top_n.
        abs_values = np.abs(values)
        top_indices = np.argsort(abs_values)[::-1][: self.top_n]

        contributions: List[FeatureContribution] = []
        for idx in top_indices:
            shap_val = float(values[idx])
            contributions.append(
                FeatureContribution(
                    feature=str(feature_names[idx]),
                    impact=round(abs(shap_val), 6),
                    direction=(
                        "increases_risk" if shap_val >= 0 else "decreases_risk"
                    ),
                )
            )

        return contributions
