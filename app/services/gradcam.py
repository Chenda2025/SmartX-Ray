"""
Grad-CAM heatmap generator.

Algorithm (Selvaraju et al. 2017):
  1. Build a sub-model that outputs (last_conv_activations, final_prediction).
  2. Record gradients of the predicted class score w.r.t. the conv activations.
  3. Pool gradients spatially → weight each activation channel.
  4. Apply ReLU, normalise, resize to original image size.
  5. Overlay as a semi-transparent jet colormap on the original X-ray.
"""

import os
import uuid
import logging
import numpy as np

logger = logging.getLogger(__name__)


# ── Public entry point ─────────────────────────────────────────────────────

def generate_gradcam(image_path: str, original_filename: str) -> str | None:
    """
    Generate a Grad-CAM heatmap overlay and save it to the heatmaps folder.

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
        from app.services.ai_service import get_model, preprocess, get_last_conv_layer_name

        model           = get_model()
        img_array       = preprocess(image_path)
        last_conv_name  = get_last_conv_layer_name()

        if last_conv_name is None:
            logger.warning("Grad-CAM skipped — no Conv2D layer found.")
            return None

        heatmap = _make_heatmap(model, img_array, last_conv_name)
        overlay = _overlay_on_image(image_path, heatmap)

        stem     = os.path.splitext(original_filename)[0]
        out_name = f"gradcam_{stem}.jpg"
        out_path = os.path.join(current_app.config["HEATMAP_FOLDER"], out_name)
        overlay.save(out_path, format="JPEG", quality=90)

        logger.info("Grad-CAM saved → %s", out_path)
        return out_name

    except Exception:
        logger.exception("Grad-CAM generation failed for %s", image_path)
        return None


# ── Step 1-4: compute the raw heatmap ─────────────────────────────────────

def _make_heatmap(model, img_array: np.ndarray, last_conv_layer_name: str) -> np.ndarray:
    """
    Return a 2-D float32 heatmap in [0, 1] using GradientTape.

    Uses a manual layer-by-layer forward pass so it works with both
    Sequential and Functional Keras 3 models (Sequential models don't
    expose model.output as a symbolic tensor until explicitly built).
    """
    import tensorflow as tf

    with tf.GradientTape() as tape:
        x = tf.cast(img_array, tf.float32)
        conv_outputs = None
        # Walk layers manually; watch the conv output so gradients flow
        for layer in model.layers:
            x = layer(x)
            if layer.name == last_conv_layer_name:
                conv_outputs = x
                tape.watch(conv_outputs)
        preds = x
        class_score = preds[:, 0]   # binary sigmoid output

    if conv_outputs is None:
        raise ValueError(f"Layer '{last_conv_layer_name}' not found during forward pass.")

    # Gradients of class score w.r.t. last conv feature maps
    grads        = tape.gradient(class_score, conv_outputs)     # (1, H, W, C)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))        # (C,)

    # Weight each channel by its pooled gradient
    conv_out = conv_outputs[0]                                   # (H, W, C)
    heatmap  = conv_out @ pooled_grads[..., tf.newaxis]          # (H, W, 1)
    heatmap  = tf.squeeze(heatmap)                               # (H, W)

    # ReLU + normalise to [0, 1]
    heatmap  = tf.nn.relu(heatmap).numpy()
    max_val  = heatmap.max()
    if max_val > 0:
        heatmap /= max_val

    return heatmap.astype(np.float32)


# ── Step 5: overlay on original image ─────────────────────────────────────

def _overlay_on_image(image_path: str, heatmap: np.ndarray, alpha: float = 0.45):
    """
    Resize the heatmap to the original image dimensions, apply a jet colormap,
    and blend with the original X-ray.

    Returns a PIL Image in RGB.
    """
    import cv2
    from PIL import Image

    # Load original in RGB
    orig_pil = Image.open(image_path).convert("RGB")
    orig_w, orig_h = orig_pil.size

    # Resize heatmap to match original image
    heatmap_uint8 = np.uint8(255 * heatmap)
    heatmap_resized = cv2.resize(heatmap_uint8, (orig_w, orig_h))

    # Apply jet colormap (returns BGR)
    colored = cv2.applyColorMap(heatmap_resized, cv2.COLORMAP_JET)
    colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

    # Blend
    orig_np  = np.array(orig_pil, dtype=np.float32)
    blend_np = (1 - alpha) * orig_np + alpha * colored_rgb.astype(np.float32)
    blend_np = np.clip(blend_np, 0, 255).astype(np.uint8)

    return Image.fromarray(blend_np)
