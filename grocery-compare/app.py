#!/usr/bin/env python3
"""Grocery price comparison — Aldi vs Kroger vs Meijer vs Walmart.

UI shell + architecture. Price providers start as stubs (returning no
prices); real integrations get wired into providers/ later. Never invent
prices: a store with no data shows as such.
"""
import importlib
import threading
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request, Response

from providers import engine

app = Flask(__name__)

DEFAULT_ZIP = "43228"
PROVIDER_MODULES = ["aldi", "kroger", "meijer", "walmart"]


def load_providers():
    providers = []
    for mod_name in PROVIDER_MODULES:
        mod = importlib.import_module("providers." + mod_name)
        providers.append(mod)
    return providers


PROVIDERS = load_providers()


def provider_statuses():
    out = []
    for mod in PROVIDERS:
        st = dict(mod.PROVIDER_STATUS)
        out.append({"store": mod.STORE_NAME, **st})
    return out


def pick_winner(results):
    """Cheapest result with a real price, or None."""
    priced = [r for r in results
              if isinstance(r.get("price"), (int, float))]
    if not priced:
        return None
    return min(priced, key=lambda r: r["price"])


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ API ---
# Scrapes are slow (JS-heavy store sites), so searches run as background
# jobs: POST starts the job and returns a job_id immediately; the frontend
# polls GET /api/job/<id> until status is "done" or "error".

@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/api/test-aldi")
def api_test_aldi():
    """Diagnostic: explore Aldi's actual DOM structure."""
    import time
    t0 = time.time()
    try:
        from providers import engine as _eng

        async def probe():
            browser, sem = await _eng._ensure()
            async with sem:
                page, ctx = await _eng._new_page(browser)
                try:
                    await page.goto(
                        "https://www.aldi.us/store/aldi/s?k=milk",
                        wait_until="domcontentloaded", timeout=40000)
                    await page.wait_for_timeout(8000)
                    info = await page.evaluate("""() => {
                      const main = document.querySelector('main');
                      const mains = [...document.querySelectorAll('main')].length;
                      const h3all = [...document.querySelectorAll('h3')]
                        .slice(0, 5).map(e => e.innerText.trim().slice(0,60));
                      const btns = [...document.querySelectorAll('button')]
                        .slice(0, 5).map(e => e.innerText.trim().slice(0,60));
                      // what repeating structures exist in main?
                      const kids = main
                        ? [...main.querySelectorAll('div')].slice(0,3).map(
                            d => (d.getAttribute('role')||'')
                              + '|' + (d.className||'').toString().slice(0,60))
                        : [];
                      const bodyTxt = document.body.innerText.slice(0, 400);
                      return {mains, h3all, btns, kids, bodyTxt};
                    }""")
                    info["url"] = page.url[:120]
                    return info
                finally:
                    try:
                        await ctx.close()
                    except Exception:
                        pass

        info = _eng.run(probe())
        info["elapsed"] = round(time.time() - t0, 1)
        info["ok"] = True
        return jsonify(info)
    except Exception as e:
        return jsonify({"ok": False, "elapsed": round(time.time() - t0, 1),
                        "error": str(e)[:300]})


@app.route("/api/debug")
def api_debug():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith(("MemTotal:", "MemAvailable:")):
                    k, v = line.split(":")
                    info[k.strip()] = v.strip()
    except Exception as e:
        info["mem_error"] = str(e)
    import os as _os
    info["https_proxy_set"] = bool(_os.environ.get("HTTPS_PROXY")
                                   or _os.environ.get("https_proxy"))
    info["grocery_proxy_set"] = bool(_os.environ.get("GROCERY_PROXY"))
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            info["cgroup_max"] = f.read().strip()
    except Exception:
        try:
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                info["cgroup_max"] = f.read().strip()
        except Exception as e:
            info["cgroup_max"] = "unknown: %s" % e
    try:
        from providers import engine as _eng
        info["browser_started"] = _eng._browser is not None
    except Exception as e:
        info["browser_error"] = str(e)[:100]
    with JOBS_LOCK:
        info["jobs"] = len(JOBS)
    return jsonify(info)


JOBS = {}
JOBS_LOCK = threading.Lock()


def _new_job(kind, label):
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"job_id": job_id, "kind": kind, "label": label,
                        "status": "pending", "created": utc_now_iso()}
        # keep memory bounded
        while len(JOBS) > 50:
            oldest = min(JOBS, key=lambda k: JOBS[k]["created"])
            del JOBS[oldest]
    return job_id


def _finish_job(job_id, payload):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(payload)
            JOBS[job_id]["status"] = "done"


def _fail_job(job_id, error):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(error)[:200]


def _collect(by_store):
    results = []
    for mod in PROVIDERS:
        res, err = by_store.get(mod.STORE_NAME, ([], None))
        if err:
            app.logger.warning("provider %s: %s", mod.STORE_NAME, err)
        results.extend(res)
    return results


def _run_search_job(job_id, item, zip_code):
    try:
        by_store = engine.run(engine.search_all(item, zip_code, PROVIDERS))
        results = _collect(by_store)
        _finish_job(job_id, {"item": item, "zip": zip_code,
                             "results": results,
                             "winner": pick_winner(results),
                             "statuses": provider_statuses(),
                             "checked_at": utc_now_iso()})
    except Exception as e:
        _fail_job(job_id, e)


def _run_list_job(job_id, items, zip_code):
    try:
        per_item, totals = [], {}
        for item in items:
            by_store = engine.run(engine.search_all(item, zip_code,
                                                    PROVIDERS))
            results = _collect(by_store)
            winner = pick_winner(results)
            per_item.append({"item": item, "results": results,
                             "winner": winner})
            if winner:
                totals[winner["store"]] = totals.get(winner["store"], 0.0) \
                    + winner["price"]
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["progress"] = \
                        "%d of %d items" % (len(per_item), len(items))
        _finish_job(job_id, {"zip": zip_code, "items": per_item,
                             "totals": totals,
                             "statuses": provider_statuses(),
                             "checked_at": utc_now_iso()})
    except Exception as e:
        _fail_job(job_id, e)


def _run_sales_job(job_id, zip_code):
    try:
        by_store = engine.run(engine.sales_all(zip_code, PROVIDERS))
        sales = {mod.STORE_NAME: by_store.get(mod.STORE_NAME,
                                              ([], None))[0]
                 for mod in PROVIDERS}
        _finish_job(job_id, {"zip": zip_code, "sales": sales,
                             "statuses": provider_statuses(),
                             "checked_at": utc_now_iso()})
    except Exception as e:
        _fail_job(job_id, e)


@app.route("/api/job/<job_id>")
def api_job(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job."}), 404
    return jsonify(dict(job))


@app.route("/api/status")
def api_status():
    return jsonify({"statuses": provider_statuses(),
                    "checked_at": utc_now_iso()})


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True, silent=True) or {}
    item = (data.get("item") or "").strip()
    zip_code = (data.get("zip") or DEFAULT_ZIP).strip() or DEFAULT_ZIP
    if not item:
        return jsonify({"error": "Type an item to search."}), 400
    job_id = _new_job("search", item)
    threading.Thread(target=_run_search_job, args=(job_id, item, zip_code),
                     daemon=True).start()
    return jsonify({"job_id": job_id, "status": "pending"})


@app.route("/api/compare-list", methods=["POST"])
def api_compare_list():
    data = request.get_json(force=True, silent=True) or {}
    raw_items = data.get("items") or []
    zip_code = (data.get("zip") or DEFAULT_ZIP).strip() or DEFAULT_ZIP
    items = [str(i).strip() for i in raw_items if str(i).strip()]
    if not items:
        return jsonify({"error": "Your list is empty."}), 400

    job_id = _new_job("compare-list", "%d items" % len(items))
    threading.Thread(target=_run_list_job,
                     args=(job_id, items, zip_code),
                     daemon=True).start()
    return jsonify({"job_id": job_id, "status": "pending"})


@app.route("/api/sales", methods=["GET", "POST"])
def api_sales():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
    else:
        data = request.args
    zip_code = (data.get("zip") or DEFAULT_ZIP).strip() or DEFAULT_ZIP
    job_id = _new_job("sales", "weekly sales")
    threading.Thread(target=_run_sales_job, args=(job_id, zip_code),
                     daemon=True).start()
    return jsonify({"job_id": job_id, "status": "pending"})


# ------------------------------------------------------------------ UI ----

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Grocery Compare</title>
<style>
  :root { --green:#1a7f37; --red:#c0392b; --ink:#1c1c1e; --mut:#6b7280;
          --line:#e5e7eb; --bg:#f6f7f9; --card:#ffffff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
         background:var(--bg); color:var(--ink); }
  header { background:var(--green); color:#fff; padding:14px 16px; position:sticky; top:0; z-index:5; }
  header h1 { margin:0; font-size:20px; }
  header .sub { font-size:12px; opacity:.9; margin-top:2px; }
  .ziprow { display:flex; gap:8px; align-items:center; margin-top:10px; }
  .ziprow label { font-size:13px; }
  .ziprow input { width:90px; padding:8px; border:none; border-radius:8px; font-size:15px; }
  nav.tabs { display:flex; background:#fff; border-bottom:1px solid var(--line);
              position:sticky; top:0; z-index:4; }
  nav.tabs button { flex:1; padding:13px 4px; border:none; background:#fff;
                    font-size:15px; color:var(--mut); border-bottom:3px solid transparent; }
  nav.tabs button.active { color:var(--green); border-bottom-color:var(--green); font-weight:700; }
  main { padding:14px 14px 40px; max-width:720px; margin:0 auto; }
  .tab { display:none; } .tab.active { display:block; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:14px; margin-bottom:12px; }
  .row { display:flex; gap:8px; }
  input[type=text], textarea { width:100%; padding:11px; font-size:16px; border:1px solid var(--line);
                               border-radius:10px; }
  textarea { min-height:90px; font-family:inherit; resize:vertical; }
  button.go { background:var(--green); color:#fff; border:none; border-radius:10px;
              padding:11px 18px; font-size:16px; font-weight:600; white-space:nowrap; }
  button.go:disabled { opacity:.5; }
  button.ghost { background:#eef0f2; color:var(--ink); border:none; border-radius:10px;
                 padding:9px 14px; font-size:14px; }
  table { width:100%; border-collapse:collapse; font-size:14px; margin-top:10px; }
  th, td { text-align:left; padding:9px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { font-size:12px; text-transform:uppercase; color:var(--mut); }
  tr.winner td { background:#e9f7ee; }
  tr.winner td:first-child { border-left:4px solid var(--green); }
  .badge { display:inline-block; font-size:11px; font-weight:700; padding:2px 8px; border-radius:20px; }
  .badge.win { background:var(--green); color:#fff; }
  .badge.sale { background:var(--red); color:#fff; margin-left:6px; }
  .badge.stub { background:#eef0f2; color:var(--mut); }
  .addr { font-size:11px; color:var(--mut); margin-top:2px; }
  .badge.live { background:#dbeafe; color:#1d4ed8; }
  .badge.blocked { background:#fee2e2; color:#991b1b; }
  .price { font-weight:700; font-size:16px; white-space:nowrap; }
  .unit { font-size:12px; color:var(--mut); }
  .meta { font-size:12px; color:var(--mut); margin-top:8px; }
  a.prod { color:#1d4ed8; font-size:13px; }
  ul.picklist { list-style:none; margin:10px 0 0; padding:0; }
  ul.picklist li { display:flex; justify-content:space-between; align-items:center;
                   padding:9px 2px; border-bottom:1px solid var(--line); font-size:15px; }
  ul.picklist li button { background:none; border:none; color:var(--red); font-size:18px; }
  .totals td:last-child, .totals th:last-child { text-align:right; }
  .empty { color:var(--mut); font-size:14px; padding:8px 0; }
  .storename { font-weight:700; font-size:16px; margin:0 0 4px; }
  .spin { text-align:center; color:var(--mut); padding:16px; }
  .err { background:#fee2e2; color:#991b1b; border-radius:10px; padding:10px; margin-top:10px; font-size:14px; }
  .hint { font-size:13px; color:var(--mut); margin-top:8px; }
</style>
</head>
<body>
<header>
  <h1>&#x1F6D2; Grocery Compare</h1>
  <div class="sub">Aldi &middot; Kroger &middot; Meijer &middot; Walmart</div>
  <div class="ziprow">
    <label for="zip">ZIP</label>
    <input id="zip" inputmode="numeric" maxlength="10" value="43228">
    <span class="sub" id="statusline"></span>
  </div>
</header>
<nav class="tabs">
  <button class="active" data-tab="search">&#x1F50D; Search</button>
  <button data-tab="list">&#x1F6D2; My List</button>
  <button data-tab="sales">&#x1F3F7;&#xFE0F; Sales</button>
</nav>
<main>
  <section class="tab active" id="tab-search">
    <div class="card">
      <div class="row">
        <input type="text" id="q" placeholder="e.g. whole milk gallon" enterkeyhint="search">
        <button class="go" id="searchBtn">Go</button>
      </div>
      <div class="hint">Compares the item across all four stores on demand.</div>
    </div>
    <div id="searchOut"></div>
  </section>

  <section class="tab" id="tab-list">
    <div class="card">
      <div class="row">
        <input type="text" id="newItem" placeholder="Add an item, e.g. eggs dozen" enterkeyhint="done">
        <button class="go" id="addBtn">Add</button>
      </div>
      <ul class="picklist" id="listUl"></ul>
      <div class="row" style="margin-top:10px">
        <button class="ghost" id="clearBtn">Clear list</button>
        <button class="go" id="compareBtn" style="margin-left:auto">Compare list</button>
      </div>
    </div>
    <div class="card">
      <b>Bulk import</b>
      <div class="hint" style="margin:4px 0 8px">Paste one item per line &mdash; works great with a list copied from Alexa.</div>
      <textarea id="bulk" placeholder="milk&#10;eggs&#10;bread"></textarea>
      <div class="row" style="margin-top:10px">
        <button class="ghost" id="importBtn">Import lines</button>
      </div>
    </div>
    <div id="listOut"></div>
  </section>

  <section class="tab" id="tab-sales">
    <div class="card">
      <b>This week's sales</b>
      <div class="hint" style="margin-top:4px">The best deals worth your time at each store.</div>
    </div>
    <div id="salesOut"><div class="spin">Loading&hellip;</div></div>
  </section>
</main>

<script>
const $ = id => document.getElementById(id);
const zip = () => ($("zip").value.trim() || "43228");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = p => (typeof p === "number") ? "$" + p.toFixed(2) : "&mdash;";

let statuses = [];
async function loadStatus() {
  try {
    const r = await fetch("/api/status");
    const j = await r.json();
    statuses = j.statuses || [];
    const live = statuses.filter(s => s.status === "live").length;
    $("statusline").textContent = live
      ? live + " of " + statuses.length + " stores live"
      : "providers connecting";
  } catch (e) { $("statusline").textContent = ""; }
}
function statusBadge(store) {
  const s = statuses.find(x => x.store === store);
  if (!s) return "";
  return ` <span class="badge ${esc(s.status)}">${esc(s.status)}</span>`;
}

document.querySelectorAll("nav.tabs button").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs button").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    $("tab-" + b.dataset.tab).classList.add("active");
    if (b.dataset.tab === "sales") loadSales();
  });
});

function resultRows(results, winner) {
  if (!results.length)
    return `<div class="empty">No prices found yet for this item. Provider integrations are still being connected &mdash; nothing is made up here.</div>`;
  const wkey = winner ? winner.store + "|" + winner.name : "";
  let h = `<table><tr><th>Store</th><th>Item</th><th>Price</th></tr>`;
  for (const r of results) {
    const isW = (r.store + "|" + r.name) === wkey;
    const st = statuses.find(x => x.store === r.store);
    const addr = st && st.address ? `<div class="addr">${esc(st.address)}</div>` : "";
    h += `<tr class="${isW ? "winner" : ""}">`;
    h += `<td><b>${esc(r.store)}</b>${addr}${isW ? ' <span class="badge win">cheapest</span>' : ""}${r.sale ? ' <span class="badge sale">sale</span>' : ""}</td>`;
    h += `<td>${esc(r.name)}${r.unit_price ? `<div class="unit">${esc(r.unit_price)}</div>` : ""}`
      + (r.url ? `<div><a class="prod" href="${esc(r.url)}" target="_blank" rel="noopener">view product &nearr;</a></div>` : "") + `</td>`;
    h += `<td class="price">${money(r.price)}</td></tr>`;
  }
  return h + "</table>";
}
const checkedLine = (ts, z) =>
  `<div class="meta">Checked ${esc(new Date(ts).toLocaleString())} &middot; ZIP ${esc(z)}</div>`;

async function doSearch() {
  const q = $("q").value.trim();
  if (!q) return;
  const btn = $("searchBtn"); btn.disabled = true;
  $("searchOut").innerHTML = `<div class="card"><div class="spin">Checking stores&hellip; (first check can take ~1 min)</div></div>`;
  try {
    const r = await fetch("/api/search", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({item: q, zip: zip()})});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Search failed");
    const done = await pollJob(j.job_id);
    $("searchOut").innerHTML =
      `<div class="card"><div class="storename">${esc(done.item)}</div>`
      + resultRows(done.results, done.winner) + checkedLine(done.checked_at, done.zip) + `</div>`;
  } catch (e) {
    $("searchOut").innerHTML = `<div class="err">${esc(e.message)}</div>`;
  }
  btn.disabled = false;
}

async function pollJob(job_id) {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const r = await fetch("/api/job/" + job_id);
    const j = await r.json();
    if (j.status === "done") return j;
    if (j.status === "error") throw new Error(j.error || "Check failed");
  }
  throw new Error("Timed out waiting for results — try again.");
}

async function pollJobProgress(job_id) {
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const r = await fetch("/api/job/" + job_id);
    const j = await r.json();
    if (j.progress) {
      const el = $("progHint");
      if (el) el.textContent = j.progress;
    }
    if (j.status === "done") return j;
    if (j.status === "error") throw new Error(j.error || "Compare failed");
  }
  throw new Error("Timed out waiting for results — try again.");
}
$("searchBtn").addEventListener("click", doSearch);
$("q").addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });

/* ---------------- shopping list ---------------- */
let myList = [];
function renderList() {
  const ul = $("listUl");
  ul.innerHTML = myList.length
    ? myList.map((it, i) =>
        `<li><span>${esc(it)}</span><button data-i="${i}" aria-label="remove">&times;</button></li>`).join("")
    : `<li style="color:var(--mut)">Nothing here yet &mdash; add items above or bulk-import below.</li>`;
  ul.querySelectorAll("button").forEach(b =>
    b.addEventListener("click", () => { myList.splice(+b.dataset.i, 1); renderList(); }));
}
function addItem(v) {
  v = (v || "").trim();
  if (v && !myList.includes(v)) { myList.push(v); renderList(); }
}
$("addBtn").addEventListener("click", () => { addItem($("newItem").value); $("newItem").value = ""; $("newItem").focus(); });
$("newItem").addEventListener("keydown", e => { if (e.key === "Enter") { addItem($("newItem").value); $("newItem").value = ""; } });
$("clearBtn").addEventListener("click", () => { myList = []; renderList(); $("listOut").innerHTML = ""; });
$("importBtn").addEventListener("click", () => {
  $("bulk").value.split("\\n").forEach(line => addItem(line));
  $("bulk").value = "";
});

async function compareList() {
  if (!myList.length) { $("listOut").innerHTML = `<div class="err">Add some items first.</div>`; return; }
  const btn = $("compareBtn"); btn.disabled = true;
  $("listOut").innerHTML = `<div class="card"><div class="spin">Comparing ${myList.length} items across 4 stores&hellip;<div class="hint" id="progHint"></div></div></div>`;
  try {
    const r = await fetch("/api/compare-list", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({items: myList, zip: zip()})});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Compare failed");
    const done = await pollJobProgress(j.job_id);
    let h = "";
    for (const it of done.items) {
      h += `<div class="card"><div class="storename">${esc(it.item)}`
        + (it.winner ? ` <span class="badge win">${esc(it.winner.store)} ${money(it.winner.price)}</span>` : "") + `</div>`
        + resultRows(it.results, it.winner) + `</div>`;
    }
    const stores = Object.keys(done.totals);
    if (stores.length) {
      const best = stores.reduce((a, b) => done.totals[a] <= done.totals[b] ? a : b);
      h += `<div class="card"><div class="storename">Estimated basket totals</div>`
        + `<table class="totals"><tr><th>Store</th><th>Winner items</th></tr>`
        + stores.sort((a, b) => done.totals[a] - done.totals[b]).map(s =>
            `<tr class="${s === best ? "winner" : ""}"><td><b>${esc(s)}</b>`
            + (s === best ? ' <span class="badge win">cheapest basket</span>' : "")
            + `</td><td>${money(done.totals[s])}</td></tr>`).join("")
        + `</table><div class="hint">Totals add up each item's cheapest price at that store. Items with no price found are skipped.</div></div>`;
    } else {
      h += `<div class="card"><div class="empty">No prices found for any item yet &mdash; provider integrations are still being connected.</div></div>`;
    }
    h += checkedLine(done.checked_at, done.zip);
    $("listOut").innerHTML = h;
  } catch (e) {
    $("listOut").innerHTML = `<div class="err">${esc(e.message)}</div>`;
  }
  btn.disabled = false;
}
$("compareBtn").addEventListener("click", compareList);

/* ---------------- sales ---------------- */
async function loadSales() {
  $("salesOut").innerHTML = `<div class="spin">Loading this week's sales&hellip;</div>`;
  try {
    const r = await fetch("/api/sales", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({zip: zip()})});
    const j = await r.json();
    const done = await pollJob(j.job_id);
    let h = "";
    for (const [store, items] of Object.entries(done.sales)) {
      const st = statuses.find(x => x.store === store);
      const addr = st && st.address ? `<div class="addr">${esc(st.address)}</div>` : "";
      h += `<div class="card"><div class="storename">${esc(store)}${statusBadge(store)}${addr}</div>`;
      if (!items.length) {
        h += `<div class="empty">No sale data yet &mdash; this provider is still being connected.</div>`;
      } else {
        h += `<table><tr><th>Item</th><th>Was</th><th>Sale</th></tr>` + items.map(s =>
          `<tr><td>${esc(s.name)}` + (s.url ? `<div><a class="prod" href="${esc(s.url)}" target="_blank" rel="noopener">view &nearr;</a></div>` : "") + `</td>`
          + `<td>${money(s.price)}</td><td class="price" style="color:var(--red)">${money(s.sale_price)}</td></tr>`
        ).join("") + `</table>`;
      }
      h += `</div>`;
    }
    h += checkedLine(done.checked_at, done.zip);
    $("salesOut").innerHTML = h;
  } catch (e) {
    $("salesOut").innerHTML = `<div class="err">${esc(e.message)}</div>`;
  }
}

loadStatus();
renderList();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 5000)))
