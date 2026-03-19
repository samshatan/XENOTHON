"""
OCR Agent – extracts text from PDF and image files.

Outputs (stored in state["ocr_results"]):
    text          : full concatenated text
    pages_data    : list of per-page dicts {page_num, text, confidence}
    avg_confidence: average OCR confidence 0-100
    word_count    : total word count
    image_count   : number of embedded images found
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SPARSE_TEXT_THRESHOLD = 50  # chars per page below which we run Tesseract

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}


def _extract_pdf(file_path: str) -> Dict[str, Any]:
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    pages_data: List[Dict[str, Any]] = []
    total_images = 0

    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text")
        image_list = page.get_images(full=True)
        total_images += len(image_list)

        confidence: float = 100.0  # assume native PDF text is high quality

        if len(page_text.strip()) < SPARSE_TEXT_THRESHOLD:
            # Render page as image and run Tesseract
            try:
                import pytesseract
                from PIL import Image

                mat = fitz.Matrix(2.0, 2.0)  # 2× zoom for better OCR
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_data = pytesseract.image_to_data(
                    img, output_type=pytesseract.Output.DICT
                )
                words = [
                    (w, int(c))
                    for w, c in zip(ocr_data["text"], ocr_data["conf"])
                    if w.strip() and int(c) >= 0
                ]
                if words:
                    page_text = " ".join(w for w, _ in words)
                    confidence = sum(c for _, c in words) / len(words)
                else:
                    confidence = 0.0
            except Exception as exc:
                logger.warning("Tesseract failed on page %d: %s", page_num, exc)
                confidence = 0.0

        pages_data.append(
            {
                "page_num": page_num,
                "text": page_text,
                "confidence": round(confidence, 2),
            }
        )

    doc.close()

    full_text = "\n".join(p["text"] for p in pages_data)
    avg_conf = (
        sum(p["confidence"] for p in pages_data) / len(pages_data)
        if pages_data
        else 0.0
    )

    return {
        "text": full_text,
        "pages_data": pages_data,
        "avg_confidence": round(avg_conf, 2),
        "word_count": len(full_text.split()),
        "image_count": total_images,
    }


def _extract_image(file_path: str) -> Dict[str, Any]:
    import pytesseract
    from PIL import Image

    img = Image.open(file_path)
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = [
        (w, int(c))
        for w, c in zip(ocr_data["text"], ocr_data["conf"])
        if w.strip() and int(c) >= 0
    ]

    if words:
        text = " ".join(w for w, _ in words)
        confidence = sum(c for _, c in words) / len(words)
    else:
        text = pytesseract.image_to_string(img)
        confidence = 50.0

    pages_data = [{"page_num": 1, "text": text, "confidence": round(confidence, 2)}]

    return {
        "text": text,
        "pages_data": pages_data,
        "avg_confidence": round(confidence, 2),
        "word_count": len(text.split()),
        "image_count": 1,
    }


async def run_ocr_agent(state: dict) -> dict:
    file_path: str = state.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        logger.error("OCR agent: file not found at %s", file_path)
        state["ocr_results"] = {
            "text": "",
            "pages_data": [],
            "avg_confidence": 0.0,
            "word_count": 0,
            "image_count": 0,
            "error": f"File not found: {file_path}",
        }
        return state

    ext = os.path.splitext(file_path)[1].lower()

    loop = asyncio.get_event_loop()
    try:
        if ext == ".pdf":
            results = await loop.run_in_executor(None, _extract_pdf, file_path)
        elif ext in SUPPORTED_IMAGE_EXTS:
            results = await loop.run_in_executor(None, _extract_image, file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    except Exception as exc:
        logger.exception("OCR agent failed: %s", exc)
        results = {
            "text": "",
            "pages_data": [],
            "avg_confidence": 0.0,
            "word_count": 0,
            "image_count": 0,
            "error": str(exc),
        }

    state["ocr_results"] = results
    logger.info(
        "OCR agent complete – words=%d  avg_conf=%.1f",
        results.get("word_count", 0),
        results.get("avg_confidence", 0.0),
    )
    return state
