"""
AI prediction service.

Backends tried in order (auto-detected from available model files):
  1. ONNX Runtime  (.onnx)   — ~100 MB RAM, no TF needed  ← preferred on Render free tier
  2. TFLite        (.tflite) — ~300 MB RAM (still needs TF import)
  3. Keras         (.h5)     — ~400 MB RAM, full TensorFlow

Grad-CAM is only available with the Keras (.h5) backend.
"""

import os
import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Singleton state ────────────────────────────────────────────────────────
_model      = None          # ONNX session | TFLite Interpreter | Keras model
_backend    = None          # "onnx" | "tflite" | "keras"
_model_lock = threading.Lock()

LABELS     = {0: "NORMAL", 1: "PNEUMONIA"}
IMAGE_SIZE = (224, 224)


# ── Model loading ──────────────────────────────────────────────────────────

def get_model():
    """Return the loaded model, loading it on first call."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _load()
    return _model


def _load():
    global _backend
    from flask import current_app

    h5_path     = current_app.config["MODEL_PATH"]
    tflite_path = h5_path.replace(".h5", ".tflite")
    onnx_path   = h5_path.replace(".h5", ".onnx")

    # ── 1. ONNX Runtime (~100 MB RAM, no TF dependency) ──────────────────
    if os.path.exists(onnx_path):
        logger.info("Loading ONNX model from %s …", onnx_path)
        try:
            import onnxruntime as ort
            sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
            _backend = "onnx"
            logger.info("ONNX model loaded — input: %s", sess.get_inputs()[0].name)
            return sess
        except Exception as exc:
            logger.error("ONNX load failed (%s), trying next backend…", exc)

    # ── 2. TFLite (~300 MB RAM, needs TF) ─────────────────────────────────
    if os.path.exists(tflite_path):
        logger.info("Loading TFLite model from %s …", tflite_path)
        try:
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=tflite_path)
            interpreter.allocate_tensors()
            _backend = "tflite"
            logger.info("TFLite model loaded")
            return interpreter
        except Exception as exc:
            logger.error("TFLite load failed (%s), trying next backend…", exc)

    # ── 3. Keras full model (~400 MB RAM) ─────────────────────────────────
    if os.path.exists(h5_path):
        logger.info("Loading Keras model from %s …", h5_path)
        try:
            import tensorflow as tf

            class _PatchedDense(tf.keras.layers.Dense):
                @classmethod
                def from_config(cls, config):
                    config.pop("quantization_config", None)
                    return super().from_config(config)

            try:
                model = tf.keras.models.load_model(
                    h5_path, compile=False,
                    custom_objects={"Dense": _PatchedDense},
                )
            except Exception:
                model = tf.keras.models.load_model(h5_path, compile=False)

            _backend = "keras"
            logger.info("Keras model loaded — input shape: %s", model.input_shape)
            return model
        except ImportError:
            # TensorFlow is not installed (expected when using ONNX/TFLite backends).
            # Fall through so FileNotFoundError is raised below with a helpful message.
            logger.warning(
                "TensorFlow not installed — Keras (.h5) backend unavailable. "
                "Set MODEL_URL to a .onnx file and redeploy."
            )
        except Exception as exc:
            logger.error("Keras load failed: %s", exc)
            raise

    raise FileNotFoundError(
        f"No model found. Looked for:\n  {onnx_path}\n  {tflite_path}\n  {h5_path}\n"
        "Set MODEL_URL in Render environment and redeploy."
    )


# ── Image preprocessing ────────────────────────────────────────────────────

def _input_channels() -> int:
    model = get_model()
    if _backend == "onnx":
        return int(model.get_inputs()[0].shape[-1])
    elif _backend == "tflite":
        return int(model.get_input_details()[0]["shape"][-1])
    else:
        return model.input_shape[-1]


def preprocess(image_path: str) -> np.ndarray:
    from PIL import Image
    n = _input_channels()
    mode = "L" if n == 1 else "RGB"
    img = Image.open(image_path).convert(mode).resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    if n == 1:
        arr = np.expand_dims(arr, axis=-1)
    return np.expand_dims(arr, axis=0)   # (1, H, W, C)


# ── Prediction ─────────────────────────────────────────────────────────────

def predict(image_path: str) -> tuple[str, float, float]:
    model     = get_model()
    img_array = preprocess(image_path)

    if _backend == "onnx":
        input_name = model.get_inputs()[0].name
        raw = float(model.run(None, {input_name: img_array})[0][0][0])
    elif _backend == "tflite":
        inp = model.get_input_details()[0]
        out = model.get_output_details()[0]
        model.set_tensor(inp["index"], img_array)
        model.invoke()
        raw = float(model.get_tensor(out["index"])[0][0])
    else:
        raw = float(model.predict(img_array, verbose=0)[0][0])

    label      = LABELS[int(raw >= 0.5)]
    confidence = raw if raw >= 0.5 else 1.0 - raw

    logger.info("Prediction [%s]: %s (conf=%.4f raw=%.4f)", _backend, label, confidence, raw)
    return label, confidence, raw


# ── Backend accessor ───────────────────────────────────────────────────────

def get_backend() -> str | None:
    """Return the active backend string: 'onnx', 'tflite', or 'keras'."""
    return _backend


# ── Grad-CAM support (Keras backend only) ─────────────────────────────────

def get_last_conv_layer_name() -> str | None:
    if _backend != "keras":
        logger.info("Grad-CAM skipped — backend is '%s', not 'keras'.", _backend)
        return None
    import tensorflow as tf
    model = get_model()
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.layers.Conv2D):
            logger.info("Last Conv2D layer: %s", layer.name)
            return layer.name
    logger.warning("No Conv2D layer found in model.")
    return None
