#!/usr/bin/env python3
"""Thrift Addict - the ultimate thrift store companion for Columbus OH 43228.
Stores, deal calendar, flip finder, antique hunter, profit tracker, run planner."""
import csv
import io
import os
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, request, redirect, url_for, Response, g

app = Flask(__name__)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thrift.db")
NTFY_TOPIC = "thrift-deals-43228-a91c4e"

# ---------------------------------------------------------------- data ----

STORES = [
    dict(name="Volunteers of America Thrift Store", addr="5640 W Broad St, Columbus, OH 43228",
         phone="(614) 870-8444", hours="Mon-Sat 8AM-8PM, Sun 11AM-6PM", rating="3.6-3.9", dist="1.5 mi", chain="VOA"),
    dict(name="Salvation Army Thrift Store", addr="420 Georgesville Rd, Columbus, OH 43228",
         phone="(614) 274-4550", hours="Call ahead - hours unverified", rating="-", dist="1.3 mi", chain="Salvation Army", unverified=True),
    dict(name="Ohio Thrift", addr="4340 W Broad St, Columbus, OH",
         phone="(614) 275-4196", hours="Mon-Sat 9AM-9PM, Sun 10AM-8PM", rating="4.1", dist="1.6 mi", chain="Ohio Thrift"),
    dict(name="Goodwill", addr="5526 Renner Rd, Columbus, OH 43228",
         phone="(614) 971-4000", hours="Mon-Sat 9AM-9PM, Sun 10AM-6PM", rating="3.2-3.9", dist="3.4 mi", chain="Goodwill"),
    dict(name="Uptown Cheapskate (Hilliard)", addr="5303 Westpointe Plaza Dr, Columbus, OH 43228",
         phone="Call ahead - unverified", hours="Resale chain, typically Mon-Sat 10-8", rating="5.0", dist="3.4 mi", chain="Resale", unverified=True),
    dict(name="Ohio Thrift", addr="647 Harrisburg Pike, Columbus, OH",
         phone="(614) 272-6281", hours="Mon-Sat 9AM-9PM, Sun 10AM-8PM", rating="4.5", dist="5.1 mi", chain="Ohio Thrift"),
    dict(name="Volunteers of America (Grove City)", addr="4026 McDowell Rd, Grove City, OH",
         phone="(614) 801-1625", hours="Mon-Sat 8AM-8PM, Sun 11AM-6PM", rating="5.0", dist="5.4 mi", chain="VOA"),
    dict(name="Grandview Mercantile (antique mall)", addr="1489 Grandview Ave, Columbus, OH 43212",
         phone="(614) 421-7000", hours="Antique mall, typically daily 10-6 (verify)", rating="-", dist="5.9 mi", chain="Antique Mall", unverified=True),
    dict(name="One More Time (consignment)", addr="1521 W 5th Ave, Columbus, OH 43212",
         phone="Call ahead - unverified", hours="Hours unverified", rating="4.6", dist="5.9 mi", chain="Consignment", unverified=True),
    dict(name="Salvation Army", addr="1675 S High St, Columbus, OH 43207",
         phone="(614) 221-4269", hours="Mon-Sat 10AM-6PM, Sun closed", rating="3.8", dist="7.3 mi", chain="Salvation Army"),
    dict(name="Volunteers of America (S High)", addr="1776 S High St, Columbus, OH 43207",
         phone="Call ahead - unverified", hours="Chain standard: Mon-Sat 8AM-8PM, Sun 11AM-6PM (verify)", rating="-", dist="7.3 mi", chain="VOA", unverified=True),
    dict(name="Out of the Closet (nonprofit thrift)", addr="1230 N High St, Columbus, OH 43201",
         phone="(614) 291-2680", hours="Hours unverified", rating="-", dist="7.7 mi", chain="Nonprofit", unverified=True),
    dict(name="Goodwill", addr="2550 N High St, Columbus, OH 43202",
         phone="(614) 384-9768", hours="Mon-Sat 9AM-9PM, Sun 10AM-6PM", rating="3.2-3.9", dist="8.5 mi", chain="Goodwill"),
    dict(name="Volunteers of America (W Henderson)", addr="1800 W Henderson Rd, Columbus, OH 43220",
         phone="Call ahead - unverified", hours="Chain standard (verify)", rating="-", dist="9.1 mi", chain="VOA", unverified=True),
    dict(name="Volunteers of America (Indianola)", addr="3620 Indianola Ave, Columbus, OH 43214",
         phone="(614) 263-9134", hours="Mon-Sat 8AM-8PM, Sun 11AM-6PM", rating="-", dist="10.0 mi", chain="VOA"),
    dict(name="Volunteers of America (E Broad)", addr="3583 E Broad St, Columbus, OH 43213",
         phone="(614) 618-9950", hours="Chain standard (verify)", rating="-", dist="12.4 mi", chain="VOA", unverified=True),
    dict(name="Goodwill", addr="2933 Morse Rd, Columbus, OH 43231",
         phone="(614) 414-0441", hours="Chain standard (verify)", rating="3.2", dist="13.2 mi", chain="Goodwill", unverified=True),
    dict(name="Salvation Army", addr="4242 Macsway Ave, Columbus, OH 43232",
         phone="(800) 728-7825", hours="Mon-Sat 10AM-7PM, Sun closed (verify)", rating="-", dist="13.3 mi", chain="Salvation Army", unverified=True),
    dict(name="Ohio Thrift", addr="4618 E Broad St, Columbus, OH 43213",
         phone="Call ahead - unverified", hours="Chain standard (verify)", rating="-", dist="13.9 mi", chain="Ohio Thrift", unverified=True),
    dict(name="Ohio Thrift", addr="5738 Columbus Sq, Columbus, OH 43231",
         phone="Call ahead - unverified", hours="Chain standard (verify)", rating="-", dist="14.3 mi", chain="Ohio Thrift", unverified=True),
    dict(name="Village Discount Outlet", addr="109 Huber Village Blvd, Westerville, OH 43081",
         phone="(614) 443-3421", hours="Mon-Sat 9AM-8PM, Sun 11AM-6PM", rating="3.7-4.1", dist="16.1 mi", chain="Bonus",
         bonus="Ohio's largest thrift store. Restocks 3,000+ pieces daily. Two color tags on sale every day: Sun $1.00, Mon $0.75, Tue $0.50."),
    dict(name="Goodwill Outlet (the bins)", addr="2675 Brice Rd, Columbus, OH 43232",
         phone="Call before going - hours unverified", hours="Pay-by-the-pound bins", rating="-", dist="15.8 mi", chain="Bonus",
         bonus="The #1 flip-sourcing spot in Columbus. Dig through bins, pay by the pound.", unverified=True),
    dict(name="Uptown Cheapskate (Dublin)", addr="2705 Federated Blvd, Columbus, OH 43235",
         phone="Call ahead - unverified", hours="Buy/sell/trade resale", rating="-", dist="11.7 mi", chain="Bonus",
         bonus="Buy/sell/trade resale shop. Good for flipping clothes same-day.", unverified=True),
]

DEAL_DAYS = [
    ("TUESDAY - POWER DAY", "Goodwill's new 50%-off color starts + Senior Day (55+) + Village Discount $0.50 tag day. The single best thrifting day of the week."),
    ("WEDNESDAY", "Salvation Army half-price day (most commonly reported - verify at your store)."),
    ("LAST TUESDAY OF THE MONTH", "Volunteers of America: ENTIRE STORE 50% off. Plan furniture and big-item runs around this."),
    ("SUNDAY", "Village Discount $1.00 tag day. Goodwill weekly color-tag sales run Sun-Mon."),
    ("MONDAY", "Village Discount $0.75 tag day. Fresh weekend donations hitting floors."),
    ("WEEKDAY MORNINGS", "Fresh restocks, first pick, no crowds. The flipper's window. Weekends are picked-over with long lines."),
]

CHAIN_DEALS = [
    ("Goodwill of Central Ohio",
     "Color of the Week: 50% off the designated tag color, changes every TUESDAY. Reported rotation: Lavender / Green / Orange / Blue / Yellow - VERIFY IN STORE, ask at the register. Weekly color-tag sales run Sundays and Mondays. Senior Day every Tuesday (55+). Good Points Plus loyalty program earns points per dollar."),
    ("Ohio Thrift",
     "Rotating color-tag system with 50-75% off select tag colors weekly, plus daily tag deals. No fixed weekday schedule verified - check their website/social or call (614) 714-2444 before a dedicated trip."),
    ("Salvation Army",
     "Wednesday half-price day is the most commonly reported pattern (half off clothing; some stores half off everything except furniture). Also two tag colors at 50% off every day (reported). Schedules vary - verify at your store."),
    ("Volunteers of America",
     "LAST TUESDAY of every month: entire store 50% off (confirmed by multiple Columbus shopper reviews). About 3 tag colors on sale weekly on an ongoing basis. Loyalty card available for extra savings."),
    ("Village Discount Outlet",
     "Two color tags on sale every day: Sunday $1.00, Monday $0.75, Tuesday $0.50. Extra discounts for seniors, college students, and military. Restocks 3,000+ pieces daily - go early."),
]

FLIPS = [
    dict(name="Vintage Levi's (501/505/517)", look="Made in USA tag, orange tab, selvedge edge, 36in+ waist commands premium. 80s-90s era.",
         buy="$4-8", sell="$40-100", where="Depop / eBay / Poshmark"),
    dict(name="Carhartt Work Jackets", look="Detroit jacket or blanket-lined. Quilted/blanket-stripe lining, brass zippers, worn-but-solid canvas.",
         buy="$6-12", sell="$60-120", where="eBay / Depop"),
    dict(name="Lululemon Activewear", look="Size dot hidden in pocket verifies the authentic style name. Define jackets and Align leggings sell fastest.",
         buy="$4-8", sell="$30-60", where="Poshmark / Mercari"),
    dict(name="Patagonia / North Face Outerwear", look="Fleece, down, Gore-Tex shells. Retro colorways carry a premium.",
         buy="$8-15", sell="$50-120", where="eBay / Poshmark"),
    dict(name="Vintage Band / Concert Tees", look="Single-stitch hems, faded prints, 80s-90s tour dates. The older and more obscure the band, the better.",
         buy="$3-6", sell="$25-100+", where="eBay / Depop"),
    dict(name="Vintage Pyrex", look="Check the backstamp on the bottom. Gooseberry, Butterprint, Pink Daisy patterns. Rare patterns hit the hundreds.",
         buy="$2-5", sell="$15-40 (rare: $100s+)", where="eBay / Mercari"),
    dict(name="Fiestaware (Homer Laughlin)", look="Fiesta backstamp. Retired colors like lilac and chartreuse. Disc pitchers are the prize.",
         buy="$1-4/pc", sell="$10-30/pc (sets: $60-150+)", where="eBay"),
    dict(name="Mid-Century Barware", look="Culver or Georges Briard. 22k gold-leaf patterns, maker signature on the base.",
         buy="$1-3/pc", sell="$8-25/pc (sets: $60-150)", where="eBay / Etsy"),
    dict(name="Cast Iron (Griswold, Wagner, Le Creuset)", look="Brand mark on the bottom, smooth machined interior, no cracks or wobble.",
         buy="$5-15", sell="$40-150", where="eBay / Mercari"),
    dict(name="Current-Edition Textbooks", look="SCAN THE ISBN. Value is 100% edition-dependent. One edition old is nearly worthless.",
         buy="$1-5", sell="$30-90", where="Amazon / eBay"),
    dict(name="First-Edition / Collectible Books", look="'First Edition / First Printing' stated on the copyright page, intact dust jacket. Verify with sold comps.",
         buy="$1-3", sell="$20-200+", where="eBay"),
    dict(name="Y2K Retro Tech", look="Canon PowerShot cameras, iPods, Walkmans. Must power on; battery/charger included doubles value.",
         buy="$3-8", sell="$50-150+", where="eBay / Mercari"),
    dict(name="Complete LEGO Sets / Board Games", look="Sealed or 100% complete with the manual. Retired sets only.",
         buy="$2-5", sell="$25-80+", where="eBay"),
    dict(name="Vintage Leather & Denim Jackets", look="Real leather: Schott, Wilson, shearling. Vintage Levi's denim truckers.",
         buy="$6-10", sell="$35-120", where="Depop / Poshmark"),
]

ANTIQUES = [
    ("Sterling Silver (not plated)",
     "Look for: 'sterling', '925', or the British lion passant mark. Weight matters - heavy pieces are rarely plated. Fake tell: 'EPNS' or 'silverplate' marks, or magnetic (silver is not magnetic). A $3 tray can be $200+ in melt alone.",
     "ebay_sold", "sterling silver tray"),
    ("Original Oil Paintings",
     "Look for: signature, visible canvas texture and brushwork at the edges (prints are flat), old wood stretchers. Google the artist name on the spot - listed artists sell. Fake tell: perfectly uniform surface, 'made in China' stickers, mass-produced hotel art.",
     "ebay_sold", "original oil painting signed"),
    ("Hand-Knotted Persian / Oriental Rugs",
     "Look for: flip it over - hand-knotted rugs show the pattern clearly in individual knots on the back; machine-made have a stiff uniform backing. Wool and silk beat synthetics. Even worn ones sell.",
     "ebay_sold", "hand knotted persian rug"),
    ("Mid-Century Modern Furniture",
     "Look for: Herman Miller, Eames, Knoll, Danish teak makers' stamps or labels underneath. Dovetail joints, solid wood. Fake tell: 'mid-century style' new reproductions - check for modern screws and particle board.",
     "ebay_sold", "mid century modern teak credenza"),
    ("Art Deco Bronze & Lalique Glass",
     "Look for: bronze statues with foundry marks, Lalique's etched signature on glass. Weight and patina are hard to fake. Ivory-look pieces: check if real ivory (legal issues) vs celluloid.",
     "ebay_sold", "lalique glass vase"),
    ("Fine Porcelain (Meissen, Herend, KPM)",
     "Look for: crossed-swords (Meissen), Herend, or KPM backstamps. Hand-painted beats transfer prints - look for brush variation. Fake tell: blurry or off-center marks, too-perfect glaze.",
     "ebay_sold", "meissen porcelain figurine"),
    ("Vintage Watches",
     "Look for: Rolex, Omega, Patek Philippe, even Longines and Hamilton. Check the movement, not just the face - fakes have cheap quartz ticks. A non-working luxury watch still sells for parts.",
     "ebay_sold", "vintage omega watch"),
    ("Gold Jewelry",
     "Look for: '14k', '18k', '585', '750' stamps inside bands and clasps. Test with a magnet (gold is not magnetic) and check weight. Costume jewelry marked '1/20 14k GF' is gold-filled, worth far less.",
     "ebay_sold", "14k gold ring vintage"),
]

# ---------------------------------------------------------------- helpers ---

def db():
    g.db = getattr(g, "db", None)
    if g.db is None:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    d = sqlite3.connect(DB)
    d.execute("""CREATE TABLE IF NOT EXISTS flips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL, buy_cost REAL NOT NULL DEFAULT 0,
        sell_price REAL, sold_where TEXT DEFAULT '', notes TEXT DEFAULT '',
        created_at TEXT NOT NULL)""")
    d.commit()
    d.close()

@app.teardown_appcontext
def close_db(exc):
    d = getattr(g, "db", None)
    if d is not None:
        d.close()

def ebay_sold_url(q):
    return "https://www.ebay.com/sch/i.html?_nkw=" + urllib.parse.quote_plus(q) + "&_sop=12&LH_Sold=1&LH_Complete=1"

def money(v):
    return "$%.2f" % v if v is not None else "-"

# ---------------------------------------------------------------- layout ---

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#faf6ef;color:#2b2118;max-width:640px;margin:0 auto;padding-bottom:90px}
header{background:linear-gradient(135deg,#7c4a1e,#b06a28);color:#fff;padding:22px 18px 18px;text-align:center}
header h1{font-size:26px;letter-spacing:1px}
header p{font-size:13px;opacity:.9;margin-top:4px}
nav{position:fixed;bottom:0;left:0;right:0;background:#2b2118;display:flex;max-width:640px;margin:0 auto;z-index:10}
nav a{flex:1;text-align:center;color:#e8dcc8;text-decoration:none;font-size:11px;padding:10px 2px 12px}
nav a .ico{font-size:20px;display:block;margin-bottom:2px}
nav a.active{color:#ffcf6e}
main{padding:14px}
.card{background:#fff;border-radius:14px;padding:14px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);border:1px solid #ead9bd}
.card h3{font-size:16px;margin-bottom:6px;color:#7c4a1e}
.card .meta{font-size:12.5px;color:#6b5a44;line-height:1.55}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin:2px 4px 2px 0}
.b-green{background:#dff5e1;color:#1e6b2a}.b-amber{background:#fdeecd;color:#8a5a00}.b-red{background:#fde2e2;color:#a02020}.b-blue{background:#e2eefe;color:#1d4fa0}
.btn{display:inline-block;background:#b06a28;color:#fff;text-decoration:none;padding:12px 18px;border-radius:12px;font-weight:700;font-size:15px;border:none;cursor:pointer;width:100%;text-align:center;margin-top:8px}
.btn-sec{background:#fff;color:#7c4a1e;border:2px solid #b06a28}
input,select,textarea{width:100%;padding:12px;border-radius:10px;border:1.5px solid #d8c49c;font-size:15px;margin:6px 0;background:#fffdf8}
label{font-size:13px;font-weight:700;color:#7c4a1e}
.row2{display:flex;gap:8px}.row2>div{flex:1}
h2.sec{font-size:19px;color:#7c4a1e;margin:6px 0 12px}
.totals{display:flex;gap:8px;margin-bottom:12px}
.totals .t{flex:1;background:#2b2118;color:#ffcf6e;border-radius:12px;padding:10px;text-align:center}
.totals .t b{display:block;font-size:19px}.totals .t span{font-size:11px;opacity:.8}
table.flip{width:100%;font-size:13px;border-collapse:collapse}
table.flip td,table.flip th{padding:8px 6px;border-bottom:1px solid #ead9bd;text-align:left}
.del{background:none;border:none;color:#a02020;font-size:16px;cursor:pointer}
.day{background:#2b2118;color:#ffcf6e;border-radius:12px;padding:12px 14px;margin-bottom:10px}
.day b{font-size:14px;letter-spacing:.5px}.day p{font-size:13px;margin-top:4px;line-height:1.5;color:#f3e9d6}
.check{display:flex;gap:10px;align-items:flex-start;padding:10px 4px;border-bottom:1px solid #ead9bd;font-size:14px}
.check input{width:22px;height:22px;margin:2px 0;flex-shrink:0}
.hint{font-size:12px;color:#8a6f4d;background:#fdf3df;border-radius:10px;padding:10px 12px;margin:10px 0;line-height:1.5}
.searchbar{position:sticky;top:0;background:#faf6ef;padding:8px 0;z-index:5}
"""

BASE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thrift Addict</title><style>""" + CSS + """</style></head><body>
<header><h1>&#x1F6CD;&#xFE0F; THRIFT ADDICT</h1><p>Columbus OH &middot; 43228 &middot; 15-mile hunting ground</p></header>
<main>%%BODY%%</main>
<nav>
<a href="/" class="%%A_HOME%%"><span class="ico">&#x1F3E0;</span>Home</a>
<a href="/stores" class="%%A_STORES%%"><span class="ico">&#x1F3EA;</span>Stores</a>
<a href="/deals" class="%%A_DEALS%%"><span class="ico">&#x1F4C5;</span>Deals</a>
<a href="/flips" class="%%A_FLIPS%%"><span class="ico">&#x1F4B0;</span>Flips</a>
<a href="/antiques" class="%%A_ANTIQUES%%"><span class="ico">&#x1F3FA;</span>Antiques</a>
<a href="/tracker" class="%%A_TRACKER%%"><span class="ico">&#x1F4CA;</span>Tracker</a>
</nav></body></html>"""

def page(body, active=""):
    p = BASE.replace("%%BODY%%", body)
    for k in ["HOME", "STORES", "DEALS", "FLIPS", "ANTIQUES", "TRACKER"]:
        p = p.replace("%%A_%s%%" % k, "active" if k == active else "")
    return p

# ---------------------------------------------------------------- routes ----

@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/")
def home():
    return page("""
<h2 class="sec">Happy hunting, Misty &#x1F49B;</h2>
<div class="card"><h3>&#x1F3EA; 23 stores mapped</h3><div class="meta">Every thrift store within 15 miles of 43228, with hours, ratings, and distance.</div>
<a class="btn" href="/stores">Browse stores</a></div>
<div class="card"><h3>&#x1F4C5; Today: """ + datetime.now().strftime("%A") + """</h3><div class="meta">""" +
    ("<b>TUESDAY = POWER DAY.</b> New Goodwill 50%-off color, Senior Day, Village Discount $0.50 tags, and VOA may be half off (last Tuesday of month)." if datetime.now().weekday() == 1 else
     "<b>WEDNESDAY = Salvation Army half-price day</b> (verify at your store)." if datetime.now().weekday() == 2 else
     "Check the deal calendar for today's best plays.") + """</div>
<a class="btn" href="/deals">Deal calendar</a></div>
<div class="card"><h3>&#x1F4B0; Flip finder</h3><div class="meta">14 proven thrift-to-resale categories with buy/sell ranges and one-tap eBay sold-price checks.</div>
<a class="btn" href="/flips">Find flips</a></div>
<div class="card"><h3>&#x1F3FA; Antique hunter</h3><div class="meta">High-value antiques: what to look for, authentication tips, and how to spot fakes.</div>
<a class="btn" href="/antiques">Hunt antiques</a></div>
<div class="card"><h3>&#x1F4CA; Profit tracker</h3><div class="meta">Log every flip. Know exactly what you've made.</div>
<a class="btn" href="/tracker">Open tracker</a></div>
<div class="card"><h3>&#x1F695; Run planner</h3><div class="meta">Tap the stores for today's route and copy the plan.</div>
<a class="btn" href="/planner">Plan a run</a></div>
<div class="card"><h3>&#x1F514; Deal alerts</h3><div class="meta">Get a phone notification when a high-value antique deal pops up locally.</div>
<a class="btn" href="/alerts">Set up alerts</a></div>
""", "HOME")

@app.route("/stores")
def stores():
    q = request.args.get("q", "").lower()
    chain = request.args.get("chain", "")
    chains = sorted(set(s["chain"] for s in STORES))
    cards = []
    for s in STORES:
        if q and q not in (s["name"] + " " + s["addr"]).lower():
            continue
        if chain and s["chain"] != chain:
            continue
        badges = '<span class="badge b-blue">%s</span><span class="badge b-green">%s</span>' % (s["chain"], s["dist"])
        if s.get("unverified"):
            badges += '<span class="badge b-amber">call ahead</span>'
        if s["chain"] == "Bonus":
            badges += '<span class="badge b-red">worth the drive</span>'
        bonus = '<div class="hint">%s</div>' % s["bonus"] if s.get("bonus") else ""
        maps = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(s["addr"])
        cards.append("""<div class="card"><h3>%s</h3><div class="meta">%s<br>%s<br>%s &middot; rated %s</div>
        <div style="margin-top:6px">%s</div>%s
        <div class="row2"><div><a class="btn btn-sec" href="%s" target="_blank">Directions</a></div>
        <div><a class="btn btn-sec" href="tel:%s">Call</a></div></div></div>""" % (
            s["name"], s["addr"], s["phone"], s["hours"], s["rating"], badges, bonus, maps,
            "".join(c for c in s["phone"] if c.isdigit() or c == "+") if s["phone"][0] == "(" else "#"))
    opts = '<option value="">All chains</option>' + "".join(
        '<option value="%s"%s>%s</option>' % (c, " selected" if c == chain else "", c) for c in chains)
    return page("""
<h2 class="sec">Stores near 43228</h2>
<form method="get" action="/stores"><div class="searchbar">
<input type="search" name="q" placeholder="Search stores..." value="%s">
<select name="chain" onchange="this.form.submit()">%s</select>
</div></form>
<div class="hint">%d stores &middot; distances are straight-line from 43228 &middot; entries marked <b>call ahead</b> could not be verified online</div>
%s""" % (request.args.get("q", ""), opts, len(cards), "".join(cards) or "<div class='card'>No stores match.</div>"), "STORES")

@app.route("/deals")
def deals():
    days = "".join('<div class="day"><b>%s</b><p>%s</p></div>' % d for d in DEAL_DAYS)
    chains = "".join('<div class="card"><h3>%s</h3><div class="meta">%s</div></div>' % c for c in CHAIN_DEALS)
    return page("""
<h2 class="sec">Best days to go</h2>
%s
<h2 class="sec" style="margin-top:16px">Sale schedules by chain</h2>
%s
<div class="hint">Sale schedules come from shopper reports and chain sites - always confirm the current color/tag at the register. Schedules change.</div>
""" % (days, chains), "DEALS")

@app.route("/flips")
def flips():
    q = request.args.get("q", "")
    cards = []
    for f in FLIPS:
        if q and q.lower() not in f["name"].lower():
            continue
        cards.append("""<div class="card"><h3>%s</h3>
        <div class="meta"><b>Look for:</b> %s</div>
        <div style="margin:8px 0"><span class="badge b-amber">Thrift %s</span><span class="badge b-green">Resells %s</span></div>
        <div class="meta">Sell on: %s</div>
        <a class="btn btn-sec" href="%s" target="_blank">Check eBay sold prices</a></div>""" % (
            f["name"], f["look"], f["buy"], f["sell"], f["where"], ebay_sold_url(f["name"])))
    return page("""
<h2 class="sec">Flip finder</h2>
<form method="get" action="/flips"><div class="searchbar">
<div class="row2"><div><input type="search" name="q" placeholder="Comp-check anything..." value="%s"></div>
<div style="flex:0 0 110px"><button class="btn" type="submit" style="margin-top:6px">Check</button></div></div>
</div></form>
<div class="hint"><b>Golden rule:</b> check eBay <i>sold</i> listings (not asking prices) in the store before you buy. The buttons open sold listings sorted by newest.</div>
%s""" % (q, "".join(cards) or "<div class='card'>No matches - try the comp checker above.</div>"), "FLIPS")

@app.route("/antiques")
def antiques():
    cards = []
    for name, tips, _, q in ANTIQUES:
        cards.append("""<div class="card"><h3>%s</h3><div class="meta">%s</div>
        <a class="btn btn-sec" href="%s" target="_blank">Check eBay sold prices</a></div>""" % (name, tips, ebay_sold_url(q)))
    return page("""
<h2 class="sec">Antique hunter</h2>
<div class="hint">High-value antiques hide in thrift stores priced as junk. These are the categories worth learning. When in doubt: photograph the marks, check sold comps, and buy the weird thing nobody else looked at twice.</div>
%s""" % "".join(cards), "ANTIQUES")

@app.route("/tracker", methods=["GET", "POST"])
def tracker():
    d = db()
    if request.method == "POST":
        item = request.form.get("item", "").strip()
        if item:
            try:
                buy = float(request.form.get("buy", 0) or 0)
            except ValueError:
                buy = 0
            sp = request.form.get("sell", "").strip()
            try:
                sell = float(sp) if sp else None
            except ValueError:
                sell = None
            d.execute("INSERT INTO flips (item, buy_cost, sell_price, sold_where, notes, created_at) VALUES (?,?,?,?,?,?)",
                      (item, buy, sell, request.form.get("where", ""), request.form.get("notes", ""),
                       datetime.now().strftime("%Y-%m-%d %H:%M")))
            d.commit()
        return redirect(url_for("tracker"))
    rows = d.execute("SELECT * FROM flips ORDER BY id DESC").fetchall()
    spent = sum(r["buy_cost"] for r in rows)
    revenue = sum(r["sell_price"] for r in rows if r["sell_price"])
    profit = revenue - spent
    unsold = sum(1 for r in rows if not r["sell_price"])
    trs = []
    for r in rows:
        p = (r["sell_price"] - r["buy_cost"]) if r["sell_price"] else None
        trs.append("<tr><td><b>%s</b><br><span style='color:#8a6f4d'>%s &middot; %s</span></td><td>%s</td><td>%s</td>"
                   "<td style='color:%s;font-weight:700'>%s</td>"
                   "<td><form method='post' action='/tracker/delete/%d' onsubmit=\"return confirm('Delete this entry?')\">"
                   "<button class='del'>&#x2715;</button></form></td></tr>" % (
                       r["item"], r["sold_where"] or "not sold yet", r["created_at"][:10],
                       money(r["buy_cost"]), money(r["sell_price"]),
                       "#1e6b2a" if p and p > 0 else "#a02020" if p else "#8a6f4d",
                       money(p) if p is not None else "holding",
                       r["id"]))
    return page("""
<h2 class="sec">Profit tracker</h2>
<div class="totals">
<div class="t"><b>%s</b><span>PROFIT</span></div>
<div class="t"><b>%s</b><span>SPENT</span></div>
<div class="t"><b>%s</b><span>SOLD FOR</span></div>
<div class="t"><b>%d</b><span>UNSOLD</span></div>
</div>
<div class="card"><h3>Log a flip</h3>
<form method="post" action="/tracker">
<label>Item</label><input name="item" required placeholder="e.g. Pyrex Gooseberry bowl">
<div class="row2"><div><label>Paid ($)</label><input name="buy" type="number" step="0.01" min="0" value="0"></div>
<div><label>Sold for ($) - blank if holding</label><input name="sell" type="number" step="0.01" min="0" placeholder=""></div></div>
<label>Sold where</label><input name="where" placeholder="eBay, Mercari, Poshmark...">
<label>Notes</label><input name="notes" placeholder="Pattern, marks, condition...">
<button class="btn" type="submit">Add to tracker</button>
</form></div>
<div class="card"><h3>History</h3>
<table class="flip"><tr><th>Item</th><th>Paid</th><th>Sold</th><th>P/L</th><th></th></tr>%s</table>
<a class="btn btn-sec" href="/tracker/export">Download CSV</a></div>
""" % (money(profit), money(spent), money(revenue), unsold, "".join(trs) or "<tr><td colspan=5>No flips logged yet.</td></tr>"), "TRACKER")

@app.route("/tracker/delete/<int:fid>", methods=["POST"])
def tracker_delete(fid):
    d = db()
    d.execute("DELETE FROM flips WHERE id=?", (fid,))
    d.commit()
    return redirect(url_for("tracker"))

@app.route("/tracker/export")
def tracker_export():
    d = db()
    rows = d.execute("SELECT id,item,buy_cost,sell_price,sold_where,notes,created_at FROM flips ORDER BY id").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "item", "buy_cost", "sell_price", "sold_where", "notes", "created_at"])
    for r in rows:
        w.writerow(list(r))
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=thrift-flips.csv"})

@app.route("/planner")
def planner():
    items = []
    for i, s in enumerate(STORES):
        items.append("""<label class="check"><input type="checkbox" data-addr="%s">
        <span><b>%s</b><br><span style="color:#6b5a44;font-size:12.5px">%s &middot; %s</span></span></label>""" % (
            s["addr"], s["name"], s["dist"], s["hours"].split(",")[0]))
    return page("""
<h2 class="sec">Run planner</h2>
<div class="hint">Tap the stores for today's route, then copy the plan. Hit them in distance order for the most efficient loop.</div>
<div class="card">%s
<button class="btn" onclick="copyRoute()">Copy my route</button>
<div id="copied" style="text-align:center;color:#1e6b2a;font-weight:700;margin-top:8px;display:none">Copied!</div></div>
<script>
function copyRoute(){
  var stops=[];document.querySelectorAll('.check input:checked').forEach(function(c,i){
    stops.push((i+1)+'. '+c.parentElement.querySelector('b').textContent+' - '+c.dataset.addr);});
  if(!stops.length){alert('Pick at least one store first!');return;}
  navigator.clipboard.writeText("Today's thrift run:\\n"+stops.join('\\n')).then(function(){
    document.getElementById('copied').style.display='block';
    setTimeout(function(){document.getElementById('copied').style.display='none'},2000);});
}
</script>
""" % "".join(items), "")

@app.route("/alerts")
def alerts():
    return page("""
<h2 class="sec">Deal alerts</h2>
<div class="card"><h3>&#x1F514; How it works</h3>
<div class="meta">A watcher scans local listings for high-value antiques and sends a push notification to your phone when a deal worth your time pops up. No price cap - if it's a real find, you'll hear about it.</div></div>
<div class="card"><h3>Step 1 - install ntfy</h3>
<div class="meta">Install the <b>ntfy</b> app (free) from the App Store or Google Play.</div></div>
<div class="card"><h3>Step 2 - subscribe</h3>
<div class="meta">In ntfy tap <b>+</b> and subscribe to this topic:<br><br>
<b style="font-size:16px;color:#7c4a1e">""" + NTFY_TOPIC + """</b></div></div>
<div class="card"><h3>Step 3 - that's it</h3>
<div class="meta">Deal alerts land as high-priority notifications on your phone. Happy hunting.</div></div>
""", "")

# ---------------------------------------------------------------- main -----

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
else:
    init_db()
