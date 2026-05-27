"""
AI prediction service.

Supports two backends (auto-detected from MODEL_PATH):
  • TFLite  (.tflite) — lightweight, ~25 MB, runs on Render free tier
  • Keras   (.h5)     — full TensorFlow, ~299 MB, requires ≥1 GB RAM

The TFLite backend is preferred for production (Render free tier has 512 MB RAM).
Grad-CAM is only available with the Keras backend; it is silently skipped otherwise.
"""

import os
import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Singleton state ────────────────────────────────────────────────────────
_model      = None          # Keras model  OR  TFLite Interpreter
_is_tflite  = False
_model_lock = threading.Lock()

LABELS     = {0: "NORMAL", 1: "PNEUMONIA"}
IMAGE_SIZE = (224, 224)


# ── Model loading ──────────────────────────────────────────────────────────

def get_model():
    """Return the loaded model (Keras or TFLite), loading it on first call."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _load()
    return _model


def _tflite_path(h5_path: str) -> str:
    """Derive the .tflite path from the .h5 path."""
    return h5_path.replace(".h5", ".tflite")


def _load():
    global _is_tflite
    from flask import current_app

    h5_path     = current_app.config["MODEL_PATH"]
    tflite_path = _tflite_path(h5_path)

    # ── Prefer TFLite (fits in Render free tier 512 MB RAM) ───────────────
    if os.path.exists(tflite_path):
        logger.info("Loading TFLite model from %s …", tflite_path)
        import tensorflow as tf
        interpreter = tf.lite.Interpreter(model_path=tflite_path)
        interpreter.allocate_tensors()
        _is_tflite = True
        logger.info("TFLite model loaded — input: %s", interpreter.get_input_details())
        return interpreter

    # ── Fallback: full Keras model ─────────────────────────────────────────
    if not os.path.exists(h5_path):
        raise FileNotFoundError(
            f"Model not found at {tflite_path} or {h5_path}. "
            "Set MODEL_URL in Render environment and redeploy."
        )

    logger.info("Loading Keras model from %s …", h5_path)
    import tensorflow as tf

    class _PatchedDense(tf.keras.layers.Dense):
        @classmethod
        def from_config(cls, config):
            config.pop("quantization_config", None)
            return super().from_config(config)

    try:
        model = tf.keras.models.load_model(
            h5_path,
            compile=False,
            custom_objects={"Dense": _PatchedDense},
        )
    except Exception:
        model = tf.keras.models.load_model(h5_path, compile=False)

    _is_tflite = False
    logger.info("Keras model loaded — input shape: %s", model.input_shape)
    return model


# ── Image preprocessing ────────────────────────────────────────────────────

def preprocess(image_path: str) -> np.ndarray:
    """
    Load, resize, and normalise an image to match the model's input shape.
    Works for both TFLite and Keras backends.
    """
    from PIL import Image

    n_channels = _get_input_channels()
    mode = "L" if n_channels == 1 else "RGB"

    img = Image.open(image_path).convert(mode).resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0

    if n_channels == 1:
        arr = np.expand_dims(arr, axis=-1)

    return np.expand_dims(arr, axis=0)   # (1, H, W, C)


def _get_input_channels() -> int:
    model = get_model()
    if _is_tflite:
        shape = model.get_input_details()[0]["shape"]   # [1, H, W, C]
        return int(shape[-1])
    else:
        return model.input_shape[-1]


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

    if _is_tflite:
        raw = _predict_tflite(model, img_array)
    else:
        raw = float(model.predict(img_array, verbose=0)[0][0])

    label      = LABELS[int(raw >= 0.5)]
    confidence = raw if raw >= 0.5 else 1.0 - raw

    logger.info("Prediction: %s (confidence=%.4f raw=%.4f)", label, confidence, raw)
    return label, confidence, raw


def _predict_tflite(interpreter, img_array: np.ndarray) -> float:
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.set_tensor(input_details[0]["index"], img_array)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]["index"])
    return float(output[0][0])


# ── Utility: last Conv2D layer name (Keras only) ──────────────────────────

def get_last_conv_layer_name() -> str | None:
    """
    Walk the model layers in reverse and return the name of the last Conv2D.
    Returns None for TFLite (Grad-CAM not supported).
    """
    if _is_tflite:
        logger.info("Grad-CAM skipped — TFLite backend does not support GradientTape.")
        return None

    import tensorflow as tf
    model = get_model()
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.layers.Conv2D):
            logger.info("Last Conv2D layer: %s", layer.name)
            return layer.name
    logger.warning("No Conv2D layer found in model.")
    return None
