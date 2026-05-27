from __future__ import annotations

import base64
import math
from io import BytesIO
from typing import Any

try:  # pragma: no cover
    import fitz
except Exception:  # pragma: no cover
    fitz = None

try:  # pragma: no cover
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:  # pragma: no cover
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:  # pragma: no cover
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None


class ImagePreprocessor:
    """Enhance uploaded prescription images before OCR or AI decoding."""

    def enhance_data_url(self, image_data: str, mime_type: str = "image/jpeg") -> dict[str, Any]:
        payload_mime, raw_bytes = self._decode_data_url(image_data, mime_type)
        image_bytes, image = self._load_image_bytes(raw_bytes, payload_mime)
        quality_before = self._score_image_quality(image)

        enhanced = self._enhance_image(image)
        roi = self._detect_roi(enhanced)
        deskewed = self._deskew(roi)
        final_image = self._finalize(deskewed)
        quality_after = self._score_image_quality(final_image)

        output_bytes = self._encode_image(final_image)
        output_b64 = base64.b64encode(output_bytes).decode("utf-8")
        result_mime = "image/png"
        return {
            "mime_type": result_mime,
            "image_data": f"data:{result_mime};base64,{output_b64}",
            "image_base64": output_b64,
            "source_image_quality": quality_after["overall_score"],
            "image_quality_breakdown": quality_after,
            "quality_before": quality_before,
            "applied_steps": [
                "contrast_adjustment",
                "denoise",
                "sharpen",
                "roi_detection",
                "deskew",
            ],
        }

    def _decode_data_url(self, image_data: str, fallback_mime: str) -> tuple[str, bytes]:
        raw = str(image_data or "").strip()
        if raw.startswith("data:") and ";base64," in raw:
            header, encoded = raw.split(",", 1)
            mime_type = header[5:].split(";", 1)[0].strip() or fallback_mime
            return mime_type, base64.b64decode(encoded.encode("utf-8"), validate=False)
        return fallback_mime, base64.b64decode(raw.encode("utf-8"), validate=False)

    def _load_image_bytes(self, raw_bytes: bytes, mime_type: str) -> tuple[bytes, Any]:
        if mime_type == "application/pdf":
            image = self._image_from_pdf(raw_bytes)
            return self._encode_image(image), image
        return raw_bytes, self._open_image(raw_bytes)

    def _image_from_pdf(self, raw_bytes: bytes) -> Any:
        if fitz is None or Image is None:  # pragma: no cover
            raise RuntimeError("PDF preprocessing requires PyMuPDF and Pillow.")
        document = fitz.open(stream=raw_bytes, filetype="pdf")
        page = document.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        document.close()
        image = Image.open(BytesIO(pix.tobytes("png")))
        return image.convert("RGB")

    def _open_image(self, raw_bytes: bytes) -> Any:
        if Image is None:  # pragma: no cover
            raise RuntimeError("Pillow is required for image preprocessing.")
        image = Image.open(BytesIO(raw_bytes))
        return image.convert("RGB")

    def _enhance_image(self, image: Any) -> Any:
        if cv2 is not None and np is not None:
            array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            denoised = cv2.fastNlMeansDenoisingColored(array, None, 10, 10, 7, 21)
            lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            merged = cv2.merge((enhanced_l, a_channel, b_channel))
            contrast = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
            sharpen_kernel = np.array([[0, -1, 0], [-1, 5.4, -1], [0, -1, 0]], dtype=np.float32)
            sharpened = cv2.filter2D(contrast, -1, sharpen_kernel)
            return Image.fromarray(cv2.cvtColor(sharpened, cv2.COLOR_BGR2RGB))

        if ImageEnhance is None or ImageFilter is None:  # pragma: no cover
            return image
        contrast = ImageEnhance.Contrast(image).enhance(1.35)
        sharpened = ImageEnhance.Sharpness(contrast).enhance(1.5)
        return sharpened.filter(ImageFilter.MedianFilter(size=3))

    def _detect_roi(self, image: Any) -> Any:
        if cv2 is None or np is None:
            return image
        rgb = np.array(image)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image
        height, width = gray.shape[:2]
        page_area = height * width
        best = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(best)
        if w * h < page_area * 0.12:
            return image
        padding_x = max(12, int(w * 0.03))
        padding_y = max(12, int(h * 0.05))
        x0 = max(0, x - padding_x)
        y0 = max(0, y - padding_y)
        x1 = min(width, x + w + padding_x)
        y1 = min(height, y + h + padding_y)
        cropped = rgb[y0:y1, x0:x1]
        return Image.fromarray(cropped)

    def _deskew(self, image: Any) -> Any:
        if cv2 is None or np is None:
            return image
        rgb = np.array(image)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if coords.size == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        if abs(angle) < 0.4:
            return image
        height, width = gray.shape[:2]
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            rgb,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return Image.fromarray(rotated)

    def _finalize(self, image: Any) -> Any:
        if ImageOps is None or ImageEnhance is None:
            return image
        grayscale = ImageOps.grayscale(image)
        contrast = ImageEnhance.Contrast(grayscale).enhance(1.2)
        return contrast.convert("RGB")

    def _encode_image(self, image: Any) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _score_image_quality(self, image: Any) -> dict[str, int]:
        if cv2 is not None and np is not None:
            gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
            contrast = min(100.0, float(gray.std()) * 1.8)
            sharpness = min(100.0, cv2.Laplacian(gray, cv2.CV_64F).var() / 8.0)
            mean_brightness = float(gray.mean())
            brightness = max(0.0, 100.0 - abs(mean_brightness - 170.0) * 0.9)
            noise = max(0.0, 100.0 - min(100.0, float(cv2.meanStdDev(gray)[1][0][0]) * 1.1))
            overall = round((contrast * 0.26) + (sharpness * 0.34) + (brightness * 0.18) + (noise * 0.22))
            clarity = round((sharpness * 0.65) + (contrast * 0.35))
            return {
                "overall_score": max(0, min(100, int(overall))),
                "contrast_score": max(0, min(100, int(round(contrast)))),
                "sharpness_score": max(0, min(100, int(round(sharpness)))),
                "brightness_score": max(0, min(100, int(round(brightness)))),
                "noise_score": max(0, min(100, int(round(noise)))),
                "handwriting_clarity_score": max(0, min(100, int(clarity))),
            }

        size_score = 70
        if hasattr(image, "size"):
            width, height = image.size
            diagonal = math.sqrt((width * width) + (height * height))
            size_score = min(100, int(diagonal / 20))
        return {
            "overall_score": size_score,
            "contrast_score": size_score,
            "sharpness_score": size_score,
            "brightness_score": 75,
            "noise_score": 70,
            "handwriting_clarity_score": size_score,
        }
