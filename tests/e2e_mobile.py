"""Phone test of the LIVE site (iPhone 13, headless Chromium). Every filter is checked against the real data.

    pip install playwright && python -m playwright install chromium
    python tests/e2e_mobile.py <folder-for-screenshots>

Read-only: it never enters the PIN or saves anything.
"""
import re
import sys
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

URL = "https://ph-civil-job-finder.vercel.app/"
OUT = sys.argv[1]
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


MANILA = timezone(timedelta(hours=8))


def age_days(j, now):
    t = datetime.fromisoformat(j["posted_at"].replace("Z", "+00:00"))
    if j["posted_precision"] == "date":   # calendar days, Manila
        return (now.astimezone(MANILA).date() - t.date()).days
    return (now - t).total_seconds() / 86400


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(**p.devices["iPhone 13"], accept_downloads=True)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("dialog", lambda d: d.dismiss())   # never type a PIN / never write anything

    page.goto(URL)
    page.wait_for_selector("#list .card", timeout=30000)
    data = page.evaluate("fetch('api/jobs').then(r => r.json())")
    jobs = {j["dedupe_key"]: j for j in data["jobs"]}
    hidden = {j["dedupe_key"]: j for j in data["hidden"]}
    now = datetime.now(timezone.utc)
    page.screenshot(path=f"{OUT}/1_top.png")
    vh = page.viewport_size["height"]
    top = page.eval_on_selector("#list .card", "e => e.getBoundingClientRect().top")
    check("first job is visible on the opening screen (filters folded)", top < vh, f"card top {top:.0f}px, screen {vh}px")
    check("Role/Area/Platform rows folded away on the phone", not page.is_visible("#f-role"))
    page.click("#f-toggle")
    check("'More filters' opens the other filter rows", page.is_visible("#f-role") and page.is_visible("#f-platform"))

    cards = lambda: page.eval_on_selector_all("#list .card", "els => els.map(e => e.dataset.k)")
    chip = lambda grp, v: page.locator(f'#{grp} .chip[data-v="{v}"]')

    def chip_n(grp, v):
        m = re.search(r"(\d+)\s*$", chip(grp, v).inner_text())
        return int(m.group(1)) if m else None

    def tap(grp, v):
        chip(grp, v).click()
        page.wait_for_timeout(150)

    # ---------- layout on a phone ----------
    ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("no sideways page scroll on iPhone 13 (390 px)", ov <= 0, f"overflow {ov}px")
    hs = page.eval_on_selector_all(".chip, .btn, .tabs button", "els => els.map(e => e.getBoundingClientRect().height)")
    check("all buttons/chips are tap-sized (>= 32 px tall)", min(hs) >= 32, f"smallest {min(hs):.0f}px")
    check("greeting 'Hi My Love' shown", "Hi My Love" in page.inner_text("h1"))
    check("footer 'I love you' shown", "I love you" in page.inner_text("footer"))
    check("no JavaScript errors on load", not errors, "; ".join(errors[:2]))

    # ---------- default view ----------
    base = len(cards())
    check("default list = '2 weeks' chip count", base == chip_n("f-time", "14"), f"{base} cards")
    first = jobs[cards()[0]]
    check("newest job is first", all(first["posted_at"] >= j["posted_at"] for k, j in jobs.items() if k in cards()))

    # ---------- time windows ----------
    prev = 0
    for v in ["1", "3", "5", "7", "14"]:
        expect = chip_n("f-time", v)
        tap("f-time", v)
        ks = cards()
        too_old = [jobs[k]["title"] for k in ks if age_days(jobs[k], now) > int(v) + 0.01]
        check(f"Posted '{v} day(s)': list matches chip count and nothing older",
              len(ks) == expect and not too_old and len(ks) >= prev, f"{len(ks)} jobs; too old: {too_old[:2]}")
        prev = len(ks)
    when = page.inner_text("#list .card .when")
    check("card shows relative + exact time", bool(re.search(r"(ago|Today|Just now)", when)) and "·" in when, when)

    # ---------- role ----------
    for role in ["Site Engineer", "Cost Estimator", "Assistant Quantity Surveyor", "Office Engineer"]:
        expect = chip_n("f-role", role)
        tap("f-role", role)
        ks = cards()
        check(f"Role '{role}': only that role", len(ks) == expect and all(role in jobs[k]["roles"] for k in ks), f"{len(ks)} jobs")
        if role == "Site Engineer":
            page.screenshot(path=f"{OUT}/2_role_site_engineer.png")
        tap("f-role", role)   # off again

    # two roles at once = either role
    tap("f-role", "Site Engineer"); tap("f-role", "Office Engineer")
    ks = cards()
    check("Two roles selected = jobs of either role",
          all({"Site Engineer", "Office Engineer"} & set(jobs[k]["roles"]) for k in ks), f"{len(ks)} jobs")
    tap("f-role", "Site Engineer"); tap("f-role", "Office Engineer")

    # ---------- experience ----------
    for lvl in ["Fresh graduates OK", "Experience not mentioned"]:
        expect = chip_n("f-exp", lvl)
        tap("f-exp", lvl)
        ks = cards()
        check(f"Experience '{lvl}': only those", len(ks) == expect and all(jobs[k]["experience"] == lvl for k in ks), f"{len(ks)} jobs")
        if lvl == "Fresh graduates OK":
            page.screenshot(path=f"{OUT}/3_fresh_grads.png")
        tap("f-exp", lvl)
    too_much = [k for k in jobs if (jobs[k].get("experience") or "").startswith("Needs")]
    check("no shown job asks for 1+ years", not too_much, f"{len(too_much)} found")
    male = [j["title"] for j in jobs.values() if re.search(r"\bmales?\b", j["description"], re.I)
            and not re.search(r"\bmales?\s*(/|or|and|&)\s*females?|females?\s*(/|or|and|&)\s*males?", j["description"], re.I)]
    check("no shown job mentions male-only wording", not male, f"{male[:2]}")

    # ---------- area ----------
    for area in ["Metro Manila", "Laguna"]:
        if chip(f"f-area", area).count() == 0:
            continue
        expect = chip_n("f-area", area)
        tap("f-area", area)
        ks = cards()
        check(f"Area '{area}': only that area", len(ks) == expect and all(jobs[k]["area"] == area for k in ks), f"{len(ks)} jobs")
        tap("f-area", area)

    # ---------- platform ----------
    for plat in ["JobStreet", "Indeed", "LinkedIn"]:
        expect = chip_n("f-platform", plat)
        tap("f-platform", plat)
        ks = cards()
        on = lambda j: plat == j["platform"] or any(a["platform"] == plat for a in j["also_on"])
        check(f"Platform '{plat}': only jobs on {plat}", len(ks) == expect and all(on(jobs[k]) for k in ks), f"{len(ks)} jobs")
        tap("f-platform", plat)

    # ---------- combined ----------
    tap("f-role", "Project Engineer"); tap("f-area", "Metro Manila"); tap("f-time", "7")
    ks = cards()
    check("Combined (Project Engineer + Metro Manila + 1 week): all three hold",
          all("Project Engineer" in jobs[k]["roles"] and jobs[k]["area"] == "Metro Manila"
              and age_days(jobs[k], now) <= 7.01 for k in ks), f"{len(ks)} jobs")

    # ---------- Excel of current filters ----------
    with page.expect_download() as dl:
        page.click("#dl-filtered")
    path = f"{OUT}/excel_filtered.xlsx"
    dl.value.save_as(path)
    import openpyxl
    ws = openpyxl.load_workbook(path).active
    header = [c.value for c in ws[1]]
    check("Excel (current filters): one row per shown job", ws.max_row - 1 == len(ks), f"{ws.max_row - 1} rows vs {len(ks)} cards")
    need = ["Posted (Manila time)", "Job title", "Company", "Experience asked", "Office / work address",
            "Recruiter email(s)", "Phone(s)", "Platform", "Job link", "Resume to send"]
    check("Excel has all detail columns", all(h in header for h in need), f"missing {[h for h in need if h not in header]}")
    link_col = header.index("Job link") + 1
    check("Excel job links are clickable", ws.cell(2, link_col).hyperlink is not None if ws.max_row > 1 else True)
    tap("f-role", "Project Engineer"); tap("f-area", "Metro Manila"); tap("f-time", "14")

    # ---------- search, toggles, sort ----------
    page.fill("#f-q", "taguig")
    page.wait_for_timeout(400)
    ks = cards()
    hay = lambda j: f'{j["title"]} {j["company"]} {j["location"]} {j["address"]} {j["area"]} {j["description"]}'.lower()
    check("Search 'taguig': every result mentions Taguig", ks and all("taguig" in hay(jobs[k]) for k in ks), f"{len(ks)} jobs")
    page.fill("#f-q", "")
    page.wait_for_timeout(400)
    page.check("#f-salary")
    ks = cards()
    check("'Salary listed' toggle: all have salary", all(jobs[k]["salary"] for k in ks), f"{len(ks)} jobs")
    page.uncheck("#f-salary")
    page.select_option("#f-sort", "salary")
    ks = cards()
    flags = [bool(jobs[k]["salary"]) for k in ks]
    check("Sort 'Salary shown first' puts salaried jobs on top", flags == sorted(flags, reverse=True))
    page.select_option("#f-sort", "new")

    # ---------- filters remembered after reload ----------
    tap("f-role", "Cost Estimator")
    page.reload()
    page.wait_for_selector("#list .card")
    check("Folded button shows how many filters are on", "1 active" in page.inner_text("#f-toggle"), page.inner_text("#f-toggle"))
    page.click("#f-toggle")
    check("Filters remembered after reopening", "on" in (chip("f-role", "Cost Estimator").get_attribute("class") or ""))
    page.click("#f-reset")
    page.wait_for_timeout(150)
    check("Reset returns to the full list", len(cards()) == base, f"{len(cards())} vs {base}")

    # ---------- card details ----------
    page.locator("#list .card details.desc summary").first.click()
    page.wait_for_timeout(150)
    page.locator("#list .card").first.scroll_into_view_if_needed()
    page.screenshot(path=f"{OUT}/4_card_expanded.png")
    href = page.get_attribute("#list .card a.btn.primary", "href")
    check("Job card links to the posting", bool(href and href.startswith("https://")), href)

    # ---------- tabs ----------
    page.click('#tabs button[data-tab="hidden"]')
    page.wait_for_timeout(150)
    ks = cards()
    reasons = page.eval_on_selector_all("#list .card .badge.why", "els => els.map(e => e.textContent)")
    expect_hidden = len({k for k, j in hidden.items() if age_days(j, now) <= 14.01})
    check("Hidden tab: one card per removed job, each with a reason",
          len(ks) == expect_hidden and len(reasons) == len(ks) and len(set(ks)) == len(ks), f"{len(ks)} cards, {expect_hidden} expected")
    page.screenshot(path=f"{OUT}/5_hidden_tab.png")
    page.click('#tabs button[data-tab="all"]')

    # ---------- bottom of page ----------
    page.locator("footer").scroll_into_view_if_needed()
    page.screenshot(path=f"{OUT}/6_bottom.png")
    check("No JavaScript errors during the whole test", not errors, "; ".join(errors[:3]))
    browser.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
