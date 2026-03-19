"""
Vision Agent – analyses the first page of a document visually using Gemini 2.5 Pro.

Outputs (stored in state["vision_results"]):
    visual_score    : 0-100 trust score from visual analysis (100 = fully trustworthy)
    visual_flags    : list of specific visual anomaly strings
    gemini_analysis : raw analysis text from the model
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_VISION_SYSTEM_PROMPT = (
    "You are an expert forensic document analyst specialising in detecting fraudulent "
    "documents. Analyse the provided document image and return ONLY a valid JSON object."
)

_VISION_PROMPT = """
Carefully examine this document image for signs of fraud or tampering.

Evaluate the following aspects and respond with a JSON object:

{
  "visual_score": <integer 0-100, where 100 = authentic, 0 = definitely fraudulent>,
  "visual_flags": [<list of specific anomalies found, empty if none>],
  "gemini_analysis": "<detailed paragraph describing your findings>",
  "watermark_present": <true|false>,
  "seal_present": <true|false>,
  "signature_present": <true|false>,
  "font_inconsistencies": <true|false>,
  "layout_anomalies": <true|false>,
  "tampering_indicators": [<list of specific tampering signs>]
}

Check for:
1. Inconsistent fonts or font sizes within the same section
2. Misaligned text or elements
3. Pixelation or blurring in specific areas (common in cut-and-paste fraud)
4. Suspicious watermarks, seals, or stamps that look low-resolution or misplaced
5. Signatures that appear copy-pasted or digitally inserted
6. Uneven margins or spacing
7. Colour inconsistencies (e.g., different ink tones for text that should be uniform)
8. Missing official elements expected for this document type

Be thorough. If the document looks entirely authentic, say so clearly.
"""


def _pdf_first_page_to_base64(file_path: str) -> str:
    """Render the first PDF page at 150 DPI and return a base64 PNG string."""
    import fitz

    doc = fitz.open(file_path)
    page = doc[0]
    mat = fitz.Matrix(150 / 72, 150 / 72)  # ~150 DPI
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    png_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(png_bytes).decode("utf-8")


def _image_to_base64(file_path: str) -> str:
    """Read an image file and return base64 string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def _call_gemini_vision(
    image_b64: str,
    mime_type: str = "image/png",
) -> Dict[str, Any]:
    """Send image + prompt to Gemini 2.5 Pro with vision capability."""
    import os
    import json

    import google.generativeai as genai

    gemini_keys = [
        os.getenv("GEMINI_API_KEY_1", ""),
        os.getenv("GEMINI_API_KEY_2", ""),
        os.getenv("GEMINI_API_KEY_3", ""),
    ]

    image_bytes = base64.b64decode(image_b64)

    loop = asyncio.get_event_loop()
    for idx, key in enumerate(gemini_keys, start=1):
        if not key:
            continue
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name="gemini-2.5-pro-latest",
                system_instruction=_VISION_SYSTEM_PROMPT,
            )
            import PIL.Image
            import io as _io

            pil_image = PIL.Image.open(_io.BytesIO(image_bytes))

            prompt_text = _VISION_PROMPT + "\n\nRespond ONLY with valid JSON, no markdown fences."

            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content([prompt_text, pil_image]),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                raw = "\n".join(inner).strip()

            result = json.loads(raw)
            logger.info("Vision agent: Gemini key %d succeeded", idx)
            return result
        except Exception as exc:
            logger.warning("Vision Gemini key %d failed: %s", idx, exc)

    # Fallback to ai_caller text-based analysis (no image)
    logger.warning("Vision agent: all Gemini keys failed, using text fallback")
    from ai_caller import call_ai

    fallback_prompt = (
        "A document image was provided for fraud analysis but vision API is unavailable. "
        "Return a conservative JSON result indicating that visual analysis could not be completed.\n"
        + _VISION_PROMPT
    )
    return await call_ai(fallback_prompt, _VISION_SYSTEM_PROMPT, json_mode=True)


def _default_vision_result() -> Dict[str, Any]:
    return {
        "visual_score": 50,
        "visual_flags": ["Visual analysis unavailable – manual review required"],
        "gemini_analysis": "Vision analysis could not be completed.",
        "watermark_present": False,
        "seal_present": False,
        "signature_present": False,
        "font_inconsistencies": False,
        "layout_anomalies": False,
        "tampering_indicators": [],
    }


async def run_vision_agent(state: dict) -> dict:
    file_path: str = state.get("file_path", "")

    if not file_path or not os.path.exists(file_path):
        logger.error("Vision agent: file not found at %s", file_path)
        result = _default_vision_result()
        result["error"] = f"File not found: {file_path}"
        state["vision_results"] = result
        return state

    ext = os.path.splitext(file_path)[1].lower()
    loop = asyncio.get_event_loop()

    try:
        if ext == ".pdf":
            image_b64 = await loop.run_in_executor(
                None, _pdf_first_page_to_base64, file_path
            )
            mime_type = "image/png"
        else:
            image_b64 = await loop.run_in_executor(
                None, _image_to_base64, file_path
            )
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
                ".bmp": "image/bmp",
            }
            mime_type = mime_map.get(ext, "image/png")
    except Exception as exc:
        logger.exception("Vision agent: failed to convert file to image: %s", exc)
        result = _default_vision_result()
        result["error"] = str(exc)
        state["vision_results"] = result
        return state

    try:
        vision_result = await _call_gemini_vision(image_b64, mime_type)
    except Exception as exc:
        logger.exception("Vision agent: Gemini call failed: %s", exc)
        vision_result = _default_vision_result()
        vision_result["error"] = str(exc)

    # Ensure required fields exist
    vision_result.setdefault("visual_score", 50)
    vision_result.setdefault("visual_flags", [])
    vision_result.setdefault("gemini_analysis", "")

    # Clamp score
    vision_result["visual_score"] = max(0, min(100, int(vision_result["visual_score"])))

    state["vision_results"] = vision_result
    logger.info(
        "Vision agent complete – visual_score=%d  flags=%d",
        vision_result["visual_score"],
        len(vision_result.get("visual_flags", [])),
    )
    return state
