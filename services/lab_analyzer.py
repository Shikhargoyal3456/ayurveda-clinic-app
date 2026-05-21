from __future__ import annotations

import json
import logging
import re
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any

try:  # pragma: no cover
    from PIL import Image, ImageEnhance, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageEnhance = None
    ImageOps = None

try:  # pragma: no cover
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:  # pragma: no cover
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None

try:  # pragma: no cover
    from pdf2image import convert_from_bytes
except Exception:  # pragma: no cover
    convert_from_bytes = None

try:  # pragma: no cover
    import fitz
except Exception:  # pragma: no cover
    fitz = None

try:  # pragma: no cover
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None

from services.ai_provider import GEMINI_API_KEY, GEMINI_MODEL, AI_TIMEOUT, call_ai_json_with_retry


logger = logging.getLogger(__name__)


def clean_extracted_text(text: str) -> str:
    """Minimal OCR cleanup that preserves line structure for lab parsing."""
    if not text:
        return ""

    cleaned = str(text).replace("\x00", " ")
    cleaned = _repair_spaced_letters(cleaned)
    cleaned = re.sub(r"[ \t]+([.,?!:;])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _repair_spaced_letters(text: str) -> str:
    lines = []
    for line in str(text or "").splitlines():
        parts = re.split(r"(\s{2,})", line)
        repaired_parts = []
        for part in parts:
            if not part or re.fullmatch(r"\s{2,}", part):
                repaired_parts.append(part)
                continue
            tokens = part.split()
            if tokens and all(len(token) == 1 and token.isalpha() for token in tokens):
                if len(tokens) >= 4 or all(token.isupper() for token in tokens):
                    repaired_parts.append("".join(tokens))
                    continue
            repaired_parts.append(part)
        lines.append("".join(repaired_parts))
    return "\n".join(lines)


class LabReportAnalyzer:
    """Analyze uploaded lab reports using OCR, heuristics, and optional AI summarization."""

    def __init__(self) -> None:
        self._configure_tesseract()
        self.test_catalog: dict[str, dict[str, Any]] = {
            "hemoglobin": {
                "aliases": ["hb", "haemoglobin", "hemoglobin"],
                "range": {"male": (13.5, 17.5), "female": (12.0, 15.5), "unit": "g/dL"},
                "low_meaning": "Low hemoglobin can suggest anemia, iron deficiency, blood loss, or chronic illness.",
                "high_meaning": "High hemoglobin can happen with dehydration, smoking, lung disease, or other causes that need review.",
                "low_recommendation": "Discuss anemia workup with your doctor and review iron, B12, folate, diet, and bleeding history.",
                "high_recommendation": "Repeat the test with hydration and ask your doctor if smoking, altitude, or lung issues may be involved.",
            },
            "rbc": {
                "aliases": ["rbc", "red blood cells"],
                "range": {"male": (4.5, 5.9), "female": (4.0, 5.2), "unit": "million/uL"},
                "low_meaning": "Low RBC count may support anemia or reduced red blood cell production.",
                "high_meaning": "High RBC count may happen with dehydration or conditions that increase red blood cell production.",
                "low_recommendation": "Review symptoms like fatigue or breathlessness and ask whether iron, B12, and folate testing is needed.",
                "high_recommendation": "Stay hydrated and discuss whether this needs repeat testing or further evaluation.",
            },
            "wbc": {
                "aliases": ["wbc", "white blood cells", "tlc", "total leukocyte count"],
                "range": (4.5, 11.0),
                "unit": "x10^3/uL",
                "low_meaning": "Low white blood cells can reduce infection-fighting ability and may be seen with viral illness, medicines, or marrow suppression.",
                "high_meaning": "High white blood cells often suggest infection, inflammation, stress response, or less commonly blood disorders.",
                "low_recommendation": "Discuss medicine history, recent infections, and whether repeat CBC is needed.",
                "high_recommendation": "Correlate with fever, infection symptoms, and ask your doctor whether additional workup is needed.",
            },
            "platelets": {
                "aliases": ["platelets", "plt"],
                "range": (150, 450),
                "unit": "x10^3/uL",
                "low_meaning": "Low platelets can increase bleeding risk depending on how low the count is.",
                "high_meaning": "High platelets may happen after infection, inflammation, iron deficiency, or other conditions.",
                "low_recommendation": "Seek timely medical review if you have bruising, bleeding, or very low counts.",
                "high_recommendation": "Discuss whether this is reactive or if repeat CBC and iron studies are needed.",
            },
            "hematocrit": {
                "aliases": ["hct", "hematocrit", "pcv"],
                "range": {"male": (41, 53), "female": (36, 46), "unit": "%"},
                "low_meaning": "Low hematocrit can support anemia, blood loss, or low red blood cell volume.",
                "high_meaning": "High hematocrit may happen with dehydration or conditions that increase red cell concentration.",
                "low_recommendation": "Review anemia symptoms and correlate this with hemoglobin, RBC count, and iron studies.",
                "high_recommendation": "Repeat testing with hydration and discuss whether further evaluation is needed.",
            },
            "mcv": {
                "aliases": ["mcv", "mean corpuscular volume"],
                "range": (80, 100),
                "unit": "fL",
                "low_meaning": "Low MCV suggests smaller-than-usual red blood cells, often seen with iron deficiency or thalassemia traits.",
                "high_meaning": "High MCV suggests larger-than-usual red blood cells and can happen with B12, folate, liver, or thyroid issues.",
                "low_recommendation": "Review iron studies and anemia workup with your doctor.",
                "high_recommendation": "Discuss B12, folate, liver, thyroid, and medicine review with your doctor.",
            },
            "mch": {
                "aliases": ["mch", "mean corpuscular hemoglobin"],
                "range": (27, 33),
                "unit": "pg",
                "low_meaning": "Low MCH suggests less hemoglobin per red blood cell, often seen with iron deficiency states.",
                "high_meaning": "High MCH can happen when red blood cells are larger or when anemia patterns need correlation with MCV.",
                "low_recommendation": "Review this with hemoglobin, MCV, ferritin, and iron studies.",
                "high_recommendation": "Correlate with CBC indices and review with your doctor.",
            },
            "mchc": {
                "aliases": ["mchc", "mean corpuscular hemoglobin concentration"],
                "range": (32, 36),
                "unit": "g/dL",
                "low_meaning": "Low MCHC suggests lower hemoglobin concentration inside red blood cells and can support iron deficiency patterns.",
                "high_meaning": "High MCHC is less common and should be interpreted carefully with the full blood count.",
                "low_recommendation": "Review iron deficiency workup and CBC indices with your doctor.",
                "high_recommendation": "Repeat the test if needed and discuss the full blood count with your doctor.",
            },
            "lymphocytes": {
                "aliases": ["lymphocytes", "lymphocyte", "lymphocyte %", "lymphocytes %"],
                "range": (20, 40),
                "unit": "%",
                "low_meaning": "Low lymphocytes may be seen with infections, stress response, steroid exposure, or immune-related issues.",
                "high_meaning": "High lymphocytes may happen with viral infections or other immune responses.",
                "low_recommendation": "Correlate with recent illness, medicines, and repeat CBC if advised.",
                "high_recommendation": "Review with symptoms and the rest of the differential count.",
            },
            "esr": {
                "aliases": ["esr", "erythrocyte sedimentation rate"],
                "range": (0, 20),
                "unit": "mm/hr",
                "low_meaning": "Low ESR is usually not concerning on its own.",
                "high_meaning": "High ESR can suggest inflammation, infection, autoimmune activity, or other conditions that need context.",
                "low_recommendation": "Usually no action is needed if the rest of the report and symptoms are reassuring.",
                "high_recommendation": "Discuss this with your doctor along with symptoms, CRP, infection history, or inflammatory conditions.",
            },
            "creatinine": {
                "aliases": ["creatinine", "crea", "serum creatinine"],
                "range": {"male": (0.7, 1.3), "female": (0.6, 1.1), "unit": "mg/dL"},
                "low_meaning": "Low creatinine is usually less concerning and can be seen with low muscle mass.",
                "high_meaning": "High creatinine may indicate reduced kidney function, dehydration, or medication effects.",
                "low_recommendation": "Usually review only if it does not fit the clinical picture.",
                "high_recommendation": "Review kidney function, hydration, blood pressure, diabetes status, and medications with your doctor.",
            },
            "blood_sugar": {
                "aliases": ["blood sugar", "glucose", "fbs", "fasting blood sugar", "rbs", "random blood sugar"],
                "range": (70, 140),
                "unit": "mg/dL",
                "low_meaning": "Low blood sugar can cause sweating, shakiness, confusion, and weakness.",
                "high_meaning": "High blood sugar can suggest diabetes, prediabetes, stress response, or poor glucose control.",
                "low_recommendation": "Review symptoms, diabetes medicines, and urgent care needs if low sugar symptoms are present.",
                "high_recommendation": "Discuss HbA1c, diet, exercise, and whether repeat fasting or post-meal testing is needed.",
            },
            "cholesterol": {
                "aliases": ["cholesterol", "total cholesterol"],
                "range": (125, 200),
                "unit": "mg/dL",
                "low_meaning": "Low total cholesterol is usually less concerning unless there are nutrition or absorption issues.",
                "high_meaning": "High total cholesterol can increase long-term cardiovascular risk.",
                "low_recommendation": "Usually review in context of weight loss, nutrition, or chronic illness if relevant.",
                "high_recommendation": "Discuss diet, exercise, weight, family history, and whether full lipid management is needed.",
            },
            "triglycerides": {
                "aliases": ["triglycerides", "tg"],
                "range": (30, 150),
                "unit": "mg/dL",
                "low_meaning": "Low triglycerides are usually not dangerous on their own.",
                "high_meaning": "High triglycerides can be linked to diabetes, alcohol use, obesity, or metabolic syndrome.",
                "low_recommendation": "Usually no treatment is needed unless there are broader nutrition concerns.",
                "high_recommendation": "Review sugar intake, alcohol, weight, diabetes control, and repeat fasting lipids with your doctor.",
            },
            "hdl": {
                "aliases": ["hdl", "good cholesterol"],
                "range": (40, 60),
                "unit": "mg/dL",
                "low_meaning": "Low HDL means less protective cholesterol support for heart health.",
                "high_meaning": "Higher HDL is usually favorable in standard interpretation.",
                "low_recommendation": "Discuss exercise, smoking cessation, and overall lipid-risk reduction.",
                "high_recommendation": "Usually continue heart-healthy lifestyle habits.",
            },
            "ldl": {
                "aliases": ["ldl", "bad cholesterol"],
                "range": (0, 100),
                "unit": "mg/dL",
                "low_meaning": "Lower LDL is generally favorable for cardiovascular risk.",
                "high_meaning": "High LDL increases risk for heart disease and stroke over time.",
                "low_recommendation": "Usually continue heart-healthy habits unless your doctor advises otherwise.",
                "high_recommendation": "Review diet, exercise, family history, and whether lipid-lowering treatment is appropriate.",
            },
            "vitamin_d": {
                "aliases": ["vitamin d", "25-oh vitamin d", "25 oh vitamin d"],
                "range": (30, 100),
                "unit": "ng/mL",
                "low_meaning": "Low vitamin D can be associated with low bone support, muscle aches, and deficiency.",
                "high_meaning": "Very high vitamin D may happen with over-supplementation and can be harmful.",
                "low_recommendation": "Discuss supplementation, sun exposure, diet, and repeat testing plan with your doctor.",
                "high_recommendation": "Review supplement doses and ask whether you should pause or adjust them.",
            },
            "b12": {
                "aliases": ["vitamin b12", "cobalamin", "b12"],
                "range": (200, 900),
                "unit": "pg/mL",
                "low_meaning": "Low B12 can contribute to anemia, numbness, tingling, fatigue, or nerve symptoms.",
                "high_meaning": "High B12 is often due to supplements but should be interpreted with history.",
                "low_recommendation": "Discuss diet, absorption issues, anemia symptoms, and whether supplementation is needed.",
                "high_recommendation": "Review supplement use and overall clinical context with your doctor.",
            },
            "tsh": {
                "aliases": ["tsh", "thyroid stimulating hormone"],
                "range": (0.4, 4.0),
                "unit": "uIU/mL",
                "low_meaning": "Low TSH may suggest overactive thyroid or excess thyroid hormone treatment.",
                "high_meaning": "High TSH may suggest underactive thyroid or insufficient thyroid replacement.",
                "low_recommendation": "Discuss symptoms like palpitations, weight loss, tremor, or thyroid medicine dosing.",
                "high_recommendation": "Discuss fatigue, weight gain, cold intolerance, and whether thyroid treatment is needed.",
            },
            "t3": {
                "aliases": ["t3", "triiodothyronine"],
                "range": (80, 200),
                "unit": "ng/dL",
                "low_meaning": "Low T3 can be seen in hypothyroidism or non-thyroidal illness.",
                "high_meaning": "High T3 may suggest hyperthyroidism.",
                "low_recommendation": "Interpret with TSH and T4 rather than alone.",
                "high_recommendation": "Review thyroid symptoms and complete thyroid profile with your doctor.",
            },
            "t4": {
                "aliases": ["t4", "thyroxine"],
                "range": (5, 12),
                "unit": "ug/dL",
                "low_meaning": "Low T4 can support hypothyroidism when correlated with TSH.",
                "high_meaning": "High T4 can support hyperthyroidism or excess thyroid replacement.",
                "low_recommendation": "Interpret with TSH and symptoms.",
                "high_recommendation": "Review thyroid symptoms and medication use with your doctor.",
            },
        }

    def _configure_tesseract(self) -> None:
        if pytesseract is None:  # pragma: no cover
            return
        executable = shutil.which("tesseract")
        if not executable:
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            executable = next((path for path in common_paths if Path(path).exists()), "")
        if executable:
            pytesseract.pytesseract.tesseract_cmd = executable

    async def extract_text_from_report(self, file_path: str, file_type: str) -> str:
        raw_bytes = Path(file_path).read_bytes()
        return self.extract_text_from_bytes(raw_bytes, file_type=file_type)

    def extract_text_from_bytes(self, file_bytes: bytes, file_type: str = "") -> str:
        normalized_type = (file_type or "").lower()
        if "pdf" in normalized_type:
            text = self._extract_text_from_pdf(file_bytes)
            if text:
                return text
            logger.warning("No readable text extracted from PDF report using built-in OCR pipelines.")
            return ""

        decoded = self._decode_text_bytes(file_bytes)
        if decoded:
            return decoded

        if self._looks_like_image(file_bytes):  # pragma: no cover
            if Image is None:
                logger.warning("Pillow is unavailable, skipping local OCR and trying Gemini OCR fallback.")
            elif not self._tesseract_is_ready():
                logger.warning("pytesseract or the Tesseract binary is unavailable, trying Gemini OCR fallback.")
            else:
                try:
                    image = self._prepare_image_for_ocr(Image.open(BytesIO(file_bytes)))
                    text = self._run_tesseract(image)
                    cleaned = self._normalize_extracted_text(text)
                    if cleaned:
                        return cleaned
                    logger.warning("Tesseract OCR returned no readable text, trying Gemini OCR fallback.")
                except Exception as exc:
                    logger.warning("Image OCR failed locally, trying Gemini OCR fallback: %s", exc)

            fallback_text = self._extract_text_with_gemini_vision(file_bytes, normalized_type or "image/png")
            if fallback_text:
                return fallback_text
            logger.error("No readable text extracted from image report after local and Gemini OCR attempts.")

        return ""

    def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        if pdfplumber is not None:  # pragma: no cover
            try:
                with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                cleaned = self._normalize_extracted_text(text)
                if self._looks_like_readable_report_text(cleaned):
                    return cleaned
            except Exception as exc:
                logger.debug("pdfplumber extraction failed: %s", exc)

        if fitz is not None:  # pragma: no cover
            try:
                with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                    text = "\n".join(page.get_text("text") for page in doc)
                cleaned = self._normalize_extracted_text(text)
                if self._looks_like_readable_report_text(cleaned):
                    return cleaned
            except Exception as exc:
                logger.debug("PyMuPDF text extraction failed: %s", exc)

        if fitz is not None and pytesseract is not None and Image is not None:  # pragma: no cover
            try:
                with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                    text = self._ocr_pdf_document(doc)
                cleaned = self._normalize_extracted_text(text)
                if cleaned:
                    return cleaned
            except Exception as exc:
                logger.debug("PyMuPDF OCR fallback failed: %s", exc)

        if convert_from_bytes is not None and pytesseract is not None:  # pragma: no cover
            try:
                pages = convert_from_bytes(file_bytes, first_page=1, last_page=3)
                text = "\n".join(self._run_tesseract(self._prepare_image_for_ocr(page)) for page in pages)
                cleaned = self._normalize_extracted_text(text)
                if cleaned:
                    return cleaned
            except Exception as exc:
                logger.debug("pdf2image OCR fallback failed: %s", exc)

        return ""

    def _ocr_pdf_document(self, document: Any) -> str:
        extracted_pages: list[str] = []
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            prepared = self._prepare_image_for_ocr(image)
            extracted_pages.append(self._run_tesseract(prepared))
        return "\n".join(extracted_pages)

    def _prepare_image_for_ocr(self, image: Any) -> Any:
        prepared = image.convert("L")
        if ImageOps is not None:
            prepared = ImageOps.autocontrast(prepared)
        if ImageEnhance is not None:
            prepared = ImageEnhance.Contrast(prepared).enhance(2.0)
            prepared = ImageEnhance.Sharpness(prepared).enhance(1.5)
        prepared = prepared.point(lambda pixel: 255 if pixel > 180 else 0)
        return prepared

    def _run_tesseract(self, image: Any) -> str:
        config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
        return pytesseract.image_to_string(image, lang="eng", config=config)

    def _tesseract_is_ready(self) -> bool:
        if pytesseract is None:
            return False
        configured_path = getattr(getattr(pytesseract, "pytesseract", None), "tesseract_cmd", "") or ""
        if configured_path and Path(configured_path).exists():
            return True
        return bool(shutil.which("tesseract"))

    def _extract_text_with_gemini_vision(self, file_bytes: bytes, file_type: str = "") -> str:
        if genai is None or types is None:
            logger.warning("Gemini OCR fallback unavailable because google-genai is not importable.")
            return ""
        if not GEMINI_API_KEY:
            logger.warning("Gemini OCR fallback unavailable because GEMINI_API_KEY is not configured.")
            return ""
        mime_type = file_type.strip() or "image/png"
        if "/" not in mime_type:
            mime_type = "image/png"
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    "Extract all readable text from this lab report image. Preserve line breaks and test/value pairs. Return only the extracted text.",
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    http_options=types.HttpOptions(timeout=AI_TIMEOUT * 1000),
                    temperature=0.0,
                    max_output_tokens=4096,
                ),
            )
            cleaned = self._normalize_extracted_text(response.text or "")
            if not cleaned:
                logger.warning("Gemini OCR fallback returned no readable text.")
            return cleaned
        except Exception as exc:
            logger.warning("Gemini OCR fallback failed: %s", exc)
            return ""

    def _decode_text_bytes(self, file_bytes: bytes) -> str:
        decoded = file_bytes.decode("utf-8", errors="ignore")
        return self._normalize_extracted_text(decoded)

    def _normalize_extracted_text(self, text: str) -> str:
        cleaned = clean_extracted_text(text)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return ""
        if self._looks_like_pdf_stream_text(cleaned):
            return ""
        return cleaned

    def _looks_like_pdf_stream_text(self, text: str) -> bool:
        lowered = text.lower()
        if "%pdf" in lowered or "endobj" in lowered or "stream" in lowered and "endstream" in lowered:
            return True
        printable_ratio = sum(1 for char in text if char.isprintable() or char in "\r\n\t") / max(len(text), 1)
        alpha_ratio = sum(1 for char in text if char.isalpha()) / max(len(text), 1)
        return printable_ratio < 0.85 or alpha_ratio < 0.2

    def _looks_like_readable_report_text(self, text: str) -> bool:
        if not text:
            return False
        alpha_count = sum(1 for char in text if char.isalpha())
        digit_count = sum(1 for char in text if char.isdigit())
        return len(text) >= 40 and alpha_count >= 20 and (digit_count > 0 or "range" in text.lower())

    def _looks_like_image(self, file_bytes: bytes) -> bool:
        signatures = (
            b"\x89PNG\r\n\x1a\n",
            b"\xff\xd8\xff",
            b"GIF87a",
            b"GIF89a",
            b"BM",
            b"RIFF",
        )
        return any(file_bytes.startswith(signature) for signature in signatures)

    async def parse_lab_values(self, text: str) -> dict[str, Any]:
        values: list[dict[str, Any]] = []
        seen_tests: set[str] = set()
        cleaned_text = str(text or "")

        for test_name, config in self.test_catalog.items():
            aliases = config["aliases"]
            alias_pattern = "|".join(re.escape(alias) for alias in aliases)
            pattern = re.compile(
                rf"(?<![A-Za-z])(?:{alias_pattern})(?:\s*\([^)]*\))?(?:\s+[A-Za-z/%]+){{0,3}}\s*(?:[:=\-]|\))?\s*(\d[\d,]*(?:\.\d+)?)",
                re.IGNORECASE,
            )
            match = pattern.search(cleaned_text)
            if not match:
                continue
            value = float(match.group(1).replace(",", ""))
            evaluation = self._evaluate_value(test_name, value, config)
            values.append(evaluation)
            seen_tests.add(test_name)

        return {
            "tests": values,
            "detected_tests": sorted(seen_tests),
            "raw_text_preview": cleaned_text[:1500],
        }

    async def analyze_with_ai(self, extracted_text: str, parsed_data: dict[str, Any]) -> dict[str, Any]:
        cleaned_text = extracted_text.strip()
        effective_text = cleaned_text or "No readable lab text could be extracted from the upload."

        detailed_prompt = (
            "You are a careful medical lab report explainer for patients.\n"
            "Suggest only possible diagnoses based on report patterns, never present them as confirmed diagnoses, "
            "and always recommend doctor consultation for urgent or abnormal results.\n"
            "Group related abnormal findings into likely patterns when relevant.\n"
            "Return strict JSON with keys: summary, diagnosis, abnormal_findings, normal_findings, recommendations.\n"
            "Diagnosis items must include: condition, confidence, evidence, confirmatory_tests.\n"
            "Each abnormal finding must include: test_name, value, normal_range, meaning, recommendation.\n"
            "Each normal finding must include: test_name, value, normal_range.\n\n"
            f"Extracted report text:\n{effective_text[:8000]}\n\n"
            f"Structured parsed data:\n{json.dumps(parsed_data, ensure_ascii=True, indent=2)}"
        )
        simpler_prompt = (
            "The following lab report text is incomplete or noisy. Explain only what can be reasonably inferred, "
            "point out missing information, and recommend uploading a clearer image if needed.\n\n"
            f"Extracted report text:\n{effective_text[:1500]}\n\n"
            'Return JSON with keys summary, diagnosis, abnormal_findings, normal_findings, recommendations.'
        )
        parsed, provider = await call_ai_json_with_retry(
            system_prompt=(
                "You explain lab reports safely and clearly. "
                "Do not invent values not present in the report. "
                "If values are incomplete, say so plainly."
            ),
            user_prompt=detailed_prompt,
            simpler_user_prompt=simpler_prompt,
            temperature=0.2,
            max_output_tokens=2048,
        )
        normalized = self._normalize_ai_payload(parsed)
        normalized["provider"] = provider
        return normalized

    def build_fallback_analysis(self, extracted_text: str, parsed_data: dict[str, Any], error: str = "") -> dict[str, Any]:
        tests = parsed_data.get("tests", [])
        abnormal_findings = []
        normal_findings = []

        for item in tests:
            if item["status"] == "normal":
                normal_findings.append(
                    {
                        "test_name": item["test_name"],
                        "value": item["formatted_value"],
                        "normal_range": item["normal_range"],
                    }
                )
            else:
                abnormal_findings.append(
                    {
                        "test_name": item["test_name"],
                        "value": item["formatted_value"],
                        "normal_range": item["normal_range"],
                        "meaning": item["meaning"],
                        "recommendation": item["recommendation"],
                    }
                )

        diagnosis = self._build_fallback_diagnosis(tests)

        if abnormal_findings:
            summary = (
                f"The report shows {len(abnormal_findings)} value(s) outside the usual reference range. "
                f"{' Possible patterns were identified for doctor review.' if diagnosis else ''} "
                "These results should be reviewed with your doctor in the context of your symptoms and history."
            )
        elif normal_findings:
            summary = (
                "The values that could be reliably read from this report are within the usual reference range. "
                "Please still review the full report with your doctor if you have symptoms or ongoing treatment."
            )
        else:
            summary = (
                "The uploaded report text was limited, so only a partial local summary could be created. "
                "You can still review the report with your doctor or try a clearer image or PDF."
            )

        recommendations = self._fallback_recommendations(abnormal_findings, bool(normal_findings), bool(extracted_text.strip()))
        payload: dict[str, Any] = {
            "summary": summary,
            "diagnosis": diagnosis,
            "abnormal_findings": abnormal_findings,
            "normal_findings": normal_findings,
            "recommendations": recommendations,
            "provider": "fallback",
        }
        if error:
            payload["warning"] = error
        return payload

    def _evaluate_value(self, test_name: str, value: float, config: dict[str, Any]) -> dict[str, Any]:
        low, high, display_range = self._range_bounds(config)
        status = "normal"
        meaning = "This value is within the usual reference range."
        recommendation = "Continue regular follow-up and discuss the report with your doctor if you have symptoms."
        if value < low:
            status = "low"
            meaning = config["low_meaning"]
            recommendation = config["low_recommendation"]
        elif value > high:
            status = "high"
            meaning = config["high_meaning"]
            recommendation = config["high_recommendation"]

        return {
            "code": test_name,
            "test_name": self._label_for_test(test_name),
            "value": value,
            "formatted_value": self._format_value(value, config),
            "normal_range": display_range,
            "status": status,
            "meaning": meaning,
            "recommendation": recommendation,
        }

    def _range_bounds(self, config: dict[str, Any]) -> tuple[float, float, str]:
        range_value = config["range"]
        unit = config.get("unit") or range_value.get("unit", "") if isinstance(range_value, dict) else config.get("unit", "")
        if isinstance(range_value, dict) and "male" in range_value and "female" in range_value:
            low = min(range_value["male"][0], range_value["female"][0])
            high = max(range_value["male"][1], range_value["female"][1])
            display = (
                f"Male: {range_value['male'][0]}-{range_value['male'][1]} {unit} | "
                f"Female: {range_value['female'][0]}-{range_value['female'][1]} {unit}"
            ).strip()
            return low, high, display
        if isinstance(range_value, tuple):
            low, high = range_value
            display = f"{low}-{high} {unit}".strip()
            return low, high, display
        low, high = 0.0, 0.0
        display = f"{low}-{high} {unit}".strip()
        return low, high, display

    def _format_value(self, value: float, config: dict[str, Any]) -> str:
        unit = config.get("unit") or config.get("range", {}).get("unit", "") if isinstance(config.get("range"), dict) else config.get("unit", "")
        number = str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{number} {unit}".strip()

    def _label_for_test(self, code: str) -> str:
        labels = {
            "hemoglobin": "Hemoglobin",
            "rbc": "RBC",
            "wbc": "WBC",
            "platelets": "Platelets",
            "hematocrit": "Hematocrit",
            "mcv": "MCV",
            "mch": "MCH",
            "mchc": "MCHC",
            "lymphocytes": "Lymphocytes",
            "esr": "ESR",
            "creatinine": "Creatinine",
            "blood_sugar": "Blood Sugar",
            "cholesterol": "Total Cholesterol",
            "triglycerides": "Triglycerides",
            "hdl": "HDL",
            "ldl": "LDL",
            "vitamin_d": "Vitamin D",
            "b12": "Vitamin B12",
            "tsh": "TSH",
            "t3": "T3",
            "t4": "T4",
        }
        return labels.get(code, code.replace("_", " ").title())

    def _normalize_ai_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        diagnosis = []
        for item in payload.get("diagnosis", []) or []:
            evidence = [
                clean_extracted_text(str(entry))
                for entry in (item.get("evidence") or [])
                if str(entry).strip()
            ]
            confirmatory_tests = [
                clean_extracted_text(str(entry))
                for entry in (item.get("confirmatory_tests") or item.get("recommended_tests") or [])
                if str(entry).strip()
            ]
            confidence = clean_extracted_text(str(item.get("confidence") or "Low")).title()
            if confidence not in {"High", "Medium", "Low"}:
                confidence = "Low"
            diagnosis.append(
                {
                    "condition": clean_extracted_text(str(item.get("condition") or item.get("name") or "Possible condition")),
                    "confidence": confidence,
                    "evidence": evidence,
                    "confirmatory_tests": confirmatory_tests,
                }
            )
        abnormal = []
        for item in payload.get("abnormal_findings", []) or []:
            abnormal.append(
                {
                    "test_name": clean_extracted_text(str(item.get("test_name") or item.get("test") or "Unknown Test")),
                    "value": clean_extracted_text(str(item.get("value") or "")),
                    "normal_range": clean_extracted_text(str(item.get("normal_range") or "Not provided")),
                    "meaning": clean_extracted_text(str(item.get("meaning") or "Please review this result with your doctor.")),
                    "recommendation": clean_extracted_text(str(item.get("recommendation") or "Discuss this result with your doctor.")),
                }
            )
        normal = []
        for item in payload.get("normal_findings", []) or []:
            normal.append(
                {
                    "test_name": clean_extracted_text(str(item.get("test_name") or item.get("test") or "Unknown Test")),
                    "value": clean_extracted_text(str(item.get("value") or "")),
                    "normal_range": clean_extracted_text(str(item.get("normal_range") or "Not provided")),
                }
            )
        recommendations = [clean_extracted_text(str(item)) for item in (payload.get("recommendations") or []) if str(item).strip()]
        if not recommendations:
            recommendations = ["Review the full report with your doctor, especially if you have symptoms or existing treatment."]
        return {
            "summary": clean_extracted_text(str(payload.get("summary") or "The report has been analyzed. Please review the findings below.")),
            "diagnosis": diagnosis,
            "abnormal_findings": abnormal,
            "normal_findings": normal,
            "recommendations": recommendations,
        }

    def _build_fallback_diagnosis(self, tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        indexed = {item.get("code"): item for item in tests}
        diagnosis = []

        hemoglobin = indexed.get("hemoglobin")
        mcv = indexed.get("mcv")
        mch = indexed.get("mch")
        mchc = indexed.get("mchc")
        rbc = indexed.get("rbc")
        wbc = indexed.get("wbc")
        esr = indexed.get("esr")
        creatinine = indexed.get("creatinine")
        blood_sugar = indexed.get("blood_sugar")
        tsh = indexed.get("tsh")
        t4 = indexed.get("t4")
        b12 = indexed.get("b12")
        vitamin_d = indexed.get("vitamin_d")
        ldl = indexed.get("ldl")
        cholesterol = indexed.get("cholesterol")
        triglycerides = indexed.get("triglycerides")

        if hemoglobin and hemoglobin["status"] == "low":
            evidence = [self._diagnosis_evidence(hemoglobin)]
            microcytic_markers = []
            for item in (mcv, mch, mchc, rbc):
                if item and item["status"] == "low":
                    evidence.append(self._diagnosis_evidence(item))
                    microcytic_markers.append(item)
            confidence = "High" if len(microcytic_markers) >= 2 else "Medium"
            condition = "Iron Deficiency Anemia" if microcytic_markers else "Possible Anemia"
            tests_to_confirm = ["Iron studies", "Serum ferritin", "TIBC", "Peripheral smear"]
            diagnosis.append(
                {
                    "condition": condition,
                    "confidence": confidence,
                    "evidence": evidence,
                    "confirmatory_tests": tests_to_confirm,
                }
            )

        inflammation_evidence = []
        for item in (wbc, esr):
            if item and item["status"] == "high":
                inflammation_evidence.append(self._diagnosis_evidence(item))
        if len(inflammation_evidence) >= 2:
            diagnosis.append(
                {
                    "condition": "Inflammatory Response",
                    "confidence": "Medium",
                    "evidence": inflammation_evidence,
                    "confirmatory_tests": ["CRP", "Clinical infection workup", "Temperature check"],
                }
            )
        elif inflammation_evidence:
            diagnosis.append(
                {
                    "condition": "Possible Infection or Inflammation",
                    "confidence": "Low",
                    "evidence": inflammation_evidence,
                    "confirmatory_tests": ["Repeat CBC", "CRP", "Clinical examination"],
                }
            )

        if creatinine and creatinine["status"] == "high":
            diagnosis.append(
                {
                    "condition": "Possible Kidney Function Impairment",
                    "confidence": "Medium",
                    "evidence": [self._diagnosis_evidence(creatinine)],
                    "confirmatory_tests": ["eGFR", "Blood urea nitrogen", "Urinalysis", "Repeat creatinine"],
                }
            )

        if blood_sugar and blood_sugar["status"] == "high":
            diagnosis.append(
                {
                    "condition": "Possible Hyperglycemia or Diabetes Pattern",
                    "confidence": "Medium",
                    "evidence": [self._diagnosis_evidence(blood_sugar)],
                    "confirmatory_tests": ["HbA1c", "Fasting glucose", "Postprandial glucose"],
                }
            )

        if tsh and tsh["status"] == "high":
            evidence = [self._diagnosis_evidence(tsh)]
            if t4 and t4["status"] == "low":
                evidence.append(self._diagnosis_evidence(t4))
            diagnosis.append(
                {
                    "condition": "Possible Hypothyroidism",
                    "confidence": "High" if t4 and t4["status"] == "low" else "Medium",
                    "evidence": evidence,
                    "confirmatory_tests": ["Free T4", "Repeat TSH", "Anti-TPO antibodies"],
                }
            )
        elif tsh and tsh["status"] == "low":
            evidence = [self._diagnosis_evidence(tsh)]
            if t4 and t4["status"] == "high":
                evidence.append(self._diagnosis_evidence(t4))
            diagnosis.append(
                {
                    "condition": "Possible Hyperthyroidism",
                    "confidence": "High" if t4 and t4["status"] == "high" else "Medium",
                    "evidence": evidence,
                    "confirmatory_tests": ["Free T4", "Free T3", "Repeat TSH"],
                }
            )

        if b12 and b12["status"] == "low":
            diagnosis.append(
                {
                    "condition": "Vitamin B12 Deficiency",
                    "confidence": "Medium",
                    "evidence": [self._diagnosis_evidence(b12)],
                    "confirmatory_tests": ["Methylmalonic acid", "Homocysteine", "Repeat B12 level"],
                }
            )

        if vitamin_d and vitamin_d["status"] == "low":
            diagnosis.append(
                {
                    "condition": "Vitamin D Deficiency",
                    "confidence": "Medium",
                    "evidence": [self._diagnosis_evidence(vitamin_d)],
                    "confirmatory_tests": ["Calcium", "Phosphorus", "Parathyroid hormone"],
                }
            )

        lipid_evidence = []
        for item in (ldl, cholesterol, triglycerides):
            if item and item["status"] == "high":
                lipid_evidence.append(self._diagnosis_evidence(item))
        if lipid_evidence:
            diagnosis.append(
                {
                    "condition": "Dyslipidemia",
                    "confidence": "Medium" if len(lipid_evidence) >= 2 else "Low",
                    "evidence": lipid_evidence,
                    "confirmatory_tests": ["Fasting lipid profile", "HbA1c", "Liver function tests"],
                }
            )

        return diagnosis

    def _diagnosis_evidence(self, item: dict[str, Any]) -> str:
        return f"{item['test_name']} {item['status']} ({item['formatted_value']}; normal {item['normal_range']})"

    def _fallback_recommendations(self, abnormal_findings: list[dict[str, Any]], has_normals: bool, has_text: bool) -> list[str]:
        recommendations = [
            "AI diagnosis is for informational purposes only. Always consult a doctor.",
            "This AI summary is informational only and should be reviewed with your doctor.",
        ]
        if abnormal_findings:
            recommendations.append("Book a doctor consultation if you have symptoms, are pregnant, have chronic illness, or take regular medicines.")
            recommendations.append("Do not start or stop treatment only from this report summary without clinician advice.")
        elif has_normals:
            recommendations.append("Keep routine follow-up if the test was done for ongoing treatment, screening, or chronic disease monitoring.")
        if not has_text:
            recommendations.append("Upload a clearer PDF or photo if the report could not be read well.")
        return recommendations
