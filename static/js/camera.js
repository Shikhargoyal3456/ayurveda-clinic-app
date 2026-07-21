(() => {
  const fileInput = document.getElementById("tongueImageInput");
  const captureBtn = document.getElementById("captureTongueBtn");
  const analyzeBtn = document.getElementById("analyzeTongueBtn");
  const preview = document.getElementById("tongueCameraPreview");
  const resultBox = document.getElementById("tongueAnalysisResult");
  if (!fileInput || !captureBtn || !analyzeBtn || !resultBox) return;

  let stream = null;
  let selectedFile = null;

  const render = (payload) => {
    resultBox.innerHTML = payload?.analysis_text
      ? `<div class="alert alert-success"><strong>${payload.prakriti_prediction || "Analysis complete"}</strong><p class="mb-0 mt-2">${payload.analysis_text}</p></div>`
      : `<div class="alert alert-warning">No analysis available.</div>`;
  };

  const upload = async () => {
    const formData = new FormData();
    if (selectedFile) formData.append("image", selectedFile);
    const response = await fetch(`/api/tongue-analyze?patient_id=${window.kashConsultContext?.patientId || 0}`, {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) throw new Error(payload.error || "Tongue analysis failed");
    render(payload.analysis);
  };

  fileInput.addEventListener("change", () => {
    selectedFile = fileInput.files?.[0] || null;
  });

  captureBtn.addEventListener("click", async () => {
    try {
      stream = stream || await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (preview && !preview.srcObject) preview.srcObject = stream;
      const canvas = document.createElement("canvas");
      canvas.width = preview.videoWidth || 1280;
      canvas.height = preview.videoHeight || 720;
      canvas.getContext("2d").drawImage(preview, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (blob) selectedFile = new File([blob], "tongue-capture.png", { type: blob.type || "image/png" });
        upload().catch((error) => (resultBox.innerHTML = `<div class="alert alert-danger">${error.message}</div>`));
      }, "image/png");
    } catch (error) {
      resultBox.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
    }
  });

  analyzeBtn.addEventListener("click", () => {
    upload().catch((error) => (resultBox.innerHTML = `<div class="alert alert-danger">${error.message}</div>`));
  });
})();
