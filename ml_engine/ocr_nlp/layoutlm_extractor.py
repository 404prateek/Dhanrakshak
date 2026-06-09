# LayoutLMv3 document entity extraction

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict

import pytesseract
import torch
from PIL import Image
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class DocumentEntities(TypedDict, total=False):
    """Structured entities extracted from a single document image."""
    name: Optional[str]
    dob: Optional[str]
    property_id: Optional[str]
    survey_number: Optional[str]
    owner_name: Optional[str]


# ---------------------------------------------------------------------------
# Label mappings  (align with your fine-tuned checkpoint; defaults shown here
# match the standard BIO scheme used during training)
# ---------------------------------------------------------------------------
_ENTITY_KEYS = ("name", "dob", "property_id", "survey_number", "owner_name")

# Map each target entity to the B- label index used in your fine-tuned model.
# If you use a different label scheme, update this dict to match id2label.
_LABEL_TO_ENTITY: Dict[str, str] = {
    "B-NAME": "name",
    "B-DOB": "dob",
    "B-PROPERTY_ID": "property_id",
    "B-SURVEY_NUMBER": "survey_number",
    "B-OWNER_NAME": "owner_name",
}

_MODEL_NAME = "microsoft/layoutlmv3-base"

# Normalised bounding-box space used by LayoutLMv3 (0–1000).
_BBOX_NORM = 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_bbox(
    box: Tuple[int, int, int, int], width: int, height: int
) -> List[int]:
    """Scale a Tesseract pixel bbox to the 0-1000 LayoutLMv3 coordinate space."""
    x0, y0, x1, y1 = box
    return [
        min(int(x0 / width * _BBOX_NORM), _BBOX_NORM),
        min(int(y0 / height * _BBOX_NORM), _BBOX_NORM),
        min(int(x1 / width * _BBOX_NORM), _BBOX_NORM),
        min(int(y1 / height * _BBOX_NORM), _BBOX_NORM),
    ]


def _ocr_words_and_boxes(
    image: Image.Image,
) -> Tuple[List[str], List[List[int]]]:
    """
    Run pytesseract on *image* and return parallel lists of
    (word_tokens, normalised_bounding_boxes).
    Empty / whitespace tokens are discarded.
    """
    width, height = image.size
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words: List[str] = []
    boxes: List[List[int]] = []

    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue
        x, y, w, h = (
            data["left"][i],
            data["top"][i],
            data["width"][i],
            data["height"][i],
        )
        pixel_box = (x, y, x + w, y + h)
        words.append(word)
        boxes.append(_normalize_bbox(pixel_box, width, height))

    return words, boxes


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class LayoutLMExtractor:
    """
    Extracts structured document entities using LayoutLMv3 + pytesseract OCR.

    Pipeline
    --------
    1. Load and RGB-normalise the source image.
    2. Run pytesseract to obtain word tokens with bounding boxes.
    3. Feed (image, words, boxes) through the LayoutLMv3 processor.
    4. Run token classification; map predicted labels back to entity keys.
    5. Return a ``DocumentEntities`` TypedDict.

    Usage
    -----
    extractor = LayoutLMExtractor()           # downloads model on first run
    entities  = extractor.extract("deed.jpg")
    # {"name": "Ramesh Kumar", "dob": "12/08/1975", "property_id": "KA-BLR-007", ...}
    """

    def __init__(
        self,
        model_name: str = _MODEL_NAME,
        weights_path: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        """
        Parameters
        ----------
        model_name    : HuggingFace model identifier or local directory path.
        weights_path  : Optional path to a fine-tuned state-dict (.pt/.pth).
                        When None the raw pretrained weights are used.
        device        : 'cuda', 'mps', or 'cpu'.  Auto-detected when None.
        """
        self.model_name = model_name
        self.weights_path = Path(weights_path) if weights_path else None
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self._processor: Optional[LayoutLMv3Processor] = None
        self._model: Optional[LayoutLMv3ForTokenClassification] = None

    # ------------------------------------------------------------------
    # Lazy loader — called automatically on first extract()
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        self._processor = LayoutLMv3Processor.from_pretrained(
            self.model_name, apply_ocr=False  # we supply our own OCR output
        )
        self._model = LayoutLMv3ForTokenClassification.from_pretrained(
            self.model_name
        )

        if self.weights_path is not None:
            if not self.weights_path.is_file():
                raise FileNotFoundError(
                    f"Weights file not found: {self.weights_path}"
                )
            state_dict = torch.load(
                self.weights_path,
                map_location=self.device,
                weights_only=True,   # safe loading — no arbitrary pickle exec
            )
            self._model.load_state_dict(state_dict, strict=True)

        self._model.to(self.device).eval()

    # ------------------------------------------------------------------
    # Internal: token-level predictions → entity spans
    # ------------------------------------------------------------------

    def _decode_entities(
        self,
        words: List[str],
        predicted_labels: List[str],
    ) -> DocumentEntities:
        """
        Walk aligned (word, label) pairs and collect the first occurrence of
        each target entity.  I- tokens extend the current span; B- tokens
        start a new span.
        """
        entities: DocumentEntities = {k: None for k in _ENTITY_KEYS}  # type: ignore[misc]
        current_entity: Optional[str] = None
        current_tokens: List[str] = []

        def _flush() -> None:
            if current_entity and current_tokens:
                entities[current_entity] = " ".join(current_tokens)  # type: ignore[literal-required]

        for word, label in zip(words, predicted_labels):
            if label.startswith("B-") and label in _LABEL_TO_ENTITY:
                _flush()
                current_entity = _LABEL_TO_ENTITY[label]
                current_tokens = [word]
            elif label.startswith("I-"):
                # Accept I- token if it continues the active span
                i_key = _LABEL_TO_ENTITY.get("B-" + label[2:])
                if i_key and i_key == current_entity:
                    current_tokens.append(word)
                else:
                    _flush()
                    current_entity = None
                    current_tokens = []
            else:
                _flush()
                current_entity = None
                current_tokens = []

        _flush()
        return entities

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, image_path: str) -> DocumentEntities:
        """
        Run the full extraction pipeline on *image_path*.

        Parameters
        ----------
        image_path : Path to the document image (any PIL-readable format).

        Returns
        -------
        DocumentEntities TypedDict with keys:
            name, dob, property_id, survey_number, owner_name.
        Missing entities are ``None``.

        Raises
        ------
        FileNotFoundError : If *image_path* does not exist.
        """
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")

        self._ensure_loaded()

        image: Image.Image = Image.open(path).convert("RGB")
        words, boxes = _ocr_words_and_boxes(image)

        if not words:
            return {k: None for k in _ENTITY_KEYS}  # type: ignore[return-value]

        encoding = self._processor(
            image,
            words,
            boxes=boxes,
            return_tensors="pt",
            truncation=True,
            padding="max_length",
            max_length=512,
        )
        encoding = {k: v.to(self.device) for k, v in encoding.items()}

        with torch.inference_mode():
            outputs = self._model(**encoding)

        # outputs.logits shape: (1, seq_len, num_labels)
        predictions = outputs.logits.argmax(dim=-1).squeeze(0).tolist()  # (seq_len,)
        id2label: Dict[int, str] = self._model.config.id2label

        # Align token predictions back to word-level (take the first sub-token)
        # The processor's word_ids() maps each token position → word index.
        word_ids: List[Optional[int]] = encoding.get(
            "word_ids",
            [None] * len(predictions),
        )
        # Fallback: use word_ids from the BatchEncoding if available
        try:
            word_ids = self._processor.tokenizer(
                words,
                is_split_into_words=True,
                truncation=True,
                max_length=512,
            ).word_ids()
        except Exception:
            pass

        word_labels: List[str] = ["O"] * len(words)
        seen: set = set()
        for token_idx, word_idx in enumerate(word_ids):
            if word_idx is None or word_idx in seen:
                continue
            seen.add(word_idx)
            if word_idx < len(words) and token_idx < len(predictions):
                word_labels[word_idx] = id2label.get(predictions[token_idx], "O")

        return self._decode_entities(words, word_labels)
