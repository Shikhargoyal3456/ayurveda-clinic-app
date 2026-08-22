(() => {
  const state = {
    days: 30,
    startDate: "",
    endDate: "",
    charts: {},
    snapshot: window.doctorStatsSnapshot || null,
  };

  const colors = ["#5FE0A8", "#2FC98A", "#E8B24A", "#f59e0b", "#ef4444", "#22c55e"];

  const qs = (sel) => document.querySelector(sel);

  const formatCurrency = (value) => `₹${Number(value || 0).toLocaleString("en-IN")}`;

  async function fetchStats(days = state.days, startDate = "", endDate = "") {
    state.days = days;
    const endpoints = [
      "/api/stats/overview",
      "/api/stats/patients",
      "/api/stats/ai-performance",
      "/api/stats/revenue",
      "/api/stats/operations",
      "/api/stats/outcomes",
    ];
    const query = new URLSearchParams({ days: String(days) });
    if (startDate) query.set("start_date", startDate);
    if (endDate) query.set("end_date", endDate);
    const results = await Promise.all(endpoints.map((url) => fetch(`${url}?${query.toString()}`).then((response) => response.json())));
    return {
      overview: results[0].data,
      patients: results[1].data,
      ai: results[2].data,
      revenue: results[3].data,
      operations: results[4].data,
      outcomes: results[5].data,
    };
  }

  function renderCards(data) {
    const host = qs("#overviewCards");
    if (!host) return;
    const cards = [
      ["👤 Total Patients", data.overview.total_patients],
      ["📅 Today’s Appointments", data.overview.appointments_today],
      ["💰 Revenue This Month", formatCurrency(data.overview.revenue_month)],
      ["⭐ Avg Satisfaction", `${Number(data.overview.average_satisfaction || 0).toFixed(1)} ⭐`],
      ["📈 Completion Rate", `${Number(data.overview.completion_rate || 0).toFixed(1)}%`],
    ];
    host.innerHTML = cards.map(([label, value]) => `<article class="card kpi-card"><span>${label}</span><strong>${value}</strong></article>`).join("");
  }

  function createChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (state.charts[canvasId]) {
      state.charts[canvasId].destroy();
    }
    state.charts[canvasId] = new Chart(canvas, config);
    return state.charts[canvasId];
  }

  function renderCharts(data) {
    createChart("newPatientsChart", {
      type: "line",
      data: {
        labels: data.patients.new_patients_trend.map((item) => item.date),
        datasets: [{ label: "New Patients", data: data.patients.new_patients_trend.map((item) => item.count), borderColor: colors[0], backgroundColor: "rgba(102,241,214,.16)", tension: 0.35 }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    createChart("demographicsChart", {
      type: "pie",
      data: {
        labels: data.patients.demographics.age_groups.map((item) => item.label),
        datasets: [{ data: data.patients.demographics.age_groups.map((item) => item.value), backgroundColor: colors }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    createChart("aiPerformanceChart", {
      type: "bar",
      data: {
        labels: ["Cases with AI", "Accuracy", "Avg Time w/ AI", "Avg Time w/o AI"],
        datasets: [{ label: "AI", data: [data.ai.cases_with_ai, data.ai.accuracy, data.ai.avg_with_ai, data.ai.avg_without_ai], backgroundColor: colors[1] }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    createChart("revenueTrendChart", {
      type: "bar",
      data: {
        labels: data.revenue.monthly_trend.map((item) => item.label),
        datasets: [{ label: "Revenue", data: data.revenue.monthly_trend.map((item) => item.value), backgroundColor: colors[2] }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    createChart("operationsChart", {
      type: "doughnut",
      data: {
        labels: data.operations.appointment_status.map((item) => item.label),
        datasets: [{ data: data.operations.appointment_status.map((item) => item.value), backgroundColor: colors }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    createChart("outcomesChart", {
      type: "bar",
      data: {
        labels: data.outcomes.common_diagnoses.map((item) => item.label).slice(0, 8),
        datasets: [{ label: "Diagnoses", data: data.outcomes.common_diagnoses.map((item) => item.value).slice(0, 8), backgroundColor: colors[4] }],
      },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: "y" },
    });
    createChart("serviceRevenueChart", {
      type: "doughnut",
      data: {
        labels: data.revenue.by_service.map((item) => item.label),
        datasets: [{ data: data.revenue.by_service.map((item) => item.value), backgroundColor: colors }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    const medicines = qs("#topMedicines");
    if (medicines) {
      medicines.innerHTML = data.ai.top_medicines.map((item, index) => `<div class="list-item"><strong>${index + 1}. ${item.label}</strong><span>${item.value}</span></div>`).join("");
    }
  }

  async function updateDateRange(days, startDate = "", endDate = "") {
    state.startDate = startDate;
    state.endDate = endDate;
    const data = await fetchStats(days, startDate, endDate);
    renderCards(data);
    renderCharts(data);
    const exportButton = qs("#exportCsv");
    if (exportButton) {
      const exportQuery = new URLSearchParams({ format: "csv", days: String(days) });
      if (startDate) exportQuery.set("start_date", startDate);
      if (endDate) exportQuery.set("end_date", endDate);
      exportButton.href = `/api/stats/export?${exportQuery.toString()}`;
    }
  }

  function exportData() {
    const query = new URLSearchParams({ format: "csv", days: String(state.days) });
    if (state.startDate) query.set("start_date", state.startDate);
    if (state.endDate) query.set("end_date", state.endDate);
    window.location.href = `/api/stats/export?${query.toString()}`;
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (target.matches(".range-btn")) {
      document.querySelectorAll(".range-btn").forEach((button) => button.classList.remove("active"));
      target.classList.add("active");
      updateDateRange(Number(target.dataset.days || 30));
    }
  });

  document.addEventListener("DOMContentLoaded", async () => {
    const printButton = qs("#printDashboard");
    const exportButton = qs("#exportCsv");
    const customApply = qs("#applyRange");
    if (printButton) printButton.addEventListener("click", () => window.print());
    if (exportButton) exportButton.addEventListener("click", (event) => { event.preventDefault(); exportData(); });
    if (customApply) {
      customApply.addEventListener("click", () => {
        const startDate = qs("#customStart")?.value || "";
        const endDate = qs("#customEnd")?.value || "";
        updateDateRange(30, startDate, endDate);
      });
    }
    if (state.snapshot) {
      renderCards(state.snapshot);
      renderCharts(state.snapshot);
    } else {
      await updateDateRange(state.days);
    }
  });
})();
