// The green bar on every page (v0.2.0): the phone's Menu, the Learn and name menus, Sign In or your name, and the links
// that still open the Streamlit app (Maps, Research, How It Works) until migration step 2 moves them here.
// The menus work as the Grazing Planner's (its session.js).
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const menus = () => [...document.querySelectorAll("details.head-menu")];
  const params = new URLSearchParams(location.search);
  const crop = params.get("crop") === "soybeans" ? "soybeans" : "corn";

  // Who's signed in: one request, shared with app.js (window.ypStatus).
  window.ypStatus = fetch("/auth/status", { credentials: "same-origin", cache: "no-store" })
    .then((r) => (r.ok ? r.json() : { sign_in: false, user: null }))
    .catch(() => ({ sign_in: false, user: null }));

  function streamlitLinks(base, state) {
    const q = new URLSearchParams();
    if (state && state !== "ne") q.set("state", state);
    if (crop !== "corn") q.set("crop", crop);
    const tail = q.toString() ? `?${q}` : "";
    for (const a of document.querySelectorAll("[data-streamlit]")) a.href = `${base}/${a.dataset.streamlit}${tail}`;
  }
  window.ypStreamlitLinks = streamlitLinks;

  function show(status) {
    const user = status.user;
    const on = Boolean(status.sign_in);
    const county = params.get("county");
    const signIn = `/auth/sign-in${county ? `?county=${encodeURIComponent(county)}` : ""}`;
    for (const id of ["signin-link", "signin-bar"]) {
      const a = $(id);
      if (!a) continue;
      a.href = signIn;
      a.classList.toggle("hidden", !on || Boolean(user));
    }
    $("me-menu")?.classList.toggle("hidden", !user);
    if (user) $("me-name").textContent = user.name || "Account";
  }

  let flat = false;
  function setMenu(open) {
    const btn = $("menu-btn");
    if (!btn) return;
    flat = open;
    btn.closest("header").classList.toggle("menu-open", open);
    btn.setAttribute("aria-expanded", String(open));
    for (const menu of menus()) menu.open = open;
  }

  document.addEventListener("DOMContentLoaded", () => {
    window.ypStatus.then((s) => {
      show(s);
      streamlitLinks((s.streamlit_url || "").replace(/\/$/, ""), params.get("state"));
    });
    const btn = $("menu-btn");
    btn?.addEventListener("click", (e) => { e.stopPropagation(); setMenu(!flat); });
    $("head-nav")?.addEventListener("click", (e) => {
      if (flat && e.target.closest("a, button") && !e.target.closest("summary")) setMenu(false);
    });
    const phone = typeof matchMedia === "function" ? matchMedia("(max-width: 640px)") : null;
    phone?.addEventListener?.("change", () => { if (!phone.matches && flat) setMenu(false); });
    for (const menu of menus()) {
      menu.addEventListener("toggle", () => {
        if (menu.open && !flat) for (const other of menus()) if (other !== menu) other.open = false;
      });
      menu.querySelector(".head-menu-panel")?.addEventListener("click", (e) => {
        if (e.target.closest("a, button") && !flat) menu.open = false;
      });
    }
    document.addEventListener("click", (e) => {
      if (flat) { if (btn && !btn.closest("header").contains(e.target)) setMenu(false); return; }
      for (const menu of menus()) if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (flat) { setMenu(false); btn?.focus(); return; }
      for (const menu of menus()) if (menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
    $("signout")?.addEventListener("click", async () => {
      show({ sign_in: true, user: null });
      try { await fetch("/auth/sign-out", { method: "POST", credentials: "same-origin" }); } catch { /* signed out here anyway */ }
      location.href = "./";
    });
  });
})();
