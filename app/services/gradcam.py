"""
Heatmap / saliency-map generator.

Strategy (chosen automatically per active backend):

  Keras (.h5)  → Grad-CAM (Selvaraju et al. 2017)
                  1. Sub-model that outputs (last_conv_activations, final_prediction).
                  2. Record gradients of class score w.r.t. conv activations.
                  3. Pool gradients spatially → weight each activation channel.
                  4. Apply ReLU, normalise, resize, overlay.

  ONNX / TFLite → Occlusion Sensitivity
                  1. Slide a neutral (0.5-filled) patch over the preprocessed image.
                  2. Measure Δprediction_score at each position.
                  3. Assemble Δ values into a 2-D saliency grid.
                  4. Normalise, resize, overlay (same colour-map pipeline as Grad-CAM).
"""

import os
import logging
import numpy as np

logger = logging.getLogger(__name__)


# ── Public entry point ─────────────────────────────────────────────────────

def generate_gradcam(image_path: str, original_filename: str) -> str | None:
    """
    Generate a heatmap overlay and save it to the heatmaps folder.

    Parameters
    ----------
    image_path        : absolute path to the uploaded X-ray
    original_filename : used only to derive a unique output filename

    Returns
    -------
    heatmap filename (relative to static/heatmaps/) or None on failure.
    """
    try:
        from flask import current_app
        from app.services.ai_service import (
            get_model, preprocess, get_last_conv_layer_name, get_backend,
        )

        model          = get_model()
        img_array      = preprocess(image_path)
        last_conv_name = get_last_conv_layer_name()   # None if not Keras

        backend = get_backend()

        if last_conv_name is not None:
            # ── Keras backend: true Grad-CAM ──────────────────────────────
            logger.info("Using Grad-CAM (Keras backend)")
            heatmap = _gradcam_heatmap(model, img_array, last_conv_name)
        else:
            # ── ONNX / TFLite backend: occlusion sensitivity ───────────────
            logger.info("Using Occlusion Sensitivity (%s backend)", backend)
            heatmap = _occlusion_heatmap(model, img_array, backend)

        if heatmap is None:
            logger.warning("Heatmap computation returned None.")
            return None

        overlay  = _overlay_on_image(image_path, heatmap)

        stem     = os.path.splitext(original_filename)[0]
        out_name = f"gradcam_{stem}.jpg"
        out_path = os.path.join(current_app.config["HEATMAP_FOLDER"], out_name)
        overlay.save(out_path, format="JPEG", quality=90)

        logger.info("Heatmap saved → %s", out_path)
        return out_name

    except Exception:
        logger.exception("Heatmap generation failed for %s", image_path)
        return None


# ── Backend 1: Grad-CAM (Keras only) ──────────────────────────────────────

def _gradcam_heatmap(model, img_array: np.ndarray, last_conv_layer_name: str) -> np.ndarray:
    """
    Return a 2-D float32 heatmap in [0, 1] using GradientTape.

    Uses a manual layer-by-layer forward pass so it works with both
    Sequential and Functional Keras 3 models.
    """
    import tensorflow as tf

    with tf.GradientTape() as tape:
        x = tf.cast(img_array, tf.float32)
        conv_outputs = None
        for layer in model.layers:
            x = layer(x)
            if layer.name == last_conv_layer_name:
                conv_outputs = x
                tape.watch(conv_outputs)
        preds       = x
        class_score = preds[:, 0]   # binary sigmoid output

    if conv_outputs is None:
        raise ValueError(f"Layer '{last_conv_layer_name}' not found during forward pass.")

    grads        = tape.gradient(class_score, conv_outputs)   # (1, H, W, C)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))      # (C,)
    conv_out     = conv_outputs[0]                             # (H, W, C)
    heatmap      = conv_out @ pooled_grads[..., tf.newaxis]    # (H, W, 1)
    heatmap      = tf.squeeze(heatmap)                         # (H, W)

    heatmap = tf.nn.relu(heatmap).numpy()
    max_val = heatmap.max()
    if max_val > 0:
        heatmap /= max_val

    return heatmap.astype(np.float32)


# ── Backend 2: Occlusion Sensitivity (ONNX / TFLite) ──────────────────────

def _occlusion_heatmap(
    model,
    img_array: np.ndarray,
    backend: str,
    patch_size: int = 32,
    stride: int = 16,
    fill_value: float = 0.5,
) -> np.ndarray:
    """
    Slide a neutral patch over the image and record how the prediction score
    changes.  Regions whose occlusion *lowers* the PNEUMONIA score the most
    are the most salient.

    Parameters
    ----------
    model       : ONNX InferenceSession or TFLite Interpreter
    img_array   : preprocessed input, shape (1, H, W, C), float32 in [0,1]
    backend     : active backend string ('onnx' | 'tflite' | 'keras')
    patch_size  : side length of the occluding square (pixels in model space)
    stride      : step between patch positions
    fill_value  : intensity used to fill the occluded region (0.5 = mid-grey)

    Returns
    -------
    2-D float32 heatmap in [0, 1], shape (H_grid, W_grid) — will be upsampled
    to the original image size by _overlay_on_image.
    """
    _, H, W, _ = img_array.shape

    def _score(arr: np.ndarray) -> float:
        """Run one forward pass and return the raw sigmoid output."""
        if backend == "onnx":
            input_name = model.get_inputs()[0].name
            return float(model.run(None, {input_name: arr})[0][0][0])
        elif backend == "tflite":
            inp = model.get_input_details()[0]
            out = model.get_output_details()[0]
            model.set_tensor(inp["index"], arr)
            model.invoke()
            return float(model.get_tensor(out["index"])[0][0])
        else:
            # Keras fallback (should not reach here normally)
            return float(model.predict(arr, verbose=0)[0][0])

    baseline = _score(img_array)

    # Build a list of (row, col) top-left corners for each patch position
    rows = list(range(0, H - patch_size + 1, stride))
    cols = list(range(0, W - patch_size + 1, stride))
    if (H - patch_size) % stride != 0:
        rows.append(H - patch_size)
    if (W - patch_size) % stride != 0:
        cols.append(W - patch_size)

    n_rows, n_cols = len(rows), len(cols)
    saliency = np.zeros((n_rows, n_cols), dtype=np.float32)

    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            occluded = img_array.copy()
            occluded[:, r : r + patch_size, c : c + patch_size, :] = fill_value
            delta = baseline - _score(occluded)   # positive = this region matters
            saliency[i, j] = max(delta, 0.0)       # ReLU: only show positive impact

    max_val = saliency.max()
    if max_val > 0:
        saliency /= max_val

    logger.info(
        "Occlusion map computed: %d×%d grid (patch=%d, stride=%d)",
        n_rows, n_cols, patch_size, stride,
    )
    return saliency


# ── Common: overlay heatmap on original image ──────────────────────────────

def _overlay_on_image(image_path: str, heatmap: np.ndarray, alpha: float = 0.45):
    """
    Resize the heatmap to the original image dimensions, apply a jet colormap,
    and blend with the original X-ray.

    Returns a PIL Image in RGB.
    """
    import cv2
    from PIL import Image

    orig_pil        = Image.open(image_path).convert("RGB")
    orig_w, orig_h  = orig_pil.size

    heatmap_uint8   = np.uint8(255 * heatmap)
    heatmap_resized = cv2.resize(heatmap_uint8, (orig_w, orig_h),
                                 interpolation=cv2.INTER_CUBIC)

    colored     = cv2.applyColorMap(heatmap_resized, cv2.COLORMAP_JET)
    colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

    orig_np  = np.array(orig_pil, dtype=np.float32)
    blend_np = (1 - alpha) * orig_np + alpha * colored_rgb.astype(np.float32)
    blend_np = np.clip(blend_np, 0, 255).astype(np.uint8)

    return Image.fromarray(blend_np)
