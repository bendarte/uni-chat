"""
Comprehensive backend test suite.
Run with: .venv/bin/python scripts/run_full_test.py
"""

import asyncio
import json
import random
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Tuple
from urllib.error import HTTPError, URLError

import requests

import os

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("BACKEND_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

results = []


def record(section, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"section": section, "name": name, "status": status, "detail": detail})
    marker = "✓" if passed else "✗"
    print(f"  [{marker}] {status}: {name}")
    if detail and not passed:
        # Print first 300 chars of detail for failures
        print(f"       → {str(detail)[:300]}")
    elif detail and passed:
        print(f"       → {str(detail)[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — DATA QUALITY: URL VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def check_url(url: str, timeout: int = 8) -> Tuple[bool, int, str]:
    """HEAD request, follow one redirect. Returns (ok, status_code, error)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; test-bot/1.0)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400, resp.status, ""
    except HTTPError as e:
        return False, e.code, str(e)
    except URLError as e:
        return False, 0, str(e.reason)
    except Exception as e:
        return False, 0, str(e)


def test_section_1():
    print("\n═══ SECTION 1: DATA QUALITY — URL VALIDATION ═══")

    resp = requests.get(f"{BASE_URL}/programs", headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        record("1-URL", "Fetch /programs", False, f"HTTP {resp.status_code}")
        return
    programs = resp.json()
    record("1-URL", f"Fetch /programs ({len(programs)} programs)", True, f"{len(programs)} programs returned")

    # Check all for empty / missing source_url
    empty_urls = [p for p in programs if not p.get("source_url", "").strip()]
    record(
        "1-URL",
        "No programs with empty source_url",
        len(empty_urls) == 0,
        f"{len(empty_urls)} programs have empty/missing source_url"
        + (f": {[p.get('name', '?') for p in empty_urls[:5]]}" if empty_urls else ""),
    )

    # Check format (https://, not localhost)
    bad_format = [
        p for p in programs
        if p.get("source_url") and (
            not p["source_url"].startswith("https://")
            or "localhost" in p["source_url"]
            or "127.0.0.1" in p["source_url"]
        )
    ]
    record(
        "1-URL",
        "All source_urls are valid https:// (not localhost)",
        len(bad_format) == 0,
        f"{len(bad_format)} programs have bad URL format"
        + (f": {[p.get('source_url') for p in bad_format[:3]]}" if bad_format else ""),
    )

    # Sample 50 random programs for HEAD requests
    valid_url_programs = [p for p in programs if p.get("source_url", "").startswith("https://")]
    sample = random.sample(valid_url_programs, min(50, len(valid_url_programs)))
    print(f"\n  Checking {len(sample)} sampled URLs with HEAD requests (max 10 concurrent)...")

    broken = []
    timed_out = []

    def check_one(p):
        url = p["source_url"]
        ok, code, err = check_url(url, timeout=8)
        return p, url, ok, code, err

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(check_one, p): p for p in sample}
        for i, fut in enumerate(as_completed(futures), 1):
            p, url, ok, code, err = fut.result()
            if not ok:
                if "timed out" in err.lower() or "timeout" in err.lower() or code == 0:
                    timed_out.append((p.get("name"), url, err))
                else:
                    broken.append((p.get("name"), url, code, err))
            if i % 10 == 0:
                print(f"    ... {i}/{len(sample)} done")

    record(
        "1-URL",
        "HTTP HEAD check (sample 50): no 4xx/5xx",
        len(broken) == 0,
        f"{len(broken)} URLs returned 4xx/5xx: "
        + str([(name, url, code) for name, url, code, _ in broken[:5]]),
    )
    record(
        "1-URL",
        "HTTP HEAD check (sample 50): no timeouts",
        len(timed_out) == 0,
        f"{len(timed_out)} URLs timed out"
        + (f": {[url for _, url, _ in timed_out[:3]]}" if timed_out else ""),
    )

    if broken:
        from urllib.parse import urlparse
        domains = {}
        for _, url, code, _ in broken:
            d = urlparse(url).netloc
            domains[d] = domains.get(d, 0) + 1
        print(f"\n  Broken URL domains: {domains}")

    if timed_out:
        from urllib.parse import urlparse
        domains = {}
        for _, url, _ in timed_out:
            d = urlparse(url).netloc
            domains[d] = domains.get(d, 0) + 1
        print(f"\n  Timed-out URL domains: {domains}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — MULTI-TURN CONVERSATIONS
# ─────────────────────────────────────────────────────────────────────────────

def chat(message: str, session_id: str, filters: Optional[Dict] = None) -> Dict:
    payload: dict = {"message": message, "session_id": session_id}
    if filters:
        payload["filters"] = filters
    resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def summarize_response(r: dict) -> str:
    answer_short = r.get("answer", "")[:120].replace("\n", " ")
    n_recs = len(r.get("recommendations", []))
    n_qs = len(r.get("questions", []))
    return f"answer='{answer_short}...', recs={n_recs}, questions={n_qs}"


def test_section_2():
    print("\n═══ SECTION 2: MULTI-TURN CONVERSATIONS ═══")

    # ── Sequence A ──────────────────────────────────────────────────────────
    print("\n  Sequence A: Vag start → clarification → val → rekommendationer")
    sid = f"test-seq-a-{int(time.time())}"
    try:
        r1 = chat("jag vill jobba med teknik", sid)
        summary1 = summarize_response(r1)
        print(f"    Turn 1: {summary1}")
        # Expect guidance / clarification, NOT direct recommendations (or few)
        has_questions_or_guidance = len(r1.get("questions", [])) > 0 or len(r1.get("answer", "")) > 20
        not_pure_recommendations = len(r1.get("recommendations", [])) <= 5
        record("2-Conv", "Seq A Turn 1: guidance/clarification (not pure recs)", has_questions_or_guidance and not_pure_recommendations, summary1)

        r2 = chat("mer mot AI och data", sid)
        summary2 = summarize_response(r2)
        print(f"    Turn 2: {summary2}")
        has_follow_up = len(r2.get("questions", [])) > 0 or len(r2.get("recommendations", [])) > 0
        record("2-Conv", "Seq A Turn 2: follow-up questions or recommendations", has_follow_up, summary2)

        r3 = chat("master på engelska", sid)
        summary3 = summarize_response(r3)
        print(f"    Turn 3: {summary3}")
        recs = r3.get("recommendations", [])
        has_recs = len(recs) > 0
        # Check that recs are AI/data related
        ai_keywords = {"ai", "machine learning", "data", "artificial", "intelligence", "computer", "neural", "deep learning"}
        ai_related = any(
            any(kw in (rec.get("program", "") + rec.get("university", "") + " ".join(rec.get("explanation", []))).lower()
                for kw in ai_keywords)
            for rec in recs[:5]
        ) if recs else False
        record("2-Conv", "Seq A Turn 3: recommendations returned", has_recs, summary3)
        record("2-Conv", "Seq A Turn 3: AI-related programs in recs", ai_related or not has_recs,
               f"Top programs: {[r.get('program') for r in recs[:3]]}")
    except Exception as e:
        record("2-Conv", "Seq A: exception", False, str(e))

    # ── Sequence B ──────────────────────────────────────────────────────────
    print("\n  Sequence B: Direkt specifik fråga")
    sid = f"test-seq-b-{int(time.time())}"
    try:
        r1 = chat("Jag vill läsa civilingenjör inom hållbar energi, master, Göteborg, heltid", sid)
        summary1 = summarize_response(r1)
        print(f"    Turn 1: {summary1}")
        recs = r1.get("recommendations", [])
        record("2-Conv", "Seq B Turn 1: direct specific → recommendations returned", len(recs) > 0, summary1)
        if recs:
            energy_keywords = {"energi", "energy", "hållbar", "sustainable", "civil", "engineering", "teknik"}
            energy_related = any(
                any(kw in (rec.get("program", "") + " ".join(rec.get("explanation", []))).lower() for kw in energy_keywords)
                for rec in recs[:5]
            )
            record("2-Conv", "Seq B Turn 1: energy/sustainable programs in recs", energy_related,
                   f"Top programs: {[r.get('program') for r in recs[:3]]}")
    except Exception as e:
        record("2-Conv", "Seq B: exception", False, str(e))

    # ── Sequence C ──────────────────────────────────────────────────────────
    print("\n  Sequence C: Reset-flödet")
    sid = f"test-seq-c-{int(time.time())}"
    try:
        r1 = chat("Jag vill plugga ekonomi i Lund, kandidat", sid)
        summary1 = summarize_response(r1)
        print(f"    Turn 1: {summary1}")
        recs1 = r1.get("recommendations", [])
        record("2-Conv", "Seq C Turn 1: ekonomi/Lund → response returned", True, summary1)

        r2 = chat("börja om", sid)
        summary2 = summarize_response(r2)
        print(f"    Turn 2 (reset): {summary2}")
        is_reset = len(r2.get("recommendations", [])) == 0
        record("2-Conv", "Seq C Turn 2: reset → no recommendations", is_reset, summary2)

        r3 = chat("psykologi", sid)
        summary3 = summarize_response(r3)
        print(f"    Turn 3: {summary3}")
        answer3 = r3.get("answer", "").lower()
        recs3 = r3.get("recommendations", [])
        # Should not reference ekonomi or Lund
        no_old_context = "lund" not in answer3 and "ekonomi" not in answer3
        record("2-Conv", "Seq C Turn 3: no old context (no Lund/ekonomi)", no_old_context, summary3)
        psych_keywords = {"psykologi", "psychology", "psykolog", "beteende", "mental"}
        psych_related = any(
            any(kw in (rec.get("program", "") + " ".join(rec.get("explanation", []))).lower() for kw in psych_keywords)
            for rec in recs3[:5]
        ) if recs3 else (any(kw in answer3 for kw in psych_keywords))
        record("2-Conv", "Seq C Turn 3: psykologi-related response", psych_related, summary3)
    except Exception as e:
        record("2-Conv", "Seq C: exception", False, str(e))

    # ── Sequence D ──────────────────────────────────────────────────────────
    print("\n  Sequence D: Bara språk-filter, ingen stad")
    sid = f"test-seq-d-{int(time.time())}"
    try:
        r1 = chat("rekommendera program", sid, filters={"language": "Swedish"})
        summary1 = summarize_response(r1)
        print(f"    Turn 1: {summary1}")
        recs = r1.get("recommendations", [])
        record("2-Conv", "Seq D: language filter → response returned", True, summary1)

        active = r1.get("active_filters", {}) or {}
        has_lang_filter = (
            active.get("language") == "Swedish"
            or active.get("language", "").lower() == "swedish"
        )
        record("2-Conv", "Seq D: active_filters includes language=Swedish", has_lang_filter,
               f"active_filters={active}")
    except Exception as e:
        record("2-Conv", "Seq D: exception", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — EDGE CASES
# ─────────────────────────────────────────────────────────────────────────────

def test_section_3():
    print("\n═══ SECTION 3: EDGE CASES ═══")
    sid = f"test-edge-{int(time.time())}"

    # Empty string
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "", "session_id": sid}, timeout=15)
        record("3-Edge", "Empty string → 422", resp.status_code == 422, f"HTTP {resp.status_code}")
    except Exception as e:
        record("3-Edge", "Empty string → 422", False, str(e))

    # Whitespace only
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "   ", "session_id": sid}, timeout=15)
        record("3-Edge", "Whitespace only → 422", resp.status_code == 422, f"HTTP {resp.status_code}")
    except Exception as e:
        record("3-Edge", "Whitespace only → 422", False, str(e))

    # 2001 chars
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "a" * 2001, "session_id": sid}, timeout=15)
        record("3-Edge", "2001 chars → 422", resp.status_code == 422, f"HTTP {resp.status_code}")
    except Exception as e:
        record("3-Edge", "2001 chars → 422", False, str(e))

    # Exactly 2000 chars
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "a" * 2000, "session_id": sid}, timeout=60)
        record("3-Edge", "2000 chars → 200", resp.status_code == 200, f"HTTP {resp.status_code}")
    except Exception as e:
        record("3-Edge", "2000 chars → 200", False, str(e))

    # Åäö + emoji
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "Jag vill plugga miljö och hållbarhet 🌱", "session_id": sid}, timeout=60)
        ok = resp.status_code == 200
        record("3-Edge", "Åäö + emoji → 200", ok, f"HTTP {resp.status_code}")
        if ok:
            data = resp.json()
            has_content = len(data.get("answer", "")) > 0 or len(data.get("recommendations", [])) > 0 or len(data.get("questions", [])) > 0
            record("3-Edge", "Åäö + emoji → relevant response", has_content, summarize_response(data))
    except Exception as e:
        record("3-Edge", "Åäö + emoji → 200", False, str(e))

    # SQL injection
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "'; DROP TABLE programs; --", "session_id": sid}, timeout=60)
        ok = resp.status_code == 200
        record("3-Edge", "SQL injection → 200 (no crash)", ok, f"HTTP {resp.status_code}")
    except Exception as e:
        record("3-Edge", "SQL injection → 200 (no crash)", False, str(e))

    # HTML/script injection
    try:
        resp = requests.post(f"{BASE_URL}/chat", headers=HEADERS,
                             json={"message": "<script>alert(1)</script>", "session_id": sid}, timeout=60)
        ok = resp.status_code == 200
        record("3-Edge", "HTML/script injection → 200 (no crash)", ok, f"HTTP {resp.status_code}")
        if ok:
            # Ensure script tag not reflected raw in answer
            answer = resp.json().get("answer", "")
            no_raw_script = "<script>" not in answer
            record("3-Edge", "HTML/script: no raw <script> in answer", no_raw_script, f"answer[:100]={answer[:100]}")
    except Exception as e:
        record("3-Edge", "HTML/script injection → 200 (no crash)", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — BACKEND-DOWN SCENARIO
# ─────────────────────────────────────────────────────────────────────────────

def test_section_4():
    print("\n═══ SECTION 4: BACKEND-DOWN / ERROR HANDLING ═══")

    # Test Next.js frontend proxy (port 3000)
    try:
        resp = requests.post("http://localhost:3000/api/chat",
                             headers={"Content-Type": "application/json"},
                             json={"message": "test", "session_id": "test"},
                             timeout=5)
        record("4-ErrorHandling", "Next.js proxy /api/chat reachable", True, f"HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        record("4-ErrorHandling", "Next.js proxy: not running (skipped)", True, "Frontend not running — skipping frontend proxy test")
    except Exception as e:
        record("4-ErrorHandling", "Next.js proxy test", False, str(e))

    # Verify backend returns {"detail": ...} on 500, not stack traces
    # We test the global exception handler indirectly by checking /programs with
    # a garbage path and ensure it returns JSON with "detail" key (not HTML/traceback)
    try:
        resp = requests.get(f"{BASE_URL}/nonexistent_path_xyz", headers=HEADERS, timeout=10)
        is_json = resp.headers.get("content-type", "").startswith("application/json")
        body = resp.text
        no_traceback = "Traceback" not in body and "traceback" not in body
        record("4-ErrorHandling", "404 response is JSON (not HTML)", is_json, f"Content-Type: {resp.headers.get('content-type')}")
        record("4-ErrorHandling", "Error responses don't leak stack traces", no_traceback, f"HTTP {resp.status_code}")
    except Exception as e:
        record("4-ErrorHandling", "Error response format check", False, str(e))

    # Test 401 on missing API key
    try:
        resp = requests.post(f"{BASE_URL}/chat",
                             headers={"Content-Type": "application/json"},
                             json={"message": "test"},
                             timeout=10)
        record("4-ErrorHandling", "Missing API key → 401", resp.status_code == 401,
               f"HTTP {resp.status_code}, body={resp.text[:100]}")
    except Exception as e:
        record("4-ErrorHandling", "Missing API key → 401", False, str(e))

    # Test wrong API key → 401
    try:
        resp = requests.post(f"{BASE_URL}/chat",
                             headers={"X-API-Key": "wrong-key", "Content-Type": "application/json"},
                             json={"message": "test"},
                             timeout=10)
        record("4-ErrorHandling", "Wrong API key → 401", resp.status_code == 401,
               f"HTTP {resp.status_code}")
    except Exception as e:
        record("4-ErrorHandling", "Wrong API key → 401", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — RECOMMENDATION QUALITY
# ─────────────────────────────────────────────────────────────────────────────

QUALITY_QUERIES = [
    (
        "AI och machine learning",
        {"ai", "machine learning", "data", "artificial intelligence", "deep learning", "neural", "computer science"},
        {"konst", "musik", "humaniora", "juridik", "law"},
    ),
    (
        "läkare eller medicin",
        {"medicin", "medicine", "läkare", "physician", "klinisk", "clinical", "biomedicin", "biomedicine", "hälsa", "health"},
        {"konst", "musik", "design", "juridik", "ekonomi", "handel"},
    ),
    (
        "ekonomi och finans, master",
        {"ekonomi", "economics", "finans", "finance", "business", "handel", "accounting", "redovisning"},
        {"konst", "musik", "medicin", "teknik", "engineering"},
    ),
    (
        "design och UX",
        {"design", "ux", "user experience", "interaktion", "interaction", "hci", "interface", "human-computer"},
        {"medicin", "ekonomi", "läkare", "juridik"},
    ),
    (
        "hållbarhet och miljö",
        {"hållbar", "sustainable", "miljö", "environment", "climate", "klimat", "energi", "ecology", "ekologi"},
        {"konst", "musik", "juridik", "finans"},
    ),
]


def test_section_5():
    print("\n═══ SECTION 5: RECOMMENDATION QUALITY ═══")

    for query, good_kws, bad_kws in QUALITY_QUERIES:
        sid = f"test-quality-{int(time.time())}-{query[:10].replace(' ', '')}"
        try:
            r = chat(query, sid)
            recs = r.get("recommendations", [])
            if not recs:
                record("5-Quality", f"'{query[:30]}' → recs returned", False,
                       f"0 recommendations. answer={r.get('answer','')[:100]}")
                continue

            record("5-Quality", f"'{query[:30]}' → recs returned", True, f"{len(recs)} recs")

            # Check at least half of top-5 contain good keywords
            top5 = recs[:5]
            good_count = 0
            for rec in top5:
                text = (rec.get("program", "") + " " + " ".join(rec.get("explanation", []))).lower()
                if any(kw in text for kw in good_kws):
                    good_count += 1

            quality_ok = good_count >= max(1, len(top5) // 2)
            record("5-Quality", f"'{query[:30]}' → semantically relevant",
                   quality_ok,
                   f"{good_count}/{len(top5)} recs contain relevant keywords. Top: {[r.get('program') for r in top5[:3]]}")

            # Check no bad keywords dominate
            bad_count = 0
            for rec in top5:
                text = (rec.get("program", "") + " " + " ".join(rec.get("explanation", []))).lower()
                if any(kw in text for kw in bad_kws) and not any(kw in text for kw in good_kws):
                    bad_count += 1
            record("5-Quality", f"'{query[:30]}' → no clearly wrong recs",
                   bad_count == 0,
                   f"{bad_count}/{len(top5)} recs appear unrelated")
        except Exception as e:
            record("5-Quality", f"'{query[:30]}': exception", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — ACTIVE FILTERS
# ─────────────────────────────────────────────────────────────────────────────

def test_section_6():
    print("\n═══ SECTION 6: ACTIVE FILTERS ═══")
    sid = f"test-filters-{int(time.time())}"

    try:
        r = chat(
            "visa program",
            sid,
            filters={"cities": ["Gothenburg"], "level": "master"},
        )
        active = r.get("active_filters", {}) or {}
        print(f"  active_filters returned: {json.dumps(active, ensure_ascii=False)}")

        # city check — may be stored as "city", "cities", or nested
        city_val = (
            active.get("city")
            or active.get("cities")
            or active.get("location")
            or ""
        )
        if isinstance(city_val, list):
            city_val = city_val[0] if city_val else ""
        city_ok = "gothenburg" in str(city_val).lower() or "göteborg" in str(city_val).lower()
        record("6-Filters", "active_filters.city == Gothenburg", city_ok,
               f"city_val={city_val!r}, full active_filters={active}")

        # level check
        level_val = active.get("level") or active.get("degree_level") or ""
        level_ok = "master" in str(level_val).lower()
        record("6-Filters", "active_filters.level == Master", level_ok,
               f"level_val={level_val!r}, full active_filters={active}")

        # Verify recommendations match filter
        recs = r.get("recommendations", [])
        if recs:
            # Check cities in recommendations
            cities_in_recs = [rec.get("city", "") for rec in recs[:5]]
            gothenburg_count = sum(
                1 for c in cities_in_recs
                if c and ("gothenburg" in c.lower() or "göteborg" in c.lower())
            )
            record("6-Filters", "Recommendations filtered to Gothenburg",
                   gothenburg_count > 0 or len(recs) == 0,
                   f"Gothenburg matches in top 5: {gothenburg_count}/5, cities={cities_in_recs}")
    except Exception as e:
        record("6-Filters", "Active filters test: exception", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("  COMPREHENSIVE BACKEND TEST SUITE")
    print(f"  Target: {BASE_URL}")
    print("═" * 60)

    test_section_1()
    test_section_2()
    test_section_3()
    test_section_4()
    test_section_5()
    test_section_6()

    # Summary
    print("\n" + "═" * 60)
    print("  SUMMARY")
    print("═" * 60)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    print(f"\n  Total: {total}  |  PASS: {passed}  |  FAIL: {failed}")

    if failed:
        print("\n  FAILED TESTS:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    ✗ [{r['section']}] {r['name']}")
                if r["detail"]:
                    print(f"      → {str(r['detail'])[:200]}")

    # Section breakdown
    print("\n  BY SECTION:")
    sections = {}
    for r in results:
        s = r["section"]
        if s not in sections:
            sections[s] = {"pass": 0, "fail": 0}
        sections[s]["pass" if r["status"] == "PASS" else "fail"] += 1
    for s, counts in sections.items():
        bar = "✓" * counts["pass"] + "✗" * counts["fail"]
        print(f"    {s}: {counts['pass']} pass, {counts['fail']} fail  [{bar}]")

    # Priority issues
    if failed:
        print("\n  PRIORITIZED ISSUES TO FIX:")
        priority = {
            "1-URL": "P1 — Data quality",
            "2-Conv": "P1 — Core functionality",
            "3-Edge": "P2 — Input validation / security",
            "4-ErrorHandling": "P2 — Error handling",
            "5-Quality": "P3 — Recommendation quality",
            "6-Filters": "P2 — Filter correctness",
        }
        seen_sections = set()
        for r in results:
            if r["status"] == "FAIL" and r["section"] not in seen_sections:
                seen_sections.add(r["section"])
                label = priority.get(r["section"], r["section"])
                fails_in_section = [x for x in results if x["section"] == r["section"] and x["status"] == "FAIL"]
                print(f"\n  [{label}] {len(fails_in_section)} issue(s):")
                for f in fails_in_section:
                    print(f"    - {f['name']}: {str(f['detail'])[:150]}")

    print("\n" + "═" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
