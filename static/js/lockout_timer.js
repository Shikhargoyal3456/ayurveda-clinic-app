// Lockout timer for Kash AI
class LockoutTimer {
    constructor(container, remainingSeconds, onTick = null) {
        this.container = container;
        this.remainingSeconds = remainingSeconds;
        this.onTick = onTick;
        this.interval = null;
    }

    start() {
        this.render();
        this.interval = setInterval(() => {
            this.remainingSeconds--;
            this.render();
            if (this.remainingSeconds <= 0) {
                clearInterval(this.interval);
                this.container.innerHTML = `<div class="lockout-resolved">✅ Lockout cleared. You can sign in again now.</div>`;
                if (typeof this.onTick === "function") {
                    this.onTick(0);
                }
            } else if (typeof this.onTick === "function") {
                this.onTick(this.remainingSeconds);
            }
        }, 1000);
    }

    formatTime() {
        const minutes = Math.floor(this.remainingSeconds / 60);
        const seconds = this.remainingSeconds % 60;
        return `${minutes}:${seconds.toString().padStart(2, "0")}`;
    }

    render() {
        const timeStr = this.formatTime();
        this.container.innerHTML = `
            <div class="lockout-warning">
                ⚠️ Your account is temporarily locked after several failed attempts.
                <br>
                <span class="lockout-timer">⏱️ ${timeStr}</span> remaining
            </div>
        `;
    }
}

window.LockoutTimer = LockoutTimer;
