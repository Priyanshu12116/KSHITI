/* Kshiti interface. No framework, no build step. */
(() => {
  "use strict";

  const I18N = window.KSHITI_I18N;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const params = new URLSearchParams(location.search);

  const state = {
    lang: localStorage.getItem("kshiti.lang") || "en",
    meta: null,
    question: "",
    qLang: "en",
    route: null,
    calc: null,
    result: null,
    streamText: "",
    busy: false,
    controller: null,
  };

  const t = (key) => I18N[state.lang][key] ?? I18N.en[key] ?? key;
  const tq = (key) => I18N[state.qLang][key] ?? I18N.en[key] ?? key;   // follows the question's language
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const squash = (s) => String(s ?? "").replace(/\s+/g, " ").trim().toLowerCase();
  const isHindi = (s) => /[ऀ-ॿ]/.test(s || "");
  const icon = (id, cls = "ic") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const secs = (v) => (v == null ? "" : `${Number(v).toFixed(v < 1 ? 2 : 1)} s`);

  const EXAMPLES = [
    { tag: "calc", q: "My plot is 200 sq m on a 9 m road. How much gap do I leave at the front, how many floors can I build, and what fee do I pay?" },
    { tag: "calc", q: "My house faces a 10 m wide street and will be 9 m tall. How much open space do I leave at the front?" },
    { tag: "hi", q: "मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली छोड़नी होगी?" },
    { tag: "rule", q: "My development permission was granted in 2023. How long does it stay valid, and how many times can I renew it?" },
    { tag: "rule", q: "Do I need separate development permission for a 300 sq m plot that matches the Development Plan?" },
    { tag: "rule", q: "How far must my balcony stay from a low-voltage overhead electric line, vertically and horizontally?" },
    { tag: "nf", q: "How do I pay my property tax online?" },
  ];

  /* ================================================================ preferences */
  function applyLang(lang) {
    state.lang = lang;
    localStorage.setItem("kshiti.lang", lang);
    document.documentElement.lang = lang;
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    $$(".seg--lang .seg__b").forEach((b) => b.classList.toggle("is-on", b.dataset.lang === lang));
    renderExamples();
    if (state.meta) renderMeta();
    if (state.result) renderFinal(state.result, { animate: false });
    else if (state.calc) renderCalc(state.calc);
  }

  function applySize(size) {
    document.documentElement.classList.remove("size-sm", "size-lg");
    if (size !== "md") document.documentElement.classList.add(`size-${size}`);
    $$("[data-size]").forEach((b) => b.classList.toggle("is-on", b.dataset.size === size));
    localStorage.setItem("kshiti.size", size);
  }

  function applyContrast(on) {
    document.documentElement.classList.toggle("hc", on);
    $("#contrast-btn").setAttribute("aria-pressed", String(on));
    localStorage.setItem("kshiti.hc", on ? "1" : "0");
  }

  /* ================================================================ brand + splash */
  async function loadWordmark() {
    const res = await fetch("/static/brand/wordmark-hi.svg");
    return res.ok ? res.text() : "";
  }

  async function splash() {
    const el = $("#splash");
    const seen = sessionStorage.getItem("kshiti.splash") === "1";
    const svg = await loadWordmark();
    $("#brand-mark").innerHTML = svg;
    const force = params.get("splash") === "1";
    if ((seen && !force) || params.get("nosplash") === "1" || !svg) {
      el.remove();
      return;
    }
    document.body.classList.add("is-splash");
    const mark = $("#splash-mark");
    mark.innerHTML = svg;
    $$(".g", mark).forEach((p) => {
      const len = Math.ceil(p.getTotalLength());
      p.style.strokeDasharray = `${len}`;
      p.style.strokeDashoffset = `${len}`;
    });
    void mark.offsetWidth;                 // commit start state before animating
    el.classList.add(reduceMotion ? "is-calm" : "is-play");

    // Hold long enough to be seen; click or any key skips.
    let skip;
    const skipped = new Promise((r) => { skip = r; });
    const onSkip = () => skip();
    setTimeout(() => { el.addEventListener("click", onSkip); document.addEventListener("keydown", onSkip, { once: true }); }, 600);
    await Promise.race([wait(reduceMotion ? 3200 : 5300), skipped]);
    el.removeEventListener("click", onSkip);
    document.removeEventListener("keydown", onSkip);

    // Fly the wordmark into the header (FLIP), then reveal the page.
    const target = $("#brand-mark").getBoundingClientRect();
    const from = mark.getBoundingClientRect();
    if (!reduceMotion && target.width) {
      $$(".g", mark).forEach((p) => { p.style.strokeWidth = "0"; p.style.fillOpacity = "1"; });
      const dx = target.left + target.width / 2 - (from.left + from.width / 2);
      const dy = target.top + target.height / 2 - (from.top + from.height / 2);
      const s = target.height / from.height;
      $$(".splash__swash, .splash__latin, .splash__tag, .splash__skip", el).forEach((n) => n.animate([{ opacity: getComputedStyle(n).opacity }, { opacity: 0 }], { duration: 380, fill: "forwards" }));
      await mark.animate(
        [{ transform: "none" }, { transform: `translate(${dx}px, ${dy}px) scale(${s})` }],
        { duration: 1000, easing: "cubic-bezier(.65,0,.35,1)", fill: "forwards" },
      ).finished;
    }
    document.body.classList.remove("is-splash");
    document.body.classList.add("is-entering");
    el.classList.add("is-leaving");
    sessionStorage.setItem("kshiti.splash", "1");
    setTimeout(() => { el.remove(); document.body.classList.remove("is-entering"); }, 900);
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ================================================================ meta (rail) */
  async function loadMeta() {
    try {
      const res = await fetch("/api/meta");
      state.meta = await res.json();
      renderMeta();
    } catch { /* rail stays with defaults */ }
  }

  function renderMeta() {
    const m = state.meta;
    $("#m-rules").textContent = m.rules_count;
    $("#m-blocks").textContent = m.blocks_count;
    $("#m-fp").textContent = `${m.fingerprint.slice(0, 16)}…`;
    $("#m-fp").title = m.fingerprint;
    const am = m.amendments || [];
    $("#amend-chip").hidden = !am.length;
    $("#m-amend").innerHTML = am.map((a) => `
      <div class="amend__item"><b>${icon("alert", "ic ic--sm")} ${esc(t("r_amend"))}: ${esc(t("rule"))} ${esc(a.sub_rule)} · ${esc(a.date.split("-").reverse().join("-"))}</b>
      ${esc(state.lang === "hi" ? a.summary_hi : a.summary_en)}</div>`).join("");
    const s = m.services;
    const chip = (name, on, model) => `<span class="chip ${on ? "chip--ok" : "chip--off"}" title="${esc(model)}">${icon(on ? "seal" : "info", "ic ic--sm")}${name} · ${esc(on ? t("svc_on") : t("svc_off"))}</span>`;
    const groqModel = (s.groq_model || "").split("/").pop();
    $("#m-svc").innerHTML = chip("Cerebras", s.cerebras, s.cerebras_model) + chip("Claude", s.claude, s.claude_model)
      + (s.groq ? chip(`Groq ${groqModel}`, s.groq, s.groq_model) : "");
    // Describe the engine that is actually answering.
    const groq = s.engine === "groq";
    $('[data-i18n="h1_d"]').textContent = s.cerebras ? t("h1_d") : s.router === "groq" ? t("h1_d_groq") : t("h1_d_local");
    $('[data-i18n="h3_d"]').textContent = groq ? t("h3_d_groq").replace("{m}", groqModel) : t("h3_d");
    renderAccuracy(m.accuracy);
  }

  function renderAccuracy(acc) {
    const box = $("#m-acc");
    if (!acc || !acc.summary) {
      box.innerHTML = `<p class="acc__empty">${esc(t("acc_empty"))}</p>`;
      return;
    }
    const s = acc.summary;
    if (acc.offline) {
      const off = [
        ["acc_off_calc", s.calc_figure_hit, s.calc_figure_total, "o"],
        ["acc_off_oos", s.out_of_scope_hit, s.out_of_scope_total, ""],
        ["acc_off_wrong", s.no_wrong_figure, s.questions, ""],
      ];
      box.innerHTML = `<div class="acc"><p class="acc__empty">${esc(t("acc_off_note"))}</p>${off.map(([k, a, b, o]) => `
        <div class="acc__row"><span class="acc__label">${esc(t(k))}</span><span class="acc__val">${a}/${b}</span>
        <span class="acc__bar ${o ? "acc__bar--o" : ""}"><i style="--w:${Math.round((a / b) * 100)}%"></i></span></div>`).join("")}
        <p class="acc__foot">${esc(t("acc_foot"))} · ${esc(acc.run_date || "")}</p></div>`;
      requestAnimationFrame(() => $$(".acc__bar i", box).forEach((i) => { i.style.width = i.style.getPropertyValue("--w"); }));
      return;
    }
    const rows = [
      ["acc_rule", s.rule_hit, s.rule_total, ""],
      ["acc_nf", s.not_found_hit, s.not_found_total, "o"],
      ["acc_fig", s.figure_hit, s.figure_total, ""],
      ["acc_lang", s.lang_hit, s.lang_total, ""],
      ["acc_quotes", s.quotes_verified, s.quotes_total, "o"],
    ].filter((r) => r[2]);
    box.innerHTML = `<div class="acc">${rows.map(([k, a, b, o]) => `
      <div class="acc__row"><span class="acc__label">${esc(t(k))}</span><span class="acc__val">${a}/${b}</span>
      <span class="acc__bar ${o ? "acc__bar--o" : ""}"><i style="--w:${Math.round((a / b) * 100)}%"></i></span></div>`).join("")}
      ${s.median_seconds != null ? `<div class="acc__row"><span class="acc__label">${esc(t("acc_time"))}</span><span class="acc__val">${secs(s.median_seconds)}</span></div>` : ""}
      <p class="acc__foot">${esc(t("acc_foot"))} · ${esc(acc.run_date || "")} · ${esc(acc.model || "")}</p></div>`;
    requestAnimationFrame(() => $$(".acc__bar i", box).forEach((i) => { i.style.width = i.style.getPropertyValue("--w"); }));
  }

  function routerName(src) {
    return src === "cerebras" ? "Cerebras" : src === "groq" ? "gpt-oss-20b (Groq)" : t("st_rules");
  }

  function engineName(model) {
    const m = String(model || "");
    if (m.startsWith("groq:")) return `${m.slice(5).split("/").pop()} (Groq)`;
    return m ? "Claude" : "—";
  }

  /* ================================================================ examples */
  function renderExamples() {
    const tagText = { calc: t("tag_calc"), rule: t("tag_rule"), hi: t("tag_hi"), nf: t("tag_nf") };
    $("#examples").innerHTML = EXAMPLES.map((e, i) => `
      <button type="button" class="ex" data-ex="${i}" ${isHindi(e.q) ? 'lang="hi"' : ""}>
        <span class="ex__tag ${e.tag === "nf" ? "ex__tag--nf" : ""}">${esc(tagText[e.tag])}</span>
        <span class="ex__text" title="${esc(e.q)}">${esc(e.q)}</span>
      </button>`).join("");
  }

  /* ================================================================ ask */
  async function ask(question, opts = {}) {
    question = question.trim();
    if (!question || state.busy) return;
    state.controller?.abort();
    state.controller = new AbortController();
    Object.assign(state, { question, qLang: isHindi(question) ? "hi" : "en", route: null, calc: null, result: null, streamText: "", busy: true });

    $("#promise").hidden = true;
    const res = $("#result");
    res.hidden = false;
    res.style.animation = "none"; void res.offsetWidth; res.style.animation = "";
    $("#qecho").innerHTML = `<small>${esc(t("q_echo"))}</small><span ${state.qLang === "hi" ? 'lang="hi"' : ""}>${esc(question)}</span>`;
    ["#warnings-top", "#figs", "#proof", "#warnings-bottom"].forEach((s) => { $(s).innerHTML = ""; });
    $("#answer-wrap").innerHTML = `<div class="answer"><div class="answer__head"><span class="answer__kicker">${icon("lens")} ${esc(t("ans_kicker"))}</span></div><div class="skel"><i></i><i></i><i></i></div></div>`;
    $("#actions").hidden = true;
    setStage("route", "active");
    ["calc", "answer", "verify"].forEach((s) => setStage(s, ""));
    setBusy(true);
    res.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });

    try {
      const resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, fixture: opts.fixture || null }),
        signal: state.controller.signal,
      });
      if (!resp.ok || !resp.body) {
        let msg = `HTTP ${resp.status}`;
        try { msg = (await resp.json()).message || msg; } catch { /* not JSON */ }
        throw new Error(msg);
      }
      await readStream(resp.body, onEvent);
    } catch (err) {
      if (err.name !== "AbortError") renderError(String(err.message || err));
    } finally {
      setBusy(false);
      state.busy = false;
    }
  }

  async function readStream(body, handler) {
    const reader = body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        let ev = "message";
        const data = [];
        raw.split("\n").forEach((line) => {
          if (line.startsWith("event:")) ev = line.slice(6).trim();
          else if (line.startsWith("data:")) data.push(line.slice(line.startsWith("data: ") ? 6 : 5));
        });
        if (data.length) handler(ev, data.join("\n"));
      }
    }
  }

  function onEvent(kind, raw) {
    if (kind === "text") {
      state.streamText += raw;
      renderStreaming();
      return;
    }
    const data = JSON.parse(raw);
    if (kind === "route") {
      state.route = data;
      setStage("route", "done", `${routerName(data.source)} · ${secs(data.seconds)}`);
      setStage("calc", "active");
    } else if (kind === "calc") {
      state.calc = data;
      renderCalc(data);
      const n = data.results.length;
      setStage("calc", n ? "done" : "skip", n ? `${n} ✓` : t("st_none"));
      setStage("answer", "active");
    } else if (kind === "done") {
      state.result = data;
      renderFinal(data, { animate: true });
    } else if (kind === "error") {
      renderError(data.message);
    }
  }

  function setBusy(on) {
    const b = $("#ask-btn");
    b.classList.toggle("is-busy", on);
    b.disabled = on;
    $("span", b).textContent = on ? t("asking") : t("ask_btn");
  }

  function setStage(name, status, note = "") {
    const li = $(`.stage[data-stage="${name}"]`);
    li.classList.remove("is-active", "is-done", "is-skip", "is-fail");
    if (status) li.classList.add(`is-${status}`);
    $(".stage__s", li).textContent = note;
  }

  /* ================================================================ figures + plot */
  const unitText = (display) => (state.lang === "hi"
    ? display.replace(/\bsq m\b/g, "वर्ग मी.").replace(/^Rs /, "₹").replace(/ m\b/g, " मी.").replace(/^None$/, "आवश्यक नहीं").replace(/^Nil$/, "शून्य")
    : display);

  function renderCalc(calc) {
    const L = state.lang;
    const figs = calc.results.map((r, i) => `
      <button type="button" class="fig ${i === 0 ? "fig--lead" : ""}" style="--i:${i}" aria-expanded="false">
        <span class="fig__label">${esc(L === "hi" ? r.label_hi : r.label_en)}</span>
        ${figValue(r)}
        <span class="fig__src">${icon("book", "ic ic--sm")} ${esc(t("rule"))} ${esc(r.sub_rule)} · ${esc(t("page"))} ${r.page}</span>
        ${r.row_text ? `<span class="fig__row">${esc(t("fig_row"))}: ${esc(squashKeep(r.row_text))}</span>` : ""}
        ${r.verified ? `<span class="fig__badge">${icon("seal", "ic ic--sm")} ${esc(t("figs_badge"))}</span>` : ""}
        <span class="fig__more"><b>${esc(t("fig_open"))}:</b> ${esc(L === "hi" ? r.basis_hi : r.basis_en)}
          ${(L === "hi" ? r.assumptions_hi : r.assumptions_en).length ? `<ul>${(L === "hi" ? r.assumptions_hi : r.assumptions_en).map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
        </span>
      </button>`).join("");
    const notes = (L === "hi" ? calc.notes_hi : calc.notes_en).map((n) => `<p class="figs__note">${icon("info")} ${esc(n)}</p>`).join("");
    $("#figs").innerHTML = figs + notes;
    $$("#figs .fig").forEach((f) => f.addEventListener("click", () => {
      const open = f.classList.toggle("is-open");
      f.setAttribute("aria-expanded", String(open));
    }));
    const plot = plotDiagram(calc, state.route);
    if (plot) $("#figs").insertAdjacentHTML("afterend", plot);
  }

  function figValue(r) {
    const parts = String(r.display).split(" → ");
    if (r.key === "far" && parts.length === 2) {
      const label = state.lang === "hi" ? "अधिकतम निर्मित क्षेत्र" : "Max built-up area";
      return `<span class="fig__value">${esc(unitText(parts[1]))}</span><span class="fig__sub">${esc(label)} · FAR ${esc(parts[0])}</span>`;
    }
    return `<span class="fig__value">${esc(unitText(r.display))}</span>`;
  }

  const squashKeep = (s) => String(s).replace(/\s{2,}/g, "  ").trim();

  function plotDiagram(calc, route) {
    $(".plot")?.remove();
    const get = (k) => calc.results.find((r) => r.key === k);
    const front = get("front_setback"), rear = get("rear_setback"), side = get("side_setback");
    if (!front && !rear && !side) return "";
    const inp = route?.inputs || {};
    const area = inp.plot_area_sqm || 200;
    const depthM = Math.sqrt(area * 1.5), widthM = area / depthM;
    const X = 30, Y = 18, W = 214, H = 176, ppmY = H / depthM, ppmX = W / widthM;
    const fpx = front ? Math.max(front.value * ppmY, front.value ? 10 : 0) : 0;
    const rpx = rear ? Math.max(rear.value * ppmY, rear.value ? 10 : 0) : 0;
    const type = inp.building_type;
    const spx = side && side.value ? Math.max(side.value * ppmX, 10) : 0;
    const leftS = type === "detached" ? spx : 0, rightS = (type === "detached" || type === "semi_detached") ? spx : 0;
    const bx = X + leftS, by = Y + rpx, bw = W - leftS - rightS, bh = H - rpx - fpx;
    const L = (k) => esc(t(k));
    const m = (v) => unitText(`${Number(v).toFixed(1)} m`);
    const band = (x, y, w, h) => (w > 0 && h > 0 ? `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="url(#hatch)"/>` : "");
    const svg = `
<svg viewBox="0 0 340 262" role="img" aria-label="${L("plot_t")}">
  <defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="7" height="7" fill="#fff"/><rect width="3.2" height="7" fill="#FED7AA"/></pattern></defs>
  <rect x="0" y="${Y + H + 12}" width="340" height="40" fill="#CFCFCF"/>
  <line x1="0" x2="340" y1="${Y + H + 32}" y2="${Y + H + 32}" stroke="#111" stroke-width="2" stroke-dasharray="10 8"/>
  <text x="${X + W / 2}" y="${Y + H + 54}" text-anchor="middle" font-size="11" font-weight="700" fill="#111">${L("plot_road")}${inp.road_width_m ? ` · ${m(inp.road_width_m)}` : ""}</text>
  ${band(X, Y + H - fpx, W, fpx)}${band(X, Y, W, rpx)}${band(X, Y + rpx, leftS, H - rpx - fpx)}${band(X + W - rightS, Y + rpx, rightS, H - rpx - fpx)}
  <rect x="${bx + 3}" y="${by + 3}" width="${Math.max(bw - 6, 0)}" height="${Math.max(bh - 6, 0)}" fill="#fff" stroke="#111" stroke-width="2" stroke-dasharray="6 4"/>
  <text x="${bx + bw / 2}" y="${by + bh / 2 + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="#111">${L("plot_build")}</text>
  <rect x="${X}" y="${Y}" width="${W}" height="${H}" fill="none" stroke="#111" stroke-width="2.5"/>
  ${front ? `<text x="${X + W + 8}" y="${Y + H - fpx / 2 + 4}" font-size="11" font-weight="800" fill="#C2410C">${L("plot_front")} ${m(front.value)}</text>` : ""}
  ${rear ? `<text x="${X + W + 8}" y="${Y + rpx / 2 + 4}" font-size="11" font-weight="800" fill="#C2410C">${L("plot_rear")} ${rear.value ? m(rear.value) : unitText("Nil")}</text>` : ""}
  ${side && spx ? `<text x="${X + W + 8}" y="${Y + H / 2 + 4}" font-size="11" font-weight="800" fill="#C2410C">${L("plot_side")} ${m(side.value)}</text>` : ""}
</svg>`;
    return `<div class="plot">${svg}<div><h3>${icon("plot")} ${L("plot_t")}</h3><p>${L("plot_d")}</p>
      <div class="legend"><span><i class="sw sw--open"></i>${L("plot_open")}</span><span><i class="sw sw--build"></i>${L("plot_build")}</span><span><i class="sw sw--road"></i>${L("plot_road")}</span></div></div></div>`;
  }

  /* ================================================================ answer */
  function highlightRules(text) {
    return esc(text).replace(/((?:Rule|Rules|नियम)\s*\d{1,3}(?:-[A-Za-z])?(?:\s*\([0-9a-zA-Z]{1,4}\))*)/g, '<span class="rref">$1</span>');
  }

  function renderStreaming() {
    let el = $("#answer-wrap .answer__text");
    if (!el) {
      $("#answer-wrap").innerHTML = `<div class="answer"><div class="answer__head"><span class="answer__kicker">${icon("lens")} ${esc(t("ans_kicker"))}</span></div>
        <div class="answer__text is-streaming" ${state.qLang === "hi" ? 'lang="hi"' : ""} aria-busy="true"></div></div>`;
      el = $("#answer-wrap .answer__text");
    }
    el.textContent = state.streamText;
  }

  function renderFinal(result, { animate }) {
    const a = result.answer;
    state.qLang = a.lang === "hi" || isHindi(result.question) ? "hi" : "en";
    if (result.calc) {
      state.route = result.route;
      if (!animate || !state.calc) { state.calc = result.calc; renderCalc(result.calc); }
      state.calc = result.calc;
    }

    // stages
    if (result.route) setStage("route", "done", `${routerName(result.route.source)} · ${secs(result.route.seconds)}`);
    const n = result.calc?.results?.length || 0;
    setStage("calc", n ? "done" : "skip", n ? `${n} · ${secs(result.seconds_to_first_figure)}` : t("st_none"));
    if (a.status === "error") setStage("answer", "fail", "");
    else setStage("answer", "done", `${engineName(a.model)} · ${secs(a.timing?.total_s)}`);
    const removed = (a.warnings || []).filter((w) => w.kind === "unverified").length;
    const nver = (a.citations || []).filter((c) => c.verified).length;
    if (a.status === "answered" || a.status === "unverified") setStage("verify", nver ? "done" : "fail", `${nver} ${t("st_verified")}${removed ? ` · ${t("st_removed")}` : ""}`);
    else setStage("verify", "skip", t("st_none"));

    // warnings
    const warns = a.warnings || [];
    $("#warnings-top").innerHTML = warns.filter((w) => w.kind === "amendment").map(warnHtml).join("");
    $("#warnings-bottom").innerHTML = warns.filter((w) => w.kind !== "amendment").map(warnHtml).join("");

    // body by status
    const wrap = $("#answer-wrap");
    if (a.status === "not_found") {
      wrap.innerHTML = `<div class="state state--nf"><span class="state__icon">${icon("notfound")}</span><div>
        <h3>${esc(tq("nf_t"))}</h3><p ${state.qLang === "hi" ? 'lang="hi"' : ""}>${esc(a.not_found_reason || tq("nf_d"))}</p>
        ${a.suggestion ? `<p><b>${esc(tq("nf_where"))}:</b> ${esc(a.suggestion)}</p>` : ""}
        <p class="muted">${esc(tq("nf_d"))}</p></div></div>`;
    } else if (a.status === "need_inputs") {
      wrap.innerHTML = inputsHtml(a, result.calc);
      bindInputs();
    } else if (a.status === "error") {
      renderError(a.error);
    } else {
      const unverified = a.status === "unverified";
      const rules = [...new Set((a.citations || []).map((c) => c.rule))];
      wrap.innerHTML = `<div class="answer ${unverified ? "answer--unverified" : ""}">
        <div class="answer__head"><span class="answer__kicker">${icon("lens")} ${esc(t("ans_kicker"))} · ${esc(t(state.qLang === "hi" ? "ans_lang_hi" : "ans_lang_en"))}</span>
        ${unverified ? `<span class="badge badge--o">${icon("alert", "ic ic--sm")} ${esc(t("ans_unverified"))}</span>` : `<span class="badge badge--ink">${icon("seal", "ic ic--sm")} ${esc(t("b_verified"))}</span>`}</div>
        <div class="answer__text" ${state.qLang === "hi" ? 'lang="hi"' : ""}>${highlightRules(a.text)}</div>
        ${unverified ? `<p class="warn__d" style="margin-top:10px">${esc(t("ans_unverified_d"))}</p>` : ""}
        <div class="answer__meta">
          <span class="badge">${icon("book", "ic ic--sm")} ${rules.length} ${esc(t("b_cited"))}</span>
          <span class="badge">${icon("seal", "ic ic--sm")} ${nver} ${esc(t("b_quotes"))}</span>
          <span class="badge badge--muted">${icon("clock", "ic ic--sm")} ${secs(result.seconds_total)}</span>
        </div></div>`;
      $("#proof").innerHTML = proofHtml(a.citations || [], result.calc);
      bindProof();
    }
    $("#actions").hidden = !(a.status === "answered" || a.status === "unverified" || a.status === "not_found");
  }

  function warnHtml(w) {
    const text = state.qLang === "hi" ? w.text_hi : w.text_en;
    return `<div class="warn warn--${esc(w.kind)}" role="${w.kind === "amendment" ? "alert" : "note"}">${icon(w.kind === "table" || w.kind === "info" ? "info" : "alert")}
      <div><p class="warn__t">${esc(t(`w_${w.kind}`))}</p><p class="warn__d">${esc(text)}</p>
      ${w.source_url ? `<p class="warn__d"><a href="${esc(w.source_url)}" target="_blank" rel="noopener">${esc(t("w_source"))} ${icon("external", "ic ic--sm")}</a></p>` : ""}</div></div>`;
  }

  function proofHtml(cites, calc) {
    if (!cites.length) return "";
    const rows = (calc?.results || []).map((r) => ({ rule: r.rule, row: squash(r.row_text) })).filter((r) => r.row);
    const cards = cites.slice(0, 8).map((c, i) => {
      const lines = c.quote.split("\n").map((ln) => {
        const hit = rows.some((r) => r.rule === c.rule && squash(ln).includes(r.row));
        return hit ? `<mark>${esc(ln)}</mark>` : esc(ln);
      }).join("\n");
      return `<article class="cite" style="--i:${i}">
        <header class="cite__head"><span class="cite__rule">${esc(t("rule"))} ${esc(c.rule)}</span><span class="cite__title">${esc(c.title)}</span>
          ${c.is_table ? `<span class="badge">${esc(t("cite_table"))}</span>` : ""}
          <span class="cite__page">${esc(t("page"))} ${c.page}</span>
          ${c.verified ? `<span class="badge badge--ink">${icon("seal", "ic ic--sm")} ${esc(t("b_verified"))}</span>` : ""}</header>
        ${c.supports ? `<p class="cite__supports" ${isHindi(c.supports) ? 'lang="hi"' : ""}><b>${esc(t("cite_supports"))}:</b> ${esc(c.supports.length > 220 ? c.supports.slice(0, 218) + "…" : c.supports)}</p>` : ""}
        <pre class="cite__quote" tabindex="0">${lines}</pre>
        <div class="cite__actions">
          <a class="btn" href="/rules.pdf#page=${c.page}" target="_blank" rel="noopener">${icon("page")} ${esc(t("cite_pdf"))} ${c.page}</a>
          <button class="btn" data-rule="${esc(c.rule)}">${icon("book")} ${esc(t("cite_full"))}</button>
          <button class="btn" data-copy="${i}">${icon("copy")} ${esc(t("cite_copy"))}</button>
        </div></article>`;
    }).join("");
    return `<section class="proof"><h3 class="proof__h">${icon("seal")} ${esc(t("proof_h"))}</h3>${cards}</section>`;
  }

  function bindProof() {
    $$("#proof [data-rule]").forEach((b) => b.addEventListener("click", () => openRule(b.dataset.rule, b)));
    $$("#proof [data-copy]").forEach((b) => b.addEventListener("click", () => {
      const c = state.result.answer.citations[Number(b.dataset.copy)];
      copy(`${t("rule")} ${c.rule}, ${t("page")} ${c.page}\n${c.quote}`);
    }));
  }

  /* ================================================================ need inputs */
  const NUM_UNITS = { road_width_m: "m", building_height_m: "m", plot_area_sqm: "sq m", built_up_area_sqm: "sq m", frontage_m: "m" };

  function inputsHtml(a, calc) {
    const fields = [];
    (a.missing_inputs || []).forEach((m) => fields.push(m.field));
    (calc?.missing || []).forEach((m) => m.fields.forEach((f) => fields.push(f)));
    const uniq = [...new Set(fields)].filter(Boolean);
    const F = I18N[state.lang].fields;
    const field = (f) => {
      if (f === "building_use") return `<label class="field">${esc(F[f])}<span class="field__box"><select name="${f}">${Object.entries(I18N[state.lang].uses).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></span></label>`;
      if (f === "building_type") return `<label class="field">${esc(F[f])}<span class="field__box"><select name="${f}">${Object.entries(I18N[state.lang].types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></span></label>`;
      if (NUM_UNITS[f]) return `<label class="field">${esc(F[f])}<span class="field__box"><input name="${f}" type="number" min="0" step="0.01" inputmode="decimal" required><span class="field__unit">${NUM_UNITS[f]}</span></span></label>`;
      return `<label class="field">${esc(F[f] || f)}<span class="field__box"><input name="${f}" type="text"></span></label>`;
    };
    return `<form class="state state--inputs" id="inputs-form"><span class="state__icon">${icon("ruler")}</span><div style="flex:1">
      <h3>${esc(t("in_t"))}</h3><p ${state.qLang === "hi" ? 'lang="hi"' : ""}>${esc(a.not_found_reason || "")}</p>
      <div class="inputs">${uniq.map(field).join("")}</div>
      <div style="margin-top:14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><button class="btn btn--primary" type="submit">${icon("calc")} ${esc(t("in_btn"))}</button>
      <span class="muted">${esc(t("in_note"))}</span></div></div></form>`;
  }

  function bindInputs() {
    const form = $("#inputs-form");
    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      const hi = state.qLang === "hi";
      const F = I18N[hi ? "hi" : "en"].fields;
      const units = { m: hi ? "मीटर" : "m", "sq m": hi ? "वर्ग मीटर" : "sq m" };
      const facts = [...new FormData(form).entries()].filter(([, v]) => String(v).trim()).map(([k, v]) => {
        const label = F[k] || k;
        if (k === "building_use") return `${label}: ${I18N[hi ? "hi" : "en"].uses[v]}`;
        if (k === "building_type") return `${label}: ${I18N[hi ? "hi" : "en"].types[v]}`;
        return `${label}: ${v}${NUM_UNITS[k] ? " " + units[NUM_UNITS[k]] : ""}`;
      });
      const q = `${state.question}\n${facts.join(hi ? "। " : ". ")}${hi ? "।" : "."}`;
      $("#q").value = q;
      ask(q);
    });
  }

  /* ================================================================ error */
  function renderError(message) {
    setStage("answer", "fail");
    setStage("verify", "skip", t("st_none"));
    $("#answer-wrap").innerHTML = `<div class="state state--err" role="alert"><span class="state__icon">${icon("alert")}</span><div>
      <h3>${esc(t("err_t"))}</h3><p>${esc(message)}</p>
      <p style="margin-top:12px"><button class="btn" id="retry-btn">${icon("arrow")} ${esc(t("err_retry"))}</button></p></div></div>`;
    $("#retry-btn").addEventListener("click", () => ask(state.question));
  }

  /* ================================================================ rule drawer */
  let lastFocus = null;
  async function openRule(rule, opener) {
    lastFocus = opener || document.activeElement;
    const d = $("#drawer");
    d.hidden = false;
    d.classList.remove("is-closing");
    $("#drawer-kicker").textContent = `${t("rule")} ${rule}`;
    $("#drawer-title").textContent = "…";
    $("#drawer-body").innerHTML = `<div class="skel"><i></i><i></i><i></i></div>`;
    $(".drawer__head [data-close]").focus();
    try {
      const r = await (await fetch(`/api/rule/${encodeURIComponent(rule)}`)).json();
      $("#drawer-title").textContent = r.title;
      $("#drawer-kicker").textContent = `${t("rule")} ${r.rule} · ${r.part} · ${t("page")} ${r.page_start}–${r.page_end}`;
      const cited = (state.result?.answer?.citations || []).filter((c) => c.rule === r.rule).map((c) => squash(c.quote));
      let page = null;
      $("#drawer-body").innerHTML = r.blocks.map((b) => {
        const brk = b.page !== page ? `<div class="pgbreak">${esc(t("page"))} ${b.page}</div>` : "";
        page = b.page;
        const hit = cited.some((q) => q.includes(squash(b.text)) || squash(b.text).includes(q));
        return `${brk}<pre class="blk ${hit ? "is-cited" : ""}">${esc(b.text)}</pre>`;
      }).join("");
      $(".blk.is-cited", $("#drawer-body"))?.scrollIntoView({ block: "center" });
    } catch {
      $("#drawer-body").textContent = "—";
    }
  }

  function closeDrawer() {
    const d = $("#drawer");
    if (d.hidden) return;
    d.classList.add("is-closing");
    setTimeout(() => { d.hidden = true; lastFocus?.focus?.(); }, reduceMotion ? 0 : 220);
  }

  /* ================================================================ actions */
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast(t("copied")); } catch { /* clipboard blocked */ }
  }

  function answerAsText() {
    const r = state.result;
    if (!r) return "";
    const a = r.answer;
    const parts = [`${t("q_echo")}: ${r.question}`, ""];
    if (a.status === "not_found") parts.push(`${tq("nf_t")}. ${a.not_found_reason}`);
    else parts.push(a.text);
    (r.calc?.results || []).forEach((c) => parts.push(`${c.label_en}: ${c.display} (Rule ${c.sub_rule}, page ${c.page})`));
    (a.citations || []).forEach((c) => parts.push("", `Rule ${c.rule}, page ${c.page}:`, c.quote.replace(/\s+/g, " ").trim()));
    parts.push("", "MP Bhumi Vikas Rules 2012, consolidated to 06-03-2025 · Kshiti");
    return parts.join("\n");
  }

  async function downloadPdf() {
    if (!state.result) return;
    const btn = $("#pdf-btn");
    btn.disabled = true;
    toast(t("pdf_wait"));
    try {
      const resp = await fetch("/api/slip", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.result) });
      if (resp.status === 404 || resp.status === 405) { toast(t("pdf_soon")); return; }
      if (!resp.ok) throw new Error(String(resp.status));
      const blob = await resp.blob();
      const name = (resp.headers.get("Content-Disposition") || "").match(/filename="?([^"]+)"?/)?.[1] || "kshiti-answer.pdf";
      const url = URL.createObjectURL(blob);
      const link = Object.assign(document.createElement("a"), { href: url, download: name });
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (e) {
      toast(`PDF: ${e.message}`);
    } finally {
      btn.disabled = false;
    }
  }

  function toast(msg) {
    const el = document.createElement("div");
    el.className = "toast";
    el.innerHTML = `${icon("seal")}<span>${esc(msg)}</span>`;
    $("#toasts").append(el);
    setTimeout(() => { el.classList.add("is-out"); setTimeout(() => el.remove(), 260); }, 2600);
  }

  function resetToStart() {
    state.controller?.abort();
    Object.assign(state, { result: null, calc: null, route: null, streamText: "", busy: false });
    $("#result").hidden = true;
    $(".plot")?.remove();
    $("#promise").hidden = false;
    $("#q").value = "";
    $("#q").focus();
    window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
  }

  /* ================================================================ wiring */
  function bind() {
    $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); ask($("#q").value); });
    $("#q").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask($("#q").value); }
    });
    $("#q").addEventListener("input", (e) => {
      const el = e.target;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
    });
    $("#examples").addEventListener("click", (e) => {
      const b = e.target.closest("[data-ex]");
      if (!b) return;
      const q = EXAMPLES[Number(b.dataset.ex)].q;
      $("#q").value = q;
      ask(q);
    });
    $$(".seg--lang .seg__b").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.lang)));
    $$("[data-size]").forEach((b) => b.addEventListener("click", () => applySize(b.dataset.size)));
    $("#contrast-btn").addEventListener("click", () => applyContrast(!document.documentElement.classList.contains("hc")));
    $("#copy-btn").addEventListener("click", () => copy(answerAsText()));
    $("#new-btn").addEventListener("click", resetToStart);
    $("#pdf-btn").addEventListener("click", downloadPdf);
    $$("[data-fb]").forEach((b) => b.addEventListener("click", () => {
      $$("[data-fb]").forEach((x) => x.classList.toggle("is-picked", x === b));
      const log = JSON.parse(localStorage.getItem("kshiti.feedback") || "[]");
      log.push({ q: state.question, verdict: b.dataset.fb, at: new Date().toISOString(), rules: state.result?.answer?.citations?.map((c) => c.rule) });
      localStorage.setItem("kshiti.feedback", JSON.stringify(log.slice(-200)));
      toast(t("fb_thanks"));
    }));
    $$("#drawer [data-close]").forEach((b) => b.addEventListener("click", closeDrawer));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDrawer();
      if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) { e.preventDefault(); $("#q").focus(); }
    });

    // Soft light that follows the pointer across the question card.
    const card = $("#askcard");
    let raf = 0;
    card.addEventListener("pointermove", (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${e.clientX - r.left}px`);
        card.style.setProperty("--my", `${e.clientY - r.top}px`);
        raf = 0;
      });
    });
  }

  async function init() {
    applySize(localStorage.getItem("kshiti.size") || "md");
    applyContrast(localStorage.getItem("kshiti.hc") === "1");
    applyLang(state.lang);
    bind();
    loadMeta();
    await splash();
    if (params.get("q")) {
      $("#q").value = params.get("q");
      ask(params.get("q"), { fixture: params.get("fixture") });
    }
  }

  init();
})();
