class VoiceRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.stream = null;
        this.mimeType = "";
    }

    getSupportedMimeType() {
        const candidates = [
            "audio/webm;codecs=opus",
            "audio/webm",
            "audio/mp4",
        ];
        return candidates.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || "";
    }

    async start() {
        this.stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        this.mimeType = this.getSupportedMimeType();
        this.mediaRecorder = this.mimeType
            ? new MediaRecorder(this.stream, { mimeType: this.mimeType })
            : new MediaRecorder(this.stream);

        this.audioChunks = [];
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                this.audioChunks.push(event.data);
            }
        };
        this.mediaRecorder.start();
        this.isRecording = true;
    }

    stop() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === "inactive") {
                resolve(null);
                return;
            }

            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.audioChunks, { type: this.mimeType || "audio/webm" });
                this.isRecording = false;
                this.mediaRecorder = null;
                this.audioChunks = [];
                resolve(blob.size > 0 ? blob : null);
            };

            this.mediaRecorder.stop();
            if (this.stream) {
                this.stream.getTracks().forEach((track) => track.stop());
                this.stream = null;
            }
        });
    }
}

export const voiceRecorder = new VoiceRecorder();
