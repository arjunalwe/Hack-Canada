/**
 * auth-guard.js — Optional script for the main app
 *
 * Drop this into index.html (or any page you want to protect):
 *
 *   <script src="auth/auth-guard.js"></script>
 *
 * If the user has no valid session they will be sent to the sign-in
 * page.  If they ARE signed in, the user object is available via:
 *
 *   window.__a0User  (parsed from sessionStorage or Auth0 SDK)
 *
 * This file is completely standalone and does NOT modify any existing
 * variables, CSS classes, or global functions.
 */

(function () {
    "use strict";

    // 1. Quick check: did a previous session store a user flag?
    const stored = sessionStorage.getItem("a0_user");
    if (stored) {
        try {
            window.__a0User = JSON.parse(stored);
            // Dispatch a custom event so the main app can react
            document.dispatchEvent(new CustomEvent("a0:user-ready", { detail: window.__a0User }));
            return; // fast path — SDK not needed
        } catch (_) {
            sessionStorage.removeItem("a0_user");
        }
    }

    // 2. No stored session — load Auth0 SDK and check silently
    //    CONFIG is read from window.AUTH0_CONFIG if the parent page sets it,
    //    otherwise we fall through to the redirect.
    const cfg = window.AUTH0_CONFIG;
    if (!cfg || !cfg.domain || cfg.domain.startsWith("YOUR_")) {
        // Auth0 not configured yet — don't redirect (dev mode)
        console.info("[auth-guard] Auth0 not configured — guard disabled.");
        return;
    }

    // Load auth.js dynamically (resolves relative to current page)
    const script = document.createElement("script");
    // Determine path: if current page is in /auth/ subdir the path is
    // auth.js, otherwise it is auth/auth.js.
    const inAuthDir = window.location.pathname.includes("/auth/");
    script.src = inAuthDir ? "auth.js" : "auth/auth.js";
    script.onload = async () => {
        try {
            await Auth0.init();
            const authed = await Auth0.isAuthenticated();
            if (!authed) {
                // Redirect to login, storing the intended destination
                const returnTo = encodeURIComponent(window.location.href);
                const loginPath = inAuthDir ? "./login.html" : "./auth/login.html";
                window.location.replace(loginPath + "?return_to=" + returnTo);
                return;
            }
            const user = await Auth0.getUser();
            window.__a0User = user;
            if (user) {
                sessionStorage.setItem("a0_user", JSON.stringify({
                    sub: user.sub,
                    name: user.name,
                    email: user.email,
                    picture: user.picture,
                }));
            }
            document.dispatchEvent(new CustomEvent("a0:user-ready", { detail: user }));
        } catch (err) {
            console.warn("[auth-guard] Auth check failed:", err.message);
        }
    };
    document.head.appendChild(script);
})();
