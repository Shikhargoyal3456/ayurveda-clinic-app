(function () {
    const app = document.getElementById("prescriptionDecoderApp");
    if (!app) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const fileInput = document.getElementById("prescriptionImage");
    const fileNameNode = document.getElementById("fileName");
    const enhanceToggle = document.getElementById("enhanceToggle");
    const enhanceBtn = document.getElementById("enhanceBtn");
    const decodeBtn = document.getElementById("decodeBtn");
    const loadingSection = document.getElementById("loadingSection");
    const loadingMessage = document.getElementById("loadingMessage");
    const resultSection = document.getElementById("resultSection");
    const decodedContent = document.getElementById("decodedContent");
    const originalPreview = document.getElementById("originalPreview");
    const originalPreviewPlaceholder = document.getElementById("originalPreviewPlaceholder");
    const enhancedPreview = document.getElementById("enhancedPreview");
    const enhancedPreviewPlaceholder = document.getElementById("enhancedPreviewPlaceholder");
    const manualEditor = document.getElementById("manualEditor");
    const feedbackBtn = document.getElementById("feedbackBtn");
    const downloadBtn = document.getElementById("downloadDecodedTextBtn");

    const state = {
        uploadedFile: null,
        enhancedImage: null,
        decodedResult: null,
    };

    fileInput?.addEventListener("change", onFileSelected);
    enhanceBtn?.addEventListener("click", enhanceImage);
    decodeBtn?.addEventListener("click", decodePrescription);
    feedbackBtn?.addEventListener("click", submitFeedback);
    downloadBtn?.addEventListener("click", downloadDecodedText);

    function onFileSelected(event) {
        state.uploadedFile = event.target.files[0] || null;
        state.enhancedImage = null;
        state.decodedResult = null;
        resultSection.hidden = true;
        clearNode(decodedContent);
        manualEditor.value = "";

        if (!state.uploadedFile) {
            fileNameNode.textContent = "No file selected yet.";
            decodeBtn.disabled = true;
            enhanceBtn.disabled = true;
            setPreview(originalPreview, originalPreviewPlaceholder, "");
            setPreview(enhancedPreview, enhancedPreviewPlaceholder, "");
            return;
        }

        fileNameNode.textContent = `Selected: ${state.uploadedFile.name}`;
        decodeBtn.disabled = false;
        enhanceBtn.disabled = false;

        const reader = new FileReader();
        reader.onload = () => setPreview(originalPreview, originalPreviewPlaceholder, String(reader.result || ""));
        reader.readAsDataURL(state.uploadedFile);
        setPreview(enhancedPreview, enhancedPreviewPlaceholder, "");
    }

    async function enhanceImage() {
        if (!state.uploadedFile) return;
        setLoading(true, "Enhancing image for clearer OCR...");
        try {
            const formData = new FormData();
            formData.append("prescription_image", state.uploadedFile);
            const payload = await postMultipart(app.dataset.enhanceEndpoint, formData);
            state.enhancedImage = payload.data;
            setPreview(enhancedPreview, enhancedPreviewPlaceholder, payload.data.image_data);
            fileNameNode.textContent = `Enhanced preview ready. Image quality: ${Number(payload.data.source_image_quality || 0)}%.`;
        } catch (error) {
            fileNameNode.textContent = error.message || "Could not enhance the prescription image.";
        } finally {
            setLoading(false);
        }
    }

    async function decodePrescription() {
        if (!state.uploadedFile) return;

        if (enhanceToggle.checked && !state.enhancedImage) {
            await enhanceImage();
        }

        setLoading(true, "Reading handwriting and verifying medicine names...");
        try {
            const formData = new FormData();
            formData.append("prescription_image", state.uploadedFile);
            const payload = await postMultipart(app.dataset.decodeEndpoint, formData);
            state.decodedResult = payload.data;
            renderDecodedResult(payload.data);
            fileNameNode.textContent = `Decoded: ${state.uploadedFile.name}`;
            if (payload.data.enhanced_preview) {
                setPreview(enhancedPreview, enhancedPreviewPlaceholder, payload.data.enhanced_preview);
            }
        } catch (error) {
            fileNameNode.textContent = error.message || "Unable to decode the prescription.";
        } finally {
            setLoading(false);
        }
    }

    async function submitFeedback() {
        if (!state.decodedResult) return;
        try {
            const firstMedicine = Array.isArray(state.decodedResult.medicines) && state.decodedResult.medicines[0]
                ? state.decodedResult.medicines[0].medicine_name
                : "";
            const formData = new FormData();
            formData.append("medicine_name", firstMedicine || "");
            formData.append("note", manualEditor.value.trim() || "User marked decoder result as incorrect.");
            await postMultipart(app.dataset.feedbackEndpoint, formData);
            feedbackBtn.textContent = "Feedback sent";
            feedbackBtn.disabled = true;
        } catch (error) {
            feedbackBtn.textContent = "Feedback failed";
        }
    }

    function renderDecodedResult(data) {
        clearNode(decodedContent);
        resultSection.hidden = false;
        feedbackBtn.disabled = false;
        feedbackBtn.textContent = "This is incorrect";

        decodedContent.appendChild(renderMetaGrid(data));
        decodedContent.appendChild(renderQualityCard(data));

        if (Array.isArray(data.medicines) && data.medicines.length) {
            decodedContent.appendChild(renderMedicines(data.medicines));
        }

        if (data.raw_decoded_text) {
            const rawCard = document.createElement("div");
            rawCard.className = "raw-text-card";
            rawCard.appendChild(makeText("h3", "Full interpretation"));
            rawCard.appendChild(makeText("p", data.raw_decoded_text));
            decodedContent.appendChild(rawCard);
        }

        if (Array.isArray(data.unreadable_parts) && data.unreadable_parts.length) {
            const unreadable = document.createElement("div");
            unreadable.className = "unreadable-note";
            unreadable.appendChild(makeText("strong", "Could not clearly read"));
            const list = document.createElement("ul");
            data.unreadable_parts.forEach((part) => list.appendChild(makeText("li", part)));
            unreadable.appendChild(list);
            unreadable.appendChild(makeText("p", "Please verify these parts with your doctor or pharmacist."));
            decodedContent.appendChild(unreadable);
        }

        const summary = [
            `Overall AI confidence: ${Number(data.confidence_overall || 0)}%`,
            `Image quality: ${Number(data.source_image_quality || 0)}%`,
            data.requires_verification ? "Verification required" : "Low-risk decode",
        ].join("\n");
        manualEditor.value = summary;
    }

    function renderMetaGrid(data) {
        const metaGrid = document.createElement("div");
        metaGrid.className = "decoded-meta-grid";
        [
            ["Doctor", data.doctor_name || "Not clearly visible"],
            ["Patient", data.patient_name || "Not clearly visible"],
            ["Date", data.date || "Not clearly visible"],
            ["Verification", data.requires_verification ? "Required" : "Not flagged"],
        ].forEach(([label, value]) => {
            const card = document.createElement("div");
            card.className = "decoded-meta-card";
            card.appendChild(makeText("strong", label));
            card.appendChild(makeText("span", value, "decoded-meta"));
            metaGrid.appendChild(card);
        });
        return metaGrid;
    }

    function renderQualityCard(data) {
        const card = document.createElement("div");
        card.className = "quality-card";
        card.appendChild(makeText("h3", "Confidence breakdown"));
        const list = document.createElement("div");
        list.className = "image-quality-list";

        const quality = data.image_quality_breakdown || {};
        [
            `Overall image quality: ${Number(data.source_image_quality || 0)}%`,
            `Handwriting clarity: ${Number(quality.handwriting_clarity_score || 0)}%`,
            `Sharpness: ${Number(quality.sharpness_score || 0)}%`,
            `Contrast: ${Number(quality.contrast_score || 0)}%`,
            `Preprocessing: ${(data.applied_preprocessing || []).join(", ") || "None"}`,
        ].forEach((text) => list.appendChild(makeText("div", text, "detail-pill")));
        card.appendChild(list);
        return card;
    }

    function renderMedicines(medicines) {
        const section = document.createElement("section");
        section.className = "medicines-section";
        section.appendChild(makeText("h3", "Medicines prescribed"));

        medicines.forEach((med, index) => {
            const card = document.createElement("article");
            card.className = "medicine-card";

            const header = document.createElement("div");
            header.className = "medicine-card__header";
            header.appendChild(makeText("div", med.medicine_name || "Unclear medicine name", "medicine-name"));
            header.appendChild(makeText("span", `AI confidence: ${Number(med.confidence || 0)}%`, `confidence-badge ${confidenceClass(Number(med.confidence || 0))}`));
            card.appendChild(header);

            const detailList = document.createElement("div");
            detailList.className = "medicine-detail-list";
            const dosage = med.dosage || {};
            [
                `Dosage: ${joinParts([dosage.amount, dosage.unit]) || "Not clearly specified"}`,
                `Frequency: ${dosage.frequency || "Not clearly specified"}`,
                `Duration: ${dosage.duration || "Not clearly specified"}`,
                `Instructions: ${dosage.instructions || "Not clearly specified"}`,
                `Name match: ${Number(med.confidence_breakdown?.medicine_name_match_strength || 0)}%`,
                `Dosage match: ${Number(med.confidence_breakdown?.dosage_pattern_match_strength || 0)}%`,
            ].forEach((text) => detailList.appendChild(makeText("div", text, "detail-pill")));
            card.appendChild(detailList);

            if (Array.isArray(med.alternatives) && med.alternatives.length) {
                const altLabel = makeText("label", "Alternative medicine matches");
                altLabel.setAttribute("for", `alt-select-${index}`);
                card.appendChild(altLabel);

                const select = document.createElement("select");
                select.className = "suggestion-select";
                select.id = `alt-select-${index}`;
                select.appendChild(new Option(med.medicine_name || "Keep current result", med.medicine_name || ""));
                med.alternatives.forEach((alt) => select.appendChild(new Option(alt, alt)));
                select.addEventListener("change", () => {
                    if (!select.value) return;
                    header.firstChild.textContent = select.value;
                });
                card.appendChild(select);
            }

            const fetchButton = document.createElement("button");
            fetchButton.type = "button";
            fetchButton.className = "btn-modern btn-modern--secondary";
            fetchButton.textContent = "Refresh suggestions";
            fetchButton.addEventListener("click", async () => {
                const dosageHint = joinParts([dosage.amount, dosage.unit]);
                const suggestions = await fetchSuggestions(med.medicine_name || med.raw_line_text || "", dosageHint, dosage.frequency || "");
                if (suggestions.length) {
                    med.alternatives = suggestions.map((item) => item.medicine_name);
                    renderDecodedResult(state.decodedResult);
                }
            });
            card.appendChild(fetchButton);

            if (med.medicine_info) {
                const infoList = document.createElement("div");
                infoList.className = "medicine-info-list";
                const uses = Array.isArray(med.medicine_info.uses) ? med.medicine_info.uses.join(", ") : "";
                const sideEffects = Array.isArray(med.medicine_info.side_effects) ? med.medicine_info.side_effects.join(", ") : "";
                const freq = Array.isArray(med.medicine_info.common_frequencies) ? med.medicine_info.common_frequencies.join(", ") : "";
                if (uses) infoList.appendChild(makeText("p", `Used for: ${uses}`));
                if (sideEffects) infoList.appendChild(makeText("p", `Side effects: ${sideEffects}`));
                if (freq) infoList.appendChild(makeText("p", `Common frequency patterns: ${freq}`));
                infoList.appendChild(makeText("p", `Category: ${med.medicine_info.category || med.category || "Unknown"}`));
                infoList.appendChild(makeText("p", `Prescription required: ${med.medicine_info.prescription_required ? "Yes" : "Usually no"}`));
                card.appendChild(infoList);
            }

            if (med.requires_verification) {
                card.appendChild(makeText("div", "This line should be verified manually before use.", "match-chip"));
            }

            section.appendChild(card);
        });

        return section;
    }

    async function fetchSuggestions(query, dosageHint, frequencyHint) {
        if (!query) return [];
        const formData = new FormData();
        formData.append("query", query);
        formData.append("dosage_hint", dosageHint || "");
        formData.append("frequency_hint", frequencyHint || "");
        try {
            const payload = await postMultipart(app.dataset.suggestEndpoint, formData);
            return Array.isArray(payload.data) ? payload.data : [];
        } catch (error) {
            return [];
        }
    }

    async function postMultipart(url, formData) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "X-CSRF-Token": csrfToken },
            body: formData,
        });
        const payload = await response.json();
        if (!response.ok || payload.success === false) {
            throw new Error(payload.error || payload.message || "Request failed.");
        }
        return payload;
    }

    function setLoading(isLoading, message) {
        loadingSection.hidden = !isLoading;
        if (message) loadingMessage.textContent = message;
    }

    function setPreview(imageNode, placeholderNode, src) {
        if (!src) {
            imageNode.hidden = true;
            imageNode.removeAttribute("src");
            placeholderNode.hidden = false;
            return;
        }
        imageNode.src = src;
        imageNode.hidden = false;
        placeholderNode.hidden = true;
    }

    function downloadDecodedText() {
        const content = [decodedContent.innerText.trim(), manualEditor.value.trim()].filter(Boolean).join("\n\n");
        if (!content) return;
        const blob = new Blob([content], { type: "text/plain" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "decoded-prescription.txt";
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function clearNode(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function makeText(tag, text, className = "") {
        const node = document.createElement(tag);
        if (className) node.className = className;
        node.textContent = text;
        return node;
    }

    function confidenceClass(value) {
        if (value >= 70) return "confidence-high";
        if (value >= 40) return "confidence-medium";
        return "confidence-low";
    }

    function joinParts(parts) {
        return parts.filter(Boolean).join(" ").trim();
    }
})();
