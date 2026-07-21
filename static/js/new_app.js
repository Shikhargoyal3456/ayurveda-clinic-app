(() => {
    const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';

    window.KashNewApp = {
        async post(url, body = {}, multipart = false) {
            const options = {
                method: 'POST',
                headers: multipart ? { 'X-CSRF-Token': csrf() } : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
                credentials: 'include',
            };
            if (multipart) {
                options.body = body;
            } else {
                options.body = JSON.stringify(body);
            }
            const response = await fetch(url, options);
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload.error || payload.detail) {
                throw new Error(payload.error || payload.detail || 'Request failed.');
            }
            return payload;
        },

        renderChatMessage(host, text, kind = 'ai') {
            if (!host) return;
            const node = document.createElement('div');
            node.className = `message ${kind}`;
            node.textContent = text;
            host.appendChild(node);
            host.scrollTop = host.scrollHeight;
        },
    };

    document.addEventListener("DOMContentLoaded", () => {
        const mobileToggle = document.getElementById("mobileToggle");
        const navLinks = document.getElementById("navLinks");
        if (mobileToggle && navLinks) {
            mobileToggle.addEventListener("click", () => {
                const isOpen = navLinks.classList.toggle("open");
                mobileToggle.setAttribute("aria-expanded", String(isOpen));
            });
        }

        const userMenu = document.getElementById("userMenu") || document.getElementById("userMenuBtn");
        const userDropdown = document.getElementById("userDropdown");

        const closeDropdown = () => {
            if (!userMenu || !userDropdown) return;
            userDropdown.classList.remove("show");
            userMenu.setAttribute("aria-expanded", "false");
        };

        if (userMenu && userDropdown) {
            userMenu.addEventListener("click", (event) => {
                event.stopPropagation();
                const isOpen = userDropdown.classList.toggle("show");
                userMenu.setAttribute("aria-expanded", String(isOpen));
            });
        }

        document.addEventListener("click", (event) => {
            if (userMenu && userDropdown && !userMenu.contains(event.target) && !userDropdown.contains(event.target)) {
                closeDropdown();
            }
            if (mobileToggle && navLinks && !mobileToggle.contains(event.target) && !navLinks.contains(event.target)) {
                navLinks.classList.remove("open");
                mobileToggle.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeDropdown();
                if (mobileToggle && navLinks) {
                    navLinks.classList.remove("open");
                    mobileToggle.setAttribute("aria-expanded", "false");
                }
            }
        });

        window.addEventListener("blur", closeDropdown);
    });
})();
