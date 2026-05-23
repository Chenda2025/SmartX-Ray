"""
AI prediction service.

Loads best_model.h5 once at startup (singleton) to avoid the cold-start
penalty on every request. The model stays in process memory for the
lifetime of the Flask worker.
"""

import os
import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Singleton state ────────────────────────────────────────────────────────
_model      = None
_model_lock = threading.Lock()

LABELS     = {0: "NORMAL", 1: "PNEUMONIA"}
IMAGE_SIZE = (224, 224)


# ── Model loading ──────────────────────────────────────────────────────────

def get_model():
    """Return the loaded Keras model, loading it on first call."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:          # double-checked inside lock
                _model = _load()
    return _model


def _load():
    from flask import current_app
    import tensorflow as tf

    model_path = current_app.config["MODEL_PATH"]
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    logger.info("Loading model from %s …", model_path)
    model = tf.keras.models.load_model(model_path, compile=False)
    logger.info("Model loaded — input shape: %s", model.input_shape)
    return model


# ── Image preprocessing ────────────────────────────────────────────────────

def preprocess(image_path: str) -> np.ndarray:
    """
    Load, resize, and normalise an image to match the model's input shape.
    Automatically handles both 1-channel (grayscale) and 3-channel (RGB) models.
    """
    from PIL import Image

    # Detect expected channels from model input shape (None, H, W, C)
    n_channels = get_model().input_shape[-1]
    mode = "L" if n_channels == 1 else "RGB"

    img = Image.open(image_path).convert(mode).resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0

    if n_channels == 1:
        arr = np.expand_dims(arr, axis=-1)      # (H, W) → (H, W, 1)

    return np.expand_dims(arr, axis=0)          # (1, H, W, C)


# ── Prediction ─────────────────────────────────────────────────────────────

def predict(image_path: str) -> tuple[str, float, float]:
    """
    Run inference on a single image.

    Returns
    -------
    label      : "PNEUMONIA" or "NORMAL"
    confidence : probability of the predicted class  (0.0 – 1.0)
    raw_score  : raw sigmoid output of the final neuron
    """
    model     = get_model()
    img_array = preprocess(image_path)

    raw = float(model.predict(img_array, verbose=0)[0][0])  # sigmoid scalar

    # sigmoid > 0.5  →  PNEUMONIA (class 1)
    label      = LABELS[int(raw >= 0.5)]
    confidence = raw if raw >= 0.5 else 1.0 - raw

    logger.info("Prediction: %s (confidence=%.4f raw=%.4f)", label, confidence, raw)
    return label, confidence, raw


# ── Utility: last Conv2D layer name ───────────────────────────────────────

def get_last_conv_layer_name() -> str | None:
    """
    Walk the model layers in reverse and return the name of the last
    Conv2D layer — needed by the Grad-CAM service.
    """
    import tensorflow as tf
    model = get_model()
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.layers.Conv2D):
            logger.info("Last Conv2D layer: %s", layer.name)
            return layer.name
    logger.warning("No Conv2D layer found in model.")
    return None
