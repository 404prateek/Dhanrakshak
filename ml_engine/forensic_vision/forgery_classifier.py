# EfficientNet-based binary forgery classifier

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights


# ---------------------------------------------------------------------------
# Label mapping
# ---------------------------------------------------------------------------
_IDX_TO_LABEL: Dict[int, str] = {0: "authentic", 1: "forged"}

# ---------------------------------------------------------------------------
# Default inference-time image transforms (matches EfficientNet-B0 training)
# ---------------------------------------------------------------------------
_DEFAULT_TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])


class ForgeryClassifier:
    """
    Binary document-forgery classifier built on a fine-tuned EfficientNet-B0.

    Usage
    -----
    # With a fine-tuned checkpoint:
    clf = ForgeryClassifier(weights_path="checkpoints/forgery_b0.pt")
    clf.load_model()
    result = clf.predict("scan.jpg")
    # {"label": "forged", "confidence": 0.923}

    # Without a checkpoint (ImageNet weights only — for development):
    clf = ForgeryClassifier()
    clf.load_model()
    result = clf.predict("scan.jpg")
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        device: Optional[str] = None,
        transform: Optional[transforms.Compose] = None,
    ) -> None:
        """
        Parameters
        ----------
        weights_path : Path to a saved state-dict (.pt / .pth) produced by
                       the fine-tuning script.  When None the model uses
                       ImageNet-pretrained weights (suitable for development).
        device       : 'cuda', 'mps', or 'cpu'.  Auto-detected when None.
        transform    : Custom torchvision transform pipeline.  Falls back to
                       the standard EfficientNet-B0 pre-processing when None.
        """
        self.weights_path = Path(weights_path) if weights_path else None
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.transform = transform or _DEFAULT_TRANSFORM
        self.model: Optional[nn.Module] = None

    # ------------------------------------------------------------------
    # Model construction helpers
    # ------------------------------------------------------------------

    def _build_backbone(self) -> nn.Module:
        """Return an EfficientNet-B0 with the classifier head replaced for 2 classes."""
        backbone = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
        in_features: int = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(p=0.3, inplace=True),
            nn.Linear(in_features, 2),
        )
        return backbone

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Build the network and load weights.

        * If *weights_path* was supplied and the file exists, the saved
          state-dict is loaded (strict=True).
        * Otherwise the model runs with ImageNet-pretrained backbone weights
          and a randomly initialised classification head (development mode).
        """
        self.model = self._build_backbone().to(self.device)

        if self.weights_path is not None:
            if not self.weights_path.is_file():
                raise FileNotFoundError(
                    f"Weights file not found: {self.weights_path}"
                )
            state_dict = torch.load(
                self.weights_path,
                map_location=self.device,
                weights_only=True,       # safe loading — no arbitrary pickle
            )
            self.model.load_state_dict(state_dict, strict=True)

        self.model.eval()

    def predict(self, image_path: str) -> Dict[str, object]:
        """
        Classify a single document image as authentic or forged.

        Parameters
        ----------
        image_path : Path to the image file (any PIL-readable format).

        Returns
        -------
        dict with keys:
            "label"      : "authentic" | "forged"
            "confidence" : float in (0, 1) — probability assigned to the
                           predicted class.

        Raises
        ------
        RuntimeError   : If load_model() has not been called first.
        FileNotFoundError : If *image_path* does not exist.
        """
        if self.model is None:
            raise RuntimeError("Call load_model() before predict().")

        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Image not found: {img_path}")

        image: Image.Image = Image.open(img_path).convert("RGB")
        tensor: torch.Tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            logits: torch.Tensor = self.model(tensor)          # (1, 2)
            probabilities: torch.Tensor = torch.softmax(logits, dim=1)  # (1, 2)
            confidence, predicted_idx = probabilities.max(dim=1)

        label: str = _IDX_TO_LABEL[int(predicted_idx.item())]
        confidence_value: float = round(float(confidence.item()), 6)

        return {"label": label, "confidence": confidence_value}
