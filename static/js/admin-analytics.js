(function () {
    let ordersChart;
    let revenueChart;
    let usersChart;
    let medicinesChart;
    let activitySocket;

    function bootstrapData() {
        const node = document.getElementById("admin-dashboard-bootstrap");
        if (!node) return {};
        try {
            return JSON.parse(node.textContent || "{}");
        } catch (error) {
            return {};
        }
    }

    function setActiveChartButton(type, range, button) {
        const buttons = document.querySelectorAll(`.chart-btn[data-chart-type="${type}"]`);
        buttons.forEach((item) => item.classList.toggle("active", item === button));
    }

    function chartLineConfig(label, labels, data, color) {
        return {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label,
                    data,
                    borderColor: color,
                    backgroundColor: `${color}22`,
                    tension: 0.35,
                    fill: true,
                    borderWidth: 3,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: "#edf2f7" } },
                    x: { grid: { display: false } },
                },
            },
        };
    }

    function initCharts() {
        const data = bootstrapData();
        if (window.Chart) {
            const ordersCtx = document.getElementById("ordersChart");
            const revenueCtx = document.getElementById("revenueChart");
            const usersCtx = document.getElementById("usersChart");
            const medicinesCtx = document.getElementById("medicinesChart");
            if (ordersCtx) {
                ordersChart = new Chart(ordersCtx, chartLineConfig("Orders", data.chartLabels || [], data.chartOrdersData || [], "#2BAE66"));
            }
            if (revenueCtx) {
                revenueChart = new Chart(revenueCtx, chartLineConfig("Revenue", data.chartLabels || [], data.chartRevenueData || [], "#0F4C5C"));
            }
            if (usersCtx) {
                usersChart = new Chart(usersCtx, {
                    type: "bar",
                    data: {
                        labels: data.chartLabels || [],
                        datasets: [{
                            label: "Users",
                            data: data.chartUsersData || [],
                            backgroundColor: "#14b8a6",
                            borderRadius: 10,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: "#edf2f7" } },
                            x: { grid: { display: false } },
                        },
                    },
                });
            }
            if (medicinesCtx) {
                medicinesChart = new Chart(medicinesCtx, {
                    type: "doughnut",
                    data: {
                        labels: data.chartMedicinesLabels || [],
                        datasets: [{
                            data: data.chartMedicinesData || [],
                            backgroundColor: ["#0f766e", "#14b8a6", "#4f46e5", "#f59e0b", "#ef4444"],
                            borderWidth: 0,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: "bottom",
                                labels: { boxWidth: 12, usePointStyle: true },
                            },
                        },
                    },
                });
            }
        }
    }

    function wsProtocol() {
        return window.location.protocol === "https:" ? "wss" : "ws";
    }

    function getIcon(type) {
        return { order: "🛒", user: "👤", prescription: "📄", payment: "💰", search: "🔎", consultation: "🎥", alert: "⚠️" }[type] || "📌";
    }

    function addActivityToFeed(activity) {
        const feed = document.getElementById("activityFeed");
        if (!feed) return;
        const anchor = document.createElement("a");
        anchor.href = activity.details_url || "/admin/activity-dashboard";
        anchor.className = `activity-item activity-item--${activity.tone || "neutral"}`;
        anchor.innerHTML = `
            <span class="activity-time">${activity.time_ago || "Just now"}</span>
            <span class="activity-content"><span class="activity-icon">${activity.icon || getIcon(activity.type)}</span><span>${activity.message || "New activity"}</span></span>
        `;
        feed.insertBefore(anchor, feed.firstChild);
        while (feed.children.length > 50) {
            feed.removeChild(feed.lastChild);
        }
    }

    function initWebSocket() {
        try {
            activitySocket = new WebSocket(`${wsProtocol()}://${window.location.host}/ws/admin/activity`);
            activitySocket.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    addActivityToFeed(payload);
                } catch (error) {}
            };
            window.setInterval(() => {
                if (activitySocket && activitySocket.readyState === WebSocket.OPEN) {
                    activitySocket.send("ping");
                }
            }, 15000);
        } catch (error) {}
    }

    async function refreshTopStats() {
        try {
            const response = await fetch("/api/admin/stats");
            if (!response.ok) return;
            const data = await response.json();
            const totalUsers = document.getElementById("totalUsers");
            const ordersToday = document.getElementById("ordersToday");
            const revenueToday = document.getElementById("revenueToday");
            const activePrescriptions = document.getElementById("activePrescriptions");
            if (totalUsers) totalUsers.textContent = data.total_users ?? 0;
            if (ordersToday) ordersToday.textContent = data.orders_today ?? 0;
            if (revenueToday) revenueToday.textContent = `₹${data.revenue_today ?? 0}`;
            if (activePrescriptions) activePrescriptions.textContent = data.active_prescriptions ?? 0;
        } catch (error) {}
    }

    async function refreshPredictionsPanel() {
        try {
            const response = await fetch("/api/admin/predictions");
            if (!response.ok) return;
            const data = await response.json();
            const predictedOrders = document.getElementById("predictedOrders");
            const predictedRevenue = document.getElementById("predictedRevenue");
            if (predictedOrders) predictedOrders.textContent = data.predicted_orders ?? 0;
            if (predictedRevenue) predictedRevenue.textContent = `₹${data.predicted_revenue ?? 0}`;
        } catch (error) {}
    }

    window.refreshAllData = function () {
        window.location.reload();
    };

    window.exportFullReport = function () {
        window.location.href = "/api/admin/export-full-report";
    };

    window.scheduleReport = async function () {
        try {
            const response = await fetch("/api/admin/reports/schedule-weekly", { method: "POST" });
            const payload = await response.json();
            window.alert(payload.message || "Weekly report scheduled.");
        } catch (error) {
            window.alert("Unable to schedule the weekly report right now.");
        }
    };

    window.refreshPredictions = async function () {
        await refreshPredictionsPanel();
    };

    window.viewAllActivity = function () {
        window.location.href = "/admin/activity-dashboard";
    };

    window.filterOrders = function () {
        const status = document.getElementById("orderStatusFilter")?.value || "all";
        const date = document.getElementById("orderDateFilter")?.value || "";
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        if (date) params.set("date", date);
        window.location.href = `/admin?${params.toString()}`;
    };

    window.investigateAnomaly = function () {
        window.location.href = "/admin/order-health";
    };

    window.viewOrder = function (orderId) {
        window.location.href = `/orders/tracking/${orderId}`;
    };

    window.updateChart = async function (type, range, button) {
        try {
            const response = await fetch(`/api/admin/chart-data?type=${encodeURIComponent(type)}&range=${encodeURIComponent(range)}`);
            if (!response.ok) return;
            const payload = await response.json();
            setActiveChartButton(type, range, button);
            const chartMap = { orders: ordersChart, revenue: revenueChart, users: usersChart, medicines: medicinesChart };
            const chart = chartMap[type];
            if (!chart) return;
            chart.data.labels = payload.labels || [];
            chart.data.datasets[0].data = payload.values || [];
            chart.update();
        } catch (error) {}
    };

    document.addEventListener("DOMContentLoaded", () => {
        initCharts();
        initWebSocket();
        window.setInterval(() => {
            refreshTopStats();
            refreshPredictionsPanel();
        }, 30000);
    });
}());
