async function testMicrophone() {
    const status = document.getElementById("micStatus");
    const levelBar = document.getElementById("levelBar");

    status.textContent = "⏳ Requesting permission...";
    status.className = "device-status checking";

    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Browser does not support media devices.");
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioDevices = devices.filter((device) => device.kind === "audioinput");

        if (audioDevices.length === 0) {
            status.textContent = "❌ No microphone found. Connect one and press Test again.";
            status.className = "device-status failed";
            return;
        }

        if (window._micStream) {
            window._micStream.getTracks().forEach((track) => track.stop());
        }

        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true },
        });

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (audioContext.state === "suspended") {
            await audioContext.resume();
        }
        const analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyser.fftSize = 256;
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const updateLevel = () => {
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            const percent = Math.min((average / 255) * 100, 100);
            levelBar.style.width = percent + "%";
            levelBar.style.background = percent > 10 ? "#34D399" : "#4F46E5";
            if (audioContext && audioContext.state === "running") {
                requestAnimationFrame(updateLevel);
            }
        };
        updateLevel();

        status.textContent = "✅ Microphone working";
        status.className = "device-status working";

        window._micStream = stream;
        window._micAudioContext = audioContext;
    } catch (error) {
        console.error("Mic error:", error);
        if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
            status.textContent = "❌ Mic blocked. Allow access in browser settings.";
        } else if (error.name === "NotFoundError") {
            status.textContent = "❌ No microphone detected. Connect one and try again.";
        } else {
            status.textContent = "❌ Mic error: " + error.message;
        }
        status.className = "device-status failed";
    }
}

async function checkMicDevices() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioDevices = devices.filter((device) => device.kind === "audioinput");
        let message = `Found ${audioDevices.length} microphone(s):\n`;
        audioDevices.forEach((device, index) => {
            message += `${index + 1}. ${device.label || "Unnamed mic"}\n`;
        });
        alert(message);
    } catch (error) {
        alert("Could not enumerate devices: " + error.message);
    }
}

async function testCamera() {
    const status = document.getElementById("cameraStatus");
    status.textContent = "⏳ Testing...";
    status.className = "device-status checking";

    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Browser does not support camera access.");
        }
        if (window._cameraStream) {
            window._cameraStream.getTracks().forEach((track) => track.stop());
        }

        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        const video = document.getElementById("cameraPreview");
        video.srcObject = stream;
        status.textContent = "✅ Camera working";
        status.className = "device-status working";
        window._cameraStream = stream;
    } catch (error) {
        status.textContent = "❌ Camera blocked";
        status.className = "device-status failed";
        alert("Please allow camera access in your browser settings.");
    }
}

async function testVideo() {
    const status = document.getElementById("videoStatus");
    status.textContent = "⏳ Testing...";
    status.className = "device-status checking";

    try {
        const response = await fetch("/telemedicine/start");
        if (response.ok) {
            status.textContent = "✅ Video ready";
            status.className = "device-status working";
        } else {
            status.textContent = "❌ Video not ready";
            status.className = "device-status failed";
        }
    } catch (error) {
        status.textContent = "❌ Video error";
        status.className = "device-status failed";
    }
}

function capturePhoto() {
    const video = document.getElementById("cameraPreview");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);
    canvas.toBlob(function (blob) {
        const formData = new FormData();
        formData.append("description", "Captured tongue image from device check");
        formData.append("patient_id", "1");
        if (blob) {
            formData.append("image", blob, "capture.jpg");
        }

        fetch("/api/tongue-analyze?patient_id=1", { method: "POST", body: formData })
            .then((response) => response.json())
            .then((data) => {
                if (data.success) {
                    alert(
                        "🔬 Tongue Diagnosis:\n\n" +
                        "Diagnosis: " + (data.diagnosis || "Generated") + "\n" +
                        "Prakriti: " + (data.prakriti || "Not specified") + "\n" +
                        "Confidence: " + Math.round(Number(data.confidence || 0) * 100) + "%\n\n" +
                        "Recommendations:\n" + (data.recommendations || []).join("\n")
                    );
                } else {
                    alert("Error: " + (data.error || "Analysis failed"));
                }
            })
            .catch(() => alert("Tongue analysis failed. Please try again."));
    }, "image/jpeg");
}

window.addEventListener("beforeunload", function () {
    if (window._micStream) {
        window._micStream.getTracks().forEach((track) => track.stop());
    }
    if (window._micAudioContext) {
        window._micAudioContext.close();
    }
    if (window._cameraStream) {
        window._cameraStream.getTracks().forEach((track) => track.stop());
    }
});
