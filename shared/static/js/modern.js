document.addEventListener("DOMContentLoaded", () => {
    const userToggle = document.querySelector("[data-modern-user-toggle]");
    const userPanel = document.querySelector("[data-modern-user-panel]");
    const mobileToggle = document.querySelector("[data-modern-mobile-toggle]");
    const mobilePanel = document.querySelector("[data-modern-mobile-panel]");

    const setExpanded = (element, expanded) => {
        if (element) {
            element.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
    };

    const closeUserPanel = () => {
        if (!userPanel) return;
        userPanel.classList.remove("is-open");
        setExpanded(userToggle, false);
    };

    const closeMobilePanel = () => {
        if (!mobilePanel) return;
        mobilePanel.classList.remove("is-open");
        setExpanded(mobileToggle, false);
    };

    if (userToggle && userPanel) {
        userToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const open = userPanel.classList.toggle("is-open");
            setExpanded(userToggle, open);
        });
    }

    if (mobileToggle && mobilePanel) {
        mobileToggle.addEventListener("click", () => {
            const open = mobilePanel.classList.toggle("is-open");
            setExpanded(mobileToggle, open);
        });
    }

    document.addEventListener("click", (event) => {
        if (userPanel && userToggle && !userPanel.contains(event.target) && !userToggle.contains(event.target)) {
            closeUserPanel();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeUserPanel();
            closeMobilePanel();
        }
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.16 });

    document.querySelectorAll(".reveal-on-scroll").forEach((element) => observer.observe(element));
});
