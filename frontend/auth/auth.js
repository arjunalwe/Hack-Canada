/**
 * auth.js — Native Auth0 PKCE implementation for Co-Pilot
 *
 * No external SDK needed. Uses the Auth0 Authentication API directly
 * with the PKCE flow (RFC 7636) — safe for SPAs without a client secret.
 *
 * Pages set window.AUTH0_CONFIG = { domain, clientId, audience, redirectUri }
 * All public functions are on window.Auth0.
 */

(function () {
    "use strict";

    // ── Config ────────────────────────────────────────────
    const CFG = window.AUTH0_CONFIG || {};
    const DOMAIN = CFG.domain || "";
    const CLIENT_ID = CFG.clientId || "";
    const AUDIENCE = CFG.audience || "";
    const REDIRECT_URI = CFG.redirectUri || (location.origin + "/auth/callback.html");
    const API_BASE = CFG.apiBase || "http://localhost:8000";

    // ── Token cache (in-memory & session storage) ─────────
    let _accessToken = null;
    let _idToken = sessionStorage.getItem("a0_id_token") || null;
    let _user = null;

    // ── PKCE helpers ──────────────────────────────────────
    function _randomBytes(len) {
        const arr = new Uint8Array(len);
        crypto.getRandomValues(arr);
        return arr;
    }

    function _base64url(buf) {
        return btoa(String.fromCharCode(...new Uint8Array(buf)))
            .replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
    }

    async function _pkce() {
        const verifier = _base64url(_randomBytes(32));
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
        const challenge = _base64url(digest);
        return { verifier, challenge };
    }

    // ── Parse JWT payload (no signature check — server does that) ─
    function _parseJWT(token) {
        try {
            const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
            return JSON.parse(atob(b64));
        } catch { return {}; }
    }

    // ── Build the /authorize URL ───────────────────────────
    function _authorizeUrl(params) {
        const base = `https://${DOMAIN}/authorize`;
        const q = new URLSearchParams({
            response_type: "code",
            client_id: CLIENT_ID,
            redirect_uri: REDIRECT_URI,
            scope: "openid profile email",
            code_challenge_method: "S256",
            ...params,
        });
        if (AUDIENCE) q.set("audience", AUDIENCE);
        return `${base}?${q}`;
    }

    // ── Login with Universal Login ─────────────────────────
    async function loginWithRedirect(opts = {}) {
        const { verifier, challenge } = await _pkce();
        sessionStorage.setItem("a0_pkce_v", verifier);

        const params = {
            code_challenge: challenge,
            state: _base64url(_randomBytes(16)),
        };
        if (opts.connection) params.connection = opts.connection;
        if (opts.screenHint) params.screen_hint = opts.screenHint;
        if (opts.loginHint) params.login_hint = opts.loginHint;

        sessionStorage.setItem("a0_state", params.state);
        window.location.assign(_authorizeUrl(params));
    }

    // ── Handle the redirect callback ───────────────────────
    async function handleRedirectCallback() {
        const search = new URLSearchParams(location.search);
        const code = search.get("code");
        const state = search.get("state");
        const verifier = sessionStorage.getItem("a0_pkce_v");

        if (!code) throw new Error("No auth code in callback URL.");
        if (!verifier) throw new Error("PKCE verifier missing — did you start from login.html?");

        // Exchange code → tokens
        const resp = await fetch(`https://${DOMAIN}/oauth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                grant_type: "authorization_code",
                client_id: CLIENT_ID,
                code,
                redirect_uri: REDIRECT_URI,
                code_verifier: verifier,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error_description || err.error || "Token exchange failed");
        }

        const tokens = await resp.json();
        _accessToken = tokens.access_token || null;
        _idToken = tokens.id_token || null;
        if (_idToken) sessionStorage.setItem("a0_id_token", _idToken);
        _user = _idToken ? _parseJWT(_idToken) : null;

        // Clean up
        sessionStorage.removeItem("a0_pkce_v");
        sessionStorage.removeItem("a0_state");

        return { token: _accessToken, user: _user };
    }

    // ── Is authenticated? ──────────────────────────────────
    function isAuthenticated() {
        if (_accessToken) return true;
        // Check session cache set by callback page
        return !!sessionStorage.getItem("a0_user");
    }

    // ── Get user ───────────────────────────────────────────
    function getUser() {
        if (_user) return _user;
        const stored = sessionStorage.getItem("a0_user");
        return stored ? JSON.parse(stored) : null;
    }

    // ── Get token ──────────────────────────────────────────
    function getToken() { return _idToken; }

    // ── Logout ─────────────────────────────────────────────
    function logout() {
        _accessToken = null; _idToken = null; _user = null;
        sessionStorage.removeItem("a0_user");
        sessionStorage.removeItem("a0_id_token");
        sessionStorage.removeItem("a0_pkce_v");
        const url = new URL(`https://${DOMAIN}/v2/logout`);
        url.searchParams.set("client_id", CLIENT_ID);
        url.searchParams.set("returnTo", location.origin + "/auth/login.html");
        window.location.assign(url.toString());
    }

    // ── Passwordless magic-link ────────────────────────────
    async function sendMagicLink(email) {
        const resp = await fetch(`https://${DOMAIN}/passwordless/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                client_id: CLIENT_ID,
                connection: "email",
                email,
                send: "link",
                authParams: { scope: "openid profile email", redirect_uri: REDIRECT_URI },
            }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error_description || err.error || "Failed to send magic link");
        }
        return true;
    }

    // ── MFA enroll (via backend proxy) ────────────────────
    async function enrollMFA() {
        const token = getToken();
        if (!token) throw new Error("Not authenticated");
        const resp = await fetch(`${API_BASE}/api/auth/mfa/enroll`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!resp.ok) throw new Error("MFA enroll failed");
        return resp.json();
    }

    async function getMFAStatus() {
        const token = getToken();
        if (!token) return { enrolled: false };
        const resp = await fetch(`${API_BASE}/api/auth/mfa/status`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!resp.ok) return { enrolled: false };
        return resp.json();
    }

    // ── /api/auth/me ───────────────────────────────────────
    async function getMe() {
        const token = getToken();
        if (!token) return null;
        const resp = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        return resp.ok ? resp.json() : null;
    }

    // ── Toast ──────────────────────────────────────────────
    function showToast(message, type = "") {
        let el = document.getElementById("a0-toast");
        if (!el) {
            el = document.createElement("div");
            el.id = "a0-toast"; el.className = "a0-toast";
            document.body.appendChild(el);
        }
        el.textContent = message;
        el.className = `a0-toast a0-toast--show${type === "ok" ? " a0-toast--ok" : type === "err" ? " a0-toast--err" : ""}`;
        clearTimeout(el._tid);
        el._tid = setTimeout(() => { el.className = "a0-toast"; }, 3500);
    }

    // ── Public API ─────────────────────────────────────────
    window.Auth0 = {
        loginWithRedirect,
        loginWithGoogle: () => loginWithRedirect({ connection: "google-oauth2" }),
        loginWithGitHub: () => loginWithRedirect({ connection: "github" }),
        loginWithLinkedIn: () => loginWithRedirect({ connection: "linkedin" }),
        signUp: () => loginWithRedirect({ screenHint: "signup" }),
        handleRedirectCallback,
        getToken,
        getUser,
        getMe,
        isAuthenticated,
        logout,
        sendMagicLink,
        enrollMFA,
        getMFAStatus,
        showToast,
        // compat shim — init() is a no-op now (no SDK to load)
        init: () => Promise.resolve(),
    };
})();
