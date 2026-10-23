/* Farm app suite: the "Farm Apps" menu in each app's header, and the link back to the company
   site, and a link to the suite account. Suite version 7: the menu in the company site's style, apps in
   its two groups (For Ranches, For Farms).
   THE SAME FILE lives in Herd Planner and Farm Equipment Planner; the master copy
   is herd-planner/brand/suite.js (a test in each app fails if its copy drifts).

   Markup: <details class="suite-apps" data-suite-apps="<this app's id>" data-suite-base="<folder>">
   - If the <details> is empty, the menu is built from <folder>/suite-apps.json
     (Herd Planner does this; its pages are plain HTML).
   - If it is already filled in (the Equipment Planner's Django template does
     that on the server), this script only adds the closing behavior.
   The menu is a <details> element, so it opens and closes even without JavaScript.

   The way back to the company site (top left of every header, before the app's name):
     <a class="suite-company" data-suite-company href="<company url>">Company name</a>
   The page writes the link itself so it works without JavaScript; this script keeps its name and
   address in step with "company" in suite-apps.json, so renaming the company is a one-file change.
   The menu also opens with a link to the company site (not on the company site itself) and, on the
   right, "My Farm" (was "Your Account" until 2026-10-11): the suite's home page for people signed in, "account" in suite-apps.json (not on that page itself).

   Suite version 9 (2026-10-12): Ask a Question, the support assistant (claude/support-assistant-plan.md). Any
   element with data-suite-ask="<where it is: site or the app's id>" opens the panel. Every such element starts with
   class suite-ask-hidden and is shown only once My Farm says the assistant is on (GET /ask/status), so a page
   never offers a button that only says it's off. Where to ask: data-suite-ask-url on the element (My Farm itself
   uses "/ask"), else My Farm's address from "account" in suite-apps.json. Every word from the server is put in
   with textContent, never as HTML.

   Suite version 11 (2026-10-15): an eye in every password box that shows and hides the password (see addEye). */
(function () {
  "use strict";

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
    if (text) node.textContent = text;
    return node;
  }

  // One app's row: its logo, name and one line, and where you stand (You're here, Open, Coming Soon).
  // Suite version 10: an app still being built ("soon" in its group) gets a greyed row that opens nothing.
  function appRow(app, here, base) {
    const isHere = app.id === here;
    const row = app.url && !isHere ? el("a", { class: "suite-app", href: app.url }) : el("div", { class: "suite-app" });
    if (isHere) row.classList.add("here");
    if (!app.url && !isHere) row.classList.add("soon");
    row.appendChild(el("img", { src: `${base}/suite-logos/${app.id}.svg`, alt: "", width: "40", height: "40" }));
    const words = el("span", { class: "suite-app-words" });
    words.appendChild(el("strong", {}, app.name));
    words.appendChild(el("span", {}, app.what));
    row.appendChild(words);
    row.appendChild(el("span", { class: "suite-app-status" }, isHere ? "You're here" : app.url ? "Open" : "Coming Soon"));
    return row;
  }

  // Suite version 7: the apps in the company site's groups ("groups" in suite-apps.json: For Ranches, For Farms).
  // A list without groups (an older copy) still works: every app in one group called Our Farm Apps.
  function groupsOf(list) {
    if (Array.isArray(list.groups) && list.groups.length) return list.groups;
    return [{ title: "Our Farm Apps", lead: "", apps: list.apps.map((a) => a.id) }];
  }

  function build(menu, list) {
    const here = menu.dataset.suiteApps;
    const base = menu.dataset.suiteBase || ".";
    menu.appendChild(el("summary", { "aria-label": "Our Farm Apps" }, "Farm Apps"));
    const panel = el("div", { class: "suite-apps-panel" });
    const top = el("div", { class: "suite-apps-top" });
    if (list.company && here !== "company-site") {
      top.appendChild(el("a", { class: "suite-apps-home", href: list.company.url }, `${list.company.name} home`));
    }
    if (top.children.length) panel.appendChild(top);
    const byId = Object.fromEntries(list.apps.map((a) => [a.id, a]));
    const ops = el("div", { class: "suite-ops" });
    for (const group of groupsOf(list)) {
      const op = el("div", { class: "suite-op" });
      const head = el("div", { class: "suite-op-head" });
      head.appendChild(el("p", { class: "suite-op-title" }, group.title));
      if (group.lead) head.appendChild(el("p", { class: "suite-op-lead" }, group.lead));
      op.appendChild(head);
      for (const id of group.apps) if (byId[id]) op.appendChild(appRow(byId[id], here, base));
      for (const soon of group.soon || []) op.appendChild(appRow({ ...soon, url: null }, here, base));
      ops.appendChild(op);
    }
    panel.appendChild(ops);
    // Suite version 10 (Scott, 2026-10-14, of the company site's menu: "I like that it also has the My Farm link on
    // the bottom"): My Farm on a line of its own at the bottom, as there. Not in My Farm itself.
    if (list.account && here !== "farm-account") {
      const foot = el("p", { class: "suite-apps-foot" });
      foot.appendChild(el("span", {}, "Your apps in one place."));
      foot.appendChild(el("a", { class: "suite-apps-account", href: list.account.url }, `${list.account.name} \u2192`));
      panel.appendChild(foot);
    }
    menu.appendChild(panel);
  }

  function closeOnOutsideClickOrEscape(menu) {
    document.addEventListener("click", (event) => { if (menu.open && !menu.contains(event.target)) menu.open = false; });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
  }

  function updateCompanyLinks(list) {
    if (!list.company) return;
    for (const link of document.querySelectorAll("a[data-suite-company]")) {
      link.href = list.company.url;
      link.textContent = list.company.name;
    }
  }

  const menus = document.querySelectorAll("details.suite-apps");
  if (!menus.length && document.querySelector("a[data-suite-company]")) {
    const base = document.querySelector("a[data-suite-company]").dataset.suiteBase || ".";
    fetch(`${base}/suite-apps.json`).then((r) => (r.ok ? r.json() : null)).then((list) => list && updateCompanyLinks(list)).catch(() => {});
  }

  // --- Ask a Question (suite version 9) -----------------------------------------------------------------
  const ASK_WORDS = {
    title: "Ask a Question",
    lead: "Answers from our own pages: the app pages, How We Test and Help",
    hello: "Hi! I answer questions about our farm apps from our own pages, and I'll show you where each answer " +
      "comes from. I can't see anyone's herd or farm records.",
    note: "Estimates, not advice. Don't type personal details. Questions are kept without your name for 90 days " +
      "to improve our pages.",
    trouble: "I couldn't reach the assistant just now. Check your connection and try again.",
  };

  function setUpAsk(askers) {
    const first = askers[0];
    const where = (url) => url.replace(/\/$/, "");
    const known = first.dataset.suiteAskUrl;
    const found = known ? Promise.resolve(where(known)) : fetch(`${first.dataset.suiteBase || document.querySelector("[data-suite-base]")?.dataset.suiteBase || "."}/suite-apps.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((list) => `${new URL(list.account.url).origin}/ask`);
    found.then((url) => fetch(`${url}/status`).then((r) => (r.ok ? r.json() : { on: false })).then((s) => {
      if (!s.on) return;
      for (const a of askers) {
        a.classList.remove("suite-ask-hidden");
        a.addEventListener("click", (event) => { event.preventDefault(); openAsk(url, a); });
      }
    })).catch(() => {});                                  // no list, offline, My Farm asleep: no button, nothing broken
  }

  let ask = null;                                          // the one panel on the page, made on first open

  function bubble(cls, text) {
    const b = el("div", { class: `suite-ask-msg ${cls}` });
    if (text) b.appendChild(el("p", {}, text));
    ask.body.appendChild(b);
    ask.body.scrollTop = ask.body.scrollHeight;
    return b;
  }

  function closeAsk() {
    if (!ask || ask.panel.hidden) return;
    ask.panel.hidden = true;
    if (ask.opener) ask.opener.focus();
  }

  function openAsk(url, opener) {
    if (!ask) makeAsk(url);
    ask.opener = opener;
    ask.from = opener.dataset.suiteAsk || "site";
    ask.panel.hidden = false;
    ask.input.focus();
  }

  function makeAsk(url) {
    const panel = el("div", { class: "suite-ask", role: "dialog", "aria-labelledby": "suite-ask-title" });
    const head = el("div", { class: "suite-ask-head" });
    const words = el("div");
    words.appendChild(el("strong", { id: "suite-ask-title" }, ASK_WORDS.title));
    words.appendChild(el("small", {}, ASK_WORDS.lead));
    head.appendChild(words);
    const close = el("button", { type: "button", class: "suite-ask-close", "aria-label": "Close" }, "\u00d7");
    head.appendChild(close);
    const body = el("div", { class: "suite-ask-body", "aria-live": "polite" });
    const form = el("form", { class: "suite-ask-foot" });
    const row = el("div", { class: "suite-ask-row" });
    const input = el("input", { type: "text", name: "question", maxlength: "500", autocomplete: "off",
      placeholder: "Ask about an app, a number or a page", "aria-label": "Your question" });
    const send = el("button", { type: "submit", class: "suite-ask-send" }, "Ask");
    row.appendChild(input);
    row.appendChild(send);
    form.appendChild(row);
    form.appendChild(el("p", { class: "suite-ask-note" }, ASK_WORDS.note));
    panel.appendChild(head);
    panel.appendChild(body);
    panel.appendChild(form);
    panel.hidden = true;
    document.body.appendChild(panel);
    ask = { url, panel, body, input, send, conversation: null, busy: false };
    bubble("bot", ASK_WORDS.hello);

    close.addEventListener("click", closeAsk);
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeAsk(); });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const question = input.value.trim();
      if (!question || ask.busy) return;
      input.value = "";
      askOne(question);
    });
  }

  function askOne(question) {
    ask.busy = true;
    ask.send.disabled = true;
    bubble("me", question);
    const waiting = bubble("bot waiting", "Looking through our pages\u2026");
    fetch(ask.url, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, conversation: ask.conversation, asked_from: ask.from }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((reply) => { waiting.remove(); showReply(reply); })
      .catch(() => { waiting.remove(); bubble("bot", ASK_WORDS.trouble); })
      .finally(() => { ask.busy = false; ask.send.disabled = false; ask.input.focus(); });
  }

  function showReply(reply) {
    if (reply.conversation) ask.conversation = reply.conversation;
    const b = bubble("bot", reply.answer);
    if (reply.sources && reply.sources.length) {
      const from = el("p", { class: "suite-ask-src" }, "From: ");
      reply.sources.forEach((s, i) => {
        if (i) from.appendChild(document.createTextNode(", "));
        from.appendChild(el("a", { href: s.url }, s.title));
      });
      b.appendChild(from);
    }
    const buttons = el("div", { class: "suite-ask-actions" });
    if (reply.offer_handoff && ask.conversation && reply.limit !== "off") {
      const yes = el("button", { type: "button", class: "suite-ask-yes" }, "Send to Scott");
      const no = el("button", { type: "button", class: "suite-ask-no" }, "No Thanks");
      yes.addEventListener("click", () => { buttons.remove(); handoffForm(b); });
      no.addEventListener("click", () => buttons.remove());
      buttons.appendChild(yes);
      buttons.appendChild(no);
    }
    if (reply.limit === "conversation") {
      const again = el("button", { type: "button", class: "suite-ask-no" }, "Start a New Chat");
      again.addEventListener("click", () => {
        ask.conversation = null;
        ask.body.textContent = "";
        bubble("bot", ASK_WORDS.hello);
        ask.input.focus();
      });
      buttons.appendChild(again);
    }
    if (buttons.children.length) b.appendChild(buttons);
    ask.body.scrollTop = ask.body.scrollHeight;
  }

  function handoffForm(b) {
    const form = el("form", { class: "suite-ask-handoff" });
    const label = el("label", {}, "Your email, if you'd like a reply (optional)");
    const email = el("input", { type: "email", maxlength: "254", autocomplete: "email" });
    label.appendChild(email);
    const go = el("button", { type: "submit", class: "suite-ask-yes" }, "Send");
    form.appendChild(label);
    form.appendChild(go);
    b.appendChild(form);
    email.focus();
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      go.disabled = true;
      fetch(`${ask.url}/handoff`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ conversation: ask.conversation, email: email.value.trim() || null }),
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((done) => { form.remove(); b.appendChild(el("p", { class: "suite-ask-done" }, done.message)); })
        .catch(() => { go.disabled = false; b.appendChild(el("p", { class: "suite-ask-done" }, ASK_WORDS.trouble)); });
    });
  }

  // Suite version 11 (Scott, 2026-10-15: "We need an eyeball" in the password box): every password box in every app
  // gets an eye at its right end that shows what was typed, and hides it again. My Farm and the Grazing Planner each
  // had their own copy of this (same look); it moved here so Herd Planner and the Equipment Planner have it too. The box is wrapped in
  // <span class="suite-pw"> so the eye can sit inside it. Sending the form always hides it first, so a browser never
  // saves or shows the password as plain text. Boxes drawn later (a dialog, a page drawn by script) get one too.
  const SVG = "http://www.w3.org/2000/svg";
  function eyeIcon(open) {                         // the drawing My Farm and the Grazing Planner had used since 2026-09
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const paths = ["M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"];
    if (!open) paths.push("M4 4l16 16");               // crossed out: the password is showing, click to hide it
    for (const d of paths) {
      const path = document.createElementNS(SVG, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    }
    return svg;
  }
  function addEye(input) {
    if (input.dataset.suiteEye !== undefined || !input.parentNode) return;
    input.dataset.suiteEye = "";
    const wrap = el("span", { class: "suite-pw" });
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const eye = el("button", { type: "button", class: "suite-eye", "aria-label": "Show password", title: "Show password", "aria-pressed": "false" });
    eye.appendChild(eyeIcon(true));
    wrap.appendChild(eye);
    function show(on) {
      input.type = on ? "text" : "password";
      eye.setAttribute("aria-pressed", String(on));
      eye.setAttribute("aria-label", on ? "Hide password" : "Show password");
      eye.title = on ? "Hide password" : "Show password";
      eye.replaceChildren(eyeIcon(!on));
    }
    eye.addEventListener("click", () => { show(input.type === "password"); input.focus(); });
    if (input.form) input.form.addEventListener("submit", () => show(false), true);
  }
  function addEyes(root) {
    if (root.matches && root.matches('input[type="password"]')) addEye(root);
    if (root.querySelectorAll) for (const input of root.querySelectorAll('input[type="password"]')) addEye(input);
  }
  addEyes(document);
  if (typeof MutationObserver === "function") {
    new MutationObserver((changes) => {
      for (const change of changes) for (const node of change.addedNodes) if (node.nodeType === 1) addEyes(node);
    }).observe(document.body || document.documentElement, { childList: true, subtree: true });
  }

  const askers = document.querySelectorAll("[data-suite-ask]");
  if (askers.length) setUpAsk(askers);

  for (const menu of document.querySelectorAll("details.suite-apps")) {
    closeOnOutsideClickOrEscape(menu);
    if (menu.children.length) continue;               // filled in on the server
    const base = menu.dataset.suiteBase || ".";
    fetch(`${base}/suite-apps.json`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((list) => { build(menu, list); updateCompanyLinks(list); })
      .catch(() => menu.remove());                     // no list (offline, first visit): no menu rather than a broken one
  }
})();
