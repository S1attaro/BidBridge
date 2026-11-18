// Jobs page: map + state list at the top, jobs below, details slide in from the right.
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("map");
  var wrap = document.getElementById("mapwrap");
  var tip = document.getElementById("tip");
  var results = document.getElementById("results");
  var filters = document.querySelector(".js-filters");
  var panel = document.getElementById("panel");
  var scrim = document.getElementById("scrim");
  var counts = JSON.parse(document.getElementById("state-counts").textContent);
  var picked = JSON.parse(document.getElementById("picked-states").textContent);
  var names = {};
  document.querySelectorAll(".opt").forEach(function (li) { names[li.dataset.st] = li.querySelector(".name").textContent; });

  // Same urgency scale as the server (core/templatetags/bb.py).
  var STOPS = [[0, [217, 45, 32]], [7, [240, 124, 18]], [14, [224, 177, 10]], [21, [47, 154, 92]]];
  function urgency(d) {
    d = Math.max(0, Math.min(21, d));
    for (var i = 1; i < STOPS.length; i++) {
      if (d <= STOPS[i][0]) {
        var a = STOPS[i - 1], b = STOPS[i], t = (d - a[0]) / (b[0] - a[0]);
        return "rgb(" + a[1].map(function (v, k) { return Math.round(v + (b[1][k] - v) * t); }).join(",") + ")";
      }
    }
    return "rgb(47,154,92)";
  }

  function el(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    parent.appendChild(e);
    return e;
  }

  // ---------- Map ----------

  var max = Math.max.apply(null, Object.values(counts).concat([1]));
  function shade(n) {
    var k = Math.pow((n || 0) / max, .5);
    var a = [233, 237, 248], b = [159, 176, 245], c = [59, 91, 253];
    var from = k < .5 ? a : b, to = k < .5 ? b : c, t = k < .5 ? k * 2 : (k - .5) * 2;
    return "rgb(" + from.map(function (v, i) { return Math.round(v + (to[i] - v) * t); }).join(",") + ")";
  }
  var gStates = el("g", {}, svg), gDots = el("g", {}, svg);
  var projection = window.d3 ? d3.geoAlbersUsa().scale(1300).translate([487.5, 305]) : null;

  fetch(window.BB_MAP_URL).then(function (r) { return r.json(); }).then(function (shapes) {
    Object.keys(shapes).forEach(function (code) {
      var n = counts[code] || 0;
      var p = el("path", { d: shapes[code].d, class: "state", "data-st": code, tabindex: 0, role: "button",
        "aria-label": shapes[code].name + ", " + n + " open jobs" }, gStates);
      p.style.fill = shade(n);
      p.addEventListener("mousemove", function (e) {
        var r = wrap.getBoundingClientRect();
        tip.innerHTML = shapes[code].name + "<span>" + n.toLocaleString() + " open jobs</span>";
        tip.style.left = (e.clientX - r.left) + "px"; tip.style.top = (e.clientY - r.top) + "px";
        tip.classList.add("on");
      });
      p.addEventListener("mouseleave", function () { tip.classList.remove("on"); });
      p.addEventListener("click", function () { toggle(code, true); });
      p.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(code, true); } });
    });
    paint();
    drawDots();
  });

  function drawDots() {
    gDots.innerHTML = "";
    if (!projection || !picked.length) return;
    results.querySelectorAll(".row[data-lat]").forEach(function (row) {
      var xy = projection([+row.dataset.lon, +row.dataset.lat]);
      if (!xy) return;
      var dot = el("circle", { cx: xy[0], cy: xy[1], r: 3.8, class: "dot" }, gDots);
      dot.style.fill = urgency(+row.dataset.days);
    });
  }

  function paint() {
    svg.querySelectorAll(".state").forEach(function (p) { p.classList.toggle("sel", picked.indexOf(p.dataset.st) > -1); });
    wrap.classList.toggle("has-sel", picked.length > 0);
  }

  // ---------- State list beside the map ----------

  var opts = document.getElementById("opts");
  var find = document.getElementById("stateFind");
  var go = document.getElementById("goSt");
  var all = Array.prototype.slice.call(opts.querySelectorAll(".opt"));
  var active = 0;

  function drawList() {
    svg.querySelectorAll(".state.peek").forEach(function (x) { x.classList.remove("peek"); });
    var q = find.value.trim().toLowerCase();
    var shown = all.filter(function (li) {
      var nm = names[li.dataset.st].toLowerCase();
      return !q || nm.indexOf(q) > -1 || li.dataset.st.toLowerCase() === q;
    });
    if (q) shown.sort(function (a, b) {
      var sa = names[a.dataset.st].toLowerCase().indexOf(q) === 0 ? 0 : 1;
      var sb = names[b.dataset.st].toLowerCase().indexOf(q) === 0 ? 0 : 1;
      return sa - sb || names[a.dataset.st].localeCompare(names[b.dataset.st]);
    });
    if (active >= shown.length) active = 0;
    opts.innerHTML = "";
    shown.forEach(function (li, i) {
      var nm = names[li.dataset.st], at = nm.toLowerCase().indexOf(q);
      li.querySelector(".name").innerHTML = q && at > -1
        ? escape(nm.slice(0, at)) + "<mark>" + escape(nm.slice(at, at + q.length)) + "</mark>" + escape(nm.slice(at + q.length)) : escape(nm);
      var on = picked.indexOf(li.dataset.st) > -1;
      li.classList.toggle("sel", on);
      li.setAttribute("aria-selected", on);
      li.classList.toggle("active", !!q && i === active);
      opts.appendChild(li);
    });
    if (!shown.length) {
      var none = document.createElement("li");
      none.className = "no-match";
      none.textContent = 'No state matches "' + find.value + '"';
      opts.appendChild(none);
    }
    document.getElementById("pickedChips").innerHTML = picked.map(function (c) {
      return '<button type="button" data-st="' + c + '" aria-label="Remove ' + escape(names[c]) + '">' + escape(names[c]) + "<b>&times;</b></button>";
    }).join("");
    var total = picked.reduce(function (t, c) { return t + (counts[c] || 0); }, 0);
    go.disabled = !picked.length;
    go.textContent = picked.length ? "Show " + total.toLocaleString() + " jobs" : "Show jobs";
  }
  function escape(s) { return String(s).replace(/[&<>"]/g, function (ch) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]; }); }

  opts.addEventListener("click", function (e) { var li = e.target.closest(".opt"); if (li) toggle(li.dataset.st, false); });
  opts.addEventListener("mouseover", function (e) { var li = e.target.closest(".opt"); if (li) peek(li.dataset.st, true); });
  opts.addEventListener("mouseout", function (e) { var li = e.target.closest(".opt"); if (li) peek(li.dataset.st, false); });
  document.getElementById("pickedChips").addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) toggle(b.dataset.st, false); });
  function peek(code, on) { var p = svg.querySelector('.state[data-st="' + code + '"]'); if (p) p.classList.toggle("peek", on); }
  find.addEventListener("input", function () { active = 0; drawList(); });
  find.addEventListener("keydown", function (e) {
    var items = opts.querySelectorAll(".opt");
    if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, items.length - 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); }
    else if (e.key === "Enter" && items[active]) { e.preventDefault(); toggle(items[active].dataset.st, false); find.value = ""; active = 0; }
    else return;
    drawList();
    var a = opts.querySelectorAll(".opt")[active];
    if (a) { a.classList.add("active"); a.scrollIntoView({ block: "nearest" }); }
  });
  go.addEventListener("click", function () { scrollToJobs(); });
  document.getElementById("clearSt").addEventListener("click", function () { picked = []; paint(); drawList(); load(); });

  // From the map, a pick takes you down to the jobs. From the list you can pick several first.
  function toggle(code, scroll) {
    var i = picked.indexOf(code);
    if (i > -1) picked.splice(i, 1); else picked.push(code);
    paint();
    drawList();
    load();
    if (i === -1 && scroll) setTimeout(scrollToJobs, 380);
  }
  function scrollToJobs() { document.getElementById("listings").scrollIntoView({ behavior: "smooth" }); }

  // ---------- Jobs list ----------

  function query(extra) {
    var params = new URLSearchParams(new FormData(filters));
    var due = filters.querySelector(".when button.on");
    if (due && due.dataset.due) params.set("when", due.dataset.due);
    var can = document.getElementById("canBid");
    if (can && can.getAttribute("aria-pressed") === "true") params.set("can_bid", "1");
    picked.forEach(function (s) { params.append("state", s); });
    Array.from(params.keys()).forEach(function (k) { if (!params.get(k)) params.delete(k); });
    if (extra) Object.keys(extra).forEach(function (k) { params.set(k, extra[k]); });
    return params.toString();
  }

  var pending;
  function load(qs) {
    qs = qs === undefined ? query() : qs;
    results.classList.add("loading");
    if (pending) pending.abort();
    pending = new AbortController();
    fetch(window.BB_LIST_URL + "?" + qs, { headers: { "X-Partial": "1" }, signal: pending.signal })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        results.innerHTML = html;
        results.classList.remove("loading");
        history.replaceState(null, "", window.BB_LIST_URL + (qs ? "?" + qs : ""));
        heading();
        drawDots();
      })
      .catch(function (e) { if (e.name !== "AbortError") results.classList.remove("loading"); });
  }

  function heading() {
    var meta = results.querySelector(".js-meta");
    var n = meta ? +meta.dataset.count : 0;
    document.getElementById("title").firstChild.textContent =
      picked.length === 0 ? "All states " : picked.length === 1 ? names[picked[0]] + " " : picked.length + " states ";
    document.getElementById("n").textContent = n.toLocaleString() + (n === 1 ? " job" : " jobs");
    document.getElementById("chips").innerHTML = picked.map(function (c) {
      return '<button type="button" class="chip-st" data-st="' + c + '" aria-label="Remove ' + escape(names[c]) + '">' + escape(names[c]) + "<b>&times;</b></button>";
    }).join("") + '<a class="add-st" href="#">' + (picked.length ? "+ Add a state" : "Pick a state on the map") + "</a>";
  }
  document.getElementById("chips").addEventListener("click", function (e) {
    var chip = e.target.closest(".chip-st");
    if (chip) { toggle(chip.dataset.st, false); return; }
    if (e.target.closest(".add-st")) { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }); }
  });

  filters.addEventListener("change", function () { load(); });
  filters.addEventListener("submit", function (e) { e.preventDefault(); load(); });
  filters.querySelectorAll(".when button").forEach(function (b) {
    b.addEventListener("click", function () {
      filters.querySelectorAll(".when button").forEach(function (x) { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
      load();
    });
  });
  var can = document.getElementById("canBid");
  if (can) can.addEventListener("click", function () { can.setAttribute("aria-pressed", can.getAttribute("aria-pressed") !== "true"); load(); });
  function pickWhen(value) {
    filters.querySelectorAll(".when button").forEach(function (x) {
      var on = x.dataset.due === value;
      x.classList.toggle("on", on);
      x.setAttribute("aria-pressed", on);
    });
  }
  results.addEventListener("click", function (e) {
    var band = e.target.closest(".see-band");
    if (!band) return;
    pickWhen(band.dataset.when);
    load();
    document.getElementById("listings").scrollIntoView({ behavior: "smooth" });
  });
  results.addEventListener("click", function (e) {
    var page = e.target.closest(".js-page");
    if (!page) return;
    e.preventDefault();
    load(page.getAttribute("href").replace(/^\?/, ""));
    document.getElementById("listings").scrollIntoView({ behavior: "smooth" });
  });

  // ---------- Details panel ----------

  var opener = null;
  results.addEventListener("click", function (e) {
    var link = e.target.closest(".js-open");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    opener = link;
    panel.innerHTML = '<div class="p-body"><div class="loading-line" style="padding-top:30px"><span class="spinner"></span>Opening...</div></div>';
    openPanel();
    fetch(link.dataset.panel).then(function (r) { return r.text(); }).then(function (html) {
      panel.innerHTML = html;
      if (window.hookSummary) window.hookSummary(panel);
      var close = panel.querySelector(".js-close");
      if (close) { close.addEventListener("click", closePanel); close.focus(); }
    });
  });
  function openPanel() { panel.classList.add("open"); panel.setAttribute("aria-hidden", "false"); scrim.classList.add("on"); }
  function closePanel() {
    panel.classList.remove("open"); panel.setAttribute("aria-hidden", "true"); scrim.classList.remove("on");
    if (opener) opener.focus({ preventScroll: true });
  }
  scrim.addEventListener("click", closePanel);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && panel.classList.contains("open")) closePanel(); });

  drawList();
  heading();
  if (location.search && (picked.length || /[?&](q|trade|when|can_bid)=/.test(location.search))) {
    setTimeout(function () { document.getElementById("listings").scrollIntoView(); }, 50);
  }
})();
