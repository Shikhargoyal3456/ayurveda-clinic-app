class KashWS {
    constructor(path, options = {}) {
        this.path = path;
        this.options = options;
        this.ws = null;
        this.retryCount = 0;
        this.maxRetries = options.maxRetries ?? 8;
        this.baseDelay = options.baseDelay ?? 1000;
        this.manualClose = false;
        this._pingInterval = null;
    }

    get url() {
        const protocol = location.protocol === "https:" ? "wss" : "ws";
        return `${protocol}://${location.host}${this.path}`;
    }

    connect() {
        this._setStatus("connecting");
        this.manualClose = false;
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            this.retryCount = 0;
            this._setStatus("connected");
            this._startPing();
            this.options.onOpen?.();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === "pong") return;
                this.options.onMessage?.(data);
            } catch (error) {
                this.options.onMessage?.(event.data);
            }
        };

        this.ws.onclose = (event) => {
            this._stopPing();
            this.options.onClose?.(event);
            if (!this.manualClose && this.retryCount < this.maxRetries) {
                this._setStatus("reconnecting");
                const delay = Math.min(this.baseDelay * Math.pow(2, this.retryCount), 30000);
                const jitter = Math.random() * 500;
                this.retryCount += 1;
                window.setTimeout(() => this.connect(), delay + jitter);
            } else if (this.retryCount >= this.maxRetries) {
                this._setStatus("failed");
            } else {
                this._setStatus("disconnected");
            }
        };

        this.ws.onerror = () => {
            this._setStatus("error");
        };
    }

    send(data) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(typeof data === "string" ? data : JSON.stringify(data));
        }
    }

    disconnect() {
        this.manualClose = true;
        this._stopPing();
        this.ws?.close();
    }

    _startPing() {
        this._stopPing();
        this._pingInterval = window.setInterval(() => {
            this.send({ type: "ping" });
        }, 25000);
    }

    _stopPing() {
        if (this._pingInterval) {
            window.clearInterval(this._pingInterval);
            this._pingInterval = null;
        }
    }

    _setStatus(status) {
        const el = this.options.statusEl;
        if (!el) return;
        const labels = {
            connecting: ["connecting", "Connecting…", "var(--color-warning)"],
            connected: ["connected", "Live", "var(--color-success)"],
            reconnecting: ["reconnecting", "Reconnecting…", "var(--color-warning)"],
            disconnected: ["disconnected", "Offline", "var(--color-text-muted)"],
            failed: ["failed", "Connection failed — refresh the page", "var(--color-danger)"],
            error: ["error", "Connection error", "var(--color-danger)"],
        };
        const [state, label, color] = labels[status] ?? labels.disconnected;
        el.dataset.wsState = state;
        const labelEl = el.querySelector(".ws-status__label");
        const dotEl = el.querySelector(".ws-status__dot");
        if (labelEl) {
            labelEl.textContent = label;
        }
        if (dotEl) {
            dotEl.style.setProperty("--dot-color", color);
        }
    }
}

window.KashWS = KashWS;
