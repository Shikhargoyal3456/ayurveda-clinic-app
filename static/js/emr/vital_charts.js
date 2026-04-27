const VitalCharts = {
    drawLine(canvasId, data, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !canvas.getContext) return;
        const ctx = canvas.getContext("2d");
        const width = canvas.width || canvas.clientWidth || 320;
        const height = canvas.height || 140;
        canvas.width = width;
        canvas.height = height;
        ctx.clearRect(0, 0, width, height);
        if (!data.length) return;
        const max = Math.max(...data, 1);
        const min = Math.min(...data, 0);
        const range = Math.max(1, max - min);
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.beginPath();
        data.forEach((point, index) => {
            const x = (index / Math.max(1, data.length - 1)) * (width - 24) + 12;
            const y = height - (((point - min) / range) * (height - 24) + 12);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    },
    createBPChart(data) {
        this.drawLine("vitalTrendChart", data, "#2d6a4f");
    },
    createWeightChart(data) {
        this.drawLine("weightTrendChart", data, "#4a9be6");
    },
    createGlucoseChart(data) {
        this.drawLine("glucoseTrendChart", data, "#ffb703");
    },
    updateRealTime(vital) {
        if (window.showToast) window.showToast(`${vital} trend refreshed`, "info");
    },
};

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("vitalTrendChart")) {
        VitalCharts.createBPChart([118, 122, 120, 126, 124, 119]);
    }
    if (document.getElementById("weightTrendChart")) {
        VitalCharts.createWeightChart([72, 71.5, 71.3, 70.9, 70.4, 70.2]);
    }
});

window.VitalCharts = VitalCharts;
