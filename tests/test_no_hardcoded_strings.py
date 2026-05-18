from __future__ import annotations

import os
import re


def test_no_hardcoded_dashboard_strings():
    health_phrase = "Health" + " score"
    care_phrase = "care" + " score"
    balanced_phrase = "Balanced" + " patient flow"
    startup_phrase = "Startup" + " advantage"
    product_phrase = "Your strongest" + " product"
    clinic_phrase = "Clinic" + " command center"
    monitor_phrase = "Monitor health" + " metrics"
    quick_actions_phrase = "EMR quick" + " actions"
    registry_phrase = "Patient" + " registry"
    clinical_phrase = "Clinical" + " Dashboard"
    consult_phrase = 'aria-label="New' + ' Consultation"'
    forbidden_patterns = [
        re.escape(health_phrase),
        re.escape(care_phrase),
        re.escape(balanced_phrase),
        re.escape(startup_phrase),
        re.escape(product_phrase),
        re.escape(clinic_phrase),
        re.escape(monitor_phrase),
        re.escape(quick_actions_phrase),
        re.escape(registry_phrase),
        re.escape(clinical_phrase),
        re.escape(consult_phrase),
    ]

    violations: list[str] = []
    for root, _dirs, files in os.walk("templates"):
        for file_name in files:
            if not file_name.endswith(".html"):
                continue
            path = os.path.join(root, file_name)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            for pattern in forbidden_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(f"{path}: {pattern}")

    for root, _dirs, files in os.walk("apps"):
        for file_name in files:
            if not file_name.endswith(".html"):
                continue
            path = os.path.join(root, file_name)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            for pattern in forbidden_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(f"{path}: {pattern}")

    assert violations == [], f"Hardcoded UI strings found: {violations}"
