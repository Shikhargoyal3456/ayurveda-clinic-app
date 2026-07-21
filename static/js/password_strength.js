// Password strength checker for Kash AI
class PasswordStrength {
    constructor() {
        this.rules = [
            { id: "length", label: "At least 8 characters", regex: /.{8,}/ },
            { id: "uppercase", label: "One uppercase letter", regex: /[A-Z]/ },
            { id: "lowercase", label: "One lowercase letter", regex: /[a-z]/ },
            { id: "number", label: "One number", regex: /\d/ },
            { id: "special", label: "One special character", regex: /[!@#$%^&*(),.?":{}|<>]/ },
        ];
        this.strengthColors = ["#ff4444", "#ff8800", "#ffcc00", "#44bb44", "#00aa00"];
        this.strengthLabels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"];
    }

    check(password) {
        const results = this.rules.map((rule) => ({ ...rule, passed: rule.regex.test(password) }));
        const score = results.filter((rule) => rule.passed).length;
        const strength = Math.min(score, 4);
        return {
            score,
            strength,
            strengthLabel: this.strengthLabels[strength],
            strengthColor: this.strengthColors[strength],
            rules: results,
            isStrong: score >= 4,
        };
    }

    render(password, container) {
        if (!container) return;
        const result = this.check(password);
        let html = `
            <div class="password-strength">
                <div class="strength-bar">
                    <div class="strength-fill" style="width: ${(result.score / 5) * 100}%; background: ${result.strengthColor};"></div>
                </div>
                <div class="strength-label" style="color: ${result.strengthColor}">
                    ${result.strengthLabel} (${result.score}/5 checks passed)
                </div>
                <ul class="rules-list">
        `;
        result.rules.forEach((rule) => {
            const icon = rule.passed ? "✅" : "❌";
            const cls = rule.passed ? "passed" : "failed";
            html += `<li class="${cls}">${icon} ${rule.label}</li>`;
        });
        html += `</ul></div>`;
        container.innerHTML = html;
    }
}

window.PasswordStrength = PasswordStrength;
