#!/usr/bin/env python3
"""snapshot.py - public-intelligence signal-first CLI router."""

from __future__ import annotations

import json
import re
import socket
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import dns.resolver
import phonenumbers
import requests
import tldextract
from bs4 import BeautifulSoup
from phonenumbers import PhoneNumberType, carrier, geocoder, timezone
from rich.console import Console
from rich.table import Table

# =========================
# constants
# =========================
CONFIDENCE = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
USER_AGENT = "snapshot-cli/1.0 (+public-intel-signal-first)"
REPORTS_DIR = Path("reports")
TIMEOUT = 8
HEADERS_TO_COLLECT = [
    "server",
    "x-powered-by",
    "content-type",
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
]
FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com",
    "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me", "zoho.com",
    "mail.com", "gmx.com", "gmx.net", "tutanota.com", "tuta.com",
}
SOCIAL_HOST_HINTS = ("linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com", "tiktok.com", "github.com")

console = Console()


@dataclass
class Finding:
    label: str
    value: str
    confidence: str


# =========================
# helpers
# =========================
def safe_get(url: str) -> requests.Response | None:
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException:
        return None


def now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def normalize_domain(value: str) -> str:
    parsed = urlparse(value if value.startswith(("http://", "https://")) else f"https://{value}")
    host = parsed.netloc or parsed.path
    return host.lower().strip("/")


def extract_emails(text: str) -> list[str]:
    return sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))[:20]


def extract_phones(text: str) -> list[str]:
    candidates = re.findall(r"\+?\d[\d\s().-]{7,}\d", text)
    return sorted(set(c.strip() for c in candidates))[:20]


def classify_input(raw: str) -> str:
    value = raw.strip()
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return "email"
    if value.startswith(("http://", "https://")):
        return "url"
    if re.match(r"^\+?[\d().\s-]{8,}$", value):
        return "phone_number"
    ext = tldextract.extract(value)
    if ext.domain and ext.suffix and " " not in value:
        return "domain"
    if re.match(r"^[A-Za-z0-9_.-]{3,32}$", value):
        return "username"
    if len(value.split()) >= 2:
        return "business_name"
    return "general_name_or_search_term"


def confidence_summary(findings: list[Finding]) -> dict[str, int]:
    out = {c: 0 for c in CONFIDENCE}
    for f in findings:
        out[f.confidence] = out.get(f.confidence, 0) + 1
    return out


# =========================
# DNS + website
# =========================
def dns_checks(domain: str) -> dict[str, Any]:
    resolver = dns.resolver.Resolver()
    data: dict[str, Any] = {"domain_exists": False, "mx_records": [], "spf_record": None, "dmarc_record": None}
    try:
        socket.gethostbyname(domain)
        data["domain_exists"] = True
    except OSError:
        return data

    try:
        data["mx_records"] = [str(r.exchange).rstrip(".") for r in resolver.resolve(domain, "MX")]
    except Exception:
        pass
    try:
        txt = [str(r).strip('"') for r in resolver.resolve(domain, "TXT")]
        spf = [t for t in txt if "v=spf1" in t.lower()]
        data["spf_record"] = spf[0] if spf else None
    except Exception:
        pass
    try:
        dmarc_domain = f"_dmarc.{domain}"
        txt = [str(r).strip('"') for r in resolver.resolve(dmarc_domain, "TXT")]
        dmarc = [t for t in txt if "v=dmarc1" in t.lower()]
        data["dmarc_record"] = dmarc[0] if dmarc else None
    except Exception:
        pass
    return data


def website_checks(target: str) -> dict[str, Any]:
    base = target if target.startswith(("http://", "https://")) else f"https://{target}"
    resp = safe_get(base)
    if resp is None:
        return {"reachable": False, "requested_url": base}

    soup = BeautifulSoup(resp.text[:300000], "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_tag.get("content", "").strip() if meta_tag else None
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    social = sorted(set(l for l in links if any(h in l for h in SOCIAL_HOST_HINTS)))[:20]

    return {
        "reachable": True,
        "requested_url": base,
        "status_code": resp.status_code,
        "final_url": resp.url,
        "page_title": title,
        "meta_description": meta_desc,
        "headers": {k: v for k, v in resp.headers.items() if k.lower() in HEADERS_TO_COLLECT},
        "public_emails": extract_emails(resp.text),
        "public_phone_numbers": extract_phones(resp.text),
        "social_links": social,
        "robots_url": f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}/robots.txt",
        "sitemap_url": f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}/sitemap.xml",
    }


# =========================
# pivots
# =========================
def gen_username_variants(base: str) -> list[str]:
    clean = re.sub(r"[^A-Za-z0-9._-]", "", base)
    variants = {clean, clean.lower(), clean.replace(".", ""), clean.replace("_", ""), clean.replace("-", "")}
    return [v for v in sorted(variants) if v][:12]


def phone_variants(e164: str) -> list[str]:
    return [e164, e164.replace("+", "00"), e164.replace("+", ""), e164.replace(" ", "")]


def search_links(term: str, domain: str | None = None) -> dict[str, str]:
    q = quote_plus(f'"{term}"')
    links = {
        "Google": f"https://www.google.com/search?q={q}",
        "DuckDuckGo": f"https://duckduckgo.com/?q={q}",
        "Bing": f"https://www.bing.com/search?q={q}",
        "GitHub search": f"https://github.com/search?q={quote_plus(term)}",
        "Facebook search": f"https://www.facebook.com/search/top/?q={quote_plus(term)}",
        "Yelp search": f"https://www.yelp.com/search?find_desc={quote_plus(term)}",
        "BBB search": f"https://www.bbb.org/search?find_text={quote_plus(term)}",
        "OpenStreetMap search": f"https://www.openstreetmap.org/search?query={quote_plus(term)}",
    }
    if domain:
        links["crt.sh"] = f"https://crt.sh/?q={quote_plus(domain)}"
    return links


# =========================
# main processing
# =========================
def run_snapshot(raw_input: str) -> dict[str, Any]:
    detected = classify_input(raw_input)
    findings: list[Finding] = []
    pivots: dict[str, str] = {}
    signals: dict[str, Any] = {}

    if detected == "email":
        email = raw_input.strip().lower()
        local, domain = email.split("@", 1)
        is_free = domain in FREE_EMAIL_PROVIDERS
        findings.append(Finding("Normalized email", email, "HIGH"))
        findings.append(Finding("Email domain", domain, "HIGH"))
        findings.append(Finding("Free provider", str(is_free), "HIGH"))
        if is_free:
            findings.append(Finding("Provider ownership note", "Domain belongs to major email provider, not target entity.", "HIGH"))
        else:
            signals["dns"] = dns_checks(domain)
            signals["website"] = website_checks(domain)
        username_vars = gen_username_variants(local)
        signals["username_variants"] = username_vars
        findings.append(Finding("Name guess from local-part", local, "LOW"))
        pivots.update(search_links(email, domain))

    elif detected == "phone_number":
        parsed = phonenumbers.parse(raw_input, None)
        possible = phonenumbers.is_possible_number(parsed)
        valid = phonenumbers.is_valid_number(parsed)
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        findings.extend([
            Finding("E.164", e164, "HIGH"),
            Finding("Possible", str(possible), "MEDIUM"),
            Finding("Valid", str(valid), "MEDIUM"),
            Finding("Region", geocoder.description_for_number(parsed, "en") or "Unknown", "MEDIUM"),
            Finding("Carrier", carrier.name_for_number(parsed, "en") or "Unknown", "LOW"),
            Finding("Timezones", ", ".join(timezone.time_zones_for_number(parsed)) or "Unknown", "LOW"),
            Finding("Number type", str(PhoneNumberType.to_string(phonenumbers.number_type(parsed))), "LOW"),
        ])
        signals["phone_variants"] = phone_variants(e164)
        pivots.update(search_links(e164))
        pivots["800notes"] = f"https://800notes.com/Phone.aspx/{e164.replace('+', '')}"
        pivots["WhoCallsMe"] = f"https://whocallsme.com/Phone-Number.aspx/{e164.replace('+', '')}"

    elif detected in {"domain", "url"}:
        domain = normalize_domain(raw_input)
        if detected == "domain":
            signals["dns"] = dns_checks(domain)
        signals["website"] = website_checks(raw_input)
        findings.append(Finding("Target domain", domain, "HIGH"))
        pivots.update(search_links(domain, domain))

    else:
        term = raw_input.strip()
        findings.append(Finding("Candidate-only mode", "No direct verification. Public pivots generated.", "HIGH"))
        signals["username_variants"] = gen_username_variants(term.replace(" ", ""))
        pivots.update(search_links(term))

    conf = confidence_summary(findings)
    return {
        "input": raw_input,
        "detected_type": detected,
        "key_findings": [f.__dict__ for f in findings],
        "public_signals": signals,
        "confidence_summary": conf,
        "next_best_pivots": pivots,
        "safety_notes": [
            "Public-source and consent-based checks only.",
            "No login/signup/recovery/account probing used.",
            "Weak matches are not identity confirmation.",
        ],
    }


def save_reports(result: dict[str, Any]) -> tuple[str, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = now_stamp()
    base = REPORTS_DIR / f"snapshot_{result['detected_type']}_{ts}"
    json_path = str(base.with_suffix(".json"))
    txt_path = str(base.with_suffix(".txt"))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    lines = [
        "Snapshot Report",
        "=" * 40,
        f"Input Summary: {result['input']}",
        f"Detected Input Type: {result['detected_type']}",
        "",
        "Key Findings:",
    ]
    for k in result["key_findings"]:
        lines.append(f"- [{k['confidence']}] {k['label']}: {k['value']}")
    lines.extend([
        "",
        "Public Signals:",
        json.dumps(result["public_signals"], indent=2),
        "",
        "Confidence Notes:",
        json.dumps(result["confidence_summary"], indent=2),
        "",
        "Next Best Pivots:",
    ])
    lines.extend([f"- {k}: {v}" for k, v in result["next_best_pivots"].items()])
    lines.extend(["", "Safety Notes:"])
    lines.extend([f"- {n}" for n in result["safety_notes"]])
    lines.extend(["", f"Saved Report Paths: {txt_path}, {json_path}"])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return txt_path, json_path


def render_terminal(result: dict[str, Any], txt_path: str, json_path: str) -> None:
    table = Table(title="snapshot summary", show_lines=False)
    table.add_column("field", style="cyan")
    table.add_column("value", style="white")

    top = "; ".join([f"{k['label']}={k['value']}" for k in result["key_findings"][:3]])
    table.add_row("input", result["input"])
    table.add_row("detected_type", result["detected_type"])
    table.add_row("top_findings", top or "none")
    table.add_row("confidence_summary", json.dumps(result["confidence_summary"]))
    table.add_row("number_of_pivots_generated", str(len(result["next_best_pivots"])))
    table.add_row("report_paths", f"{txt_path} | {json_path}")
    console.print(table)


def main() -> None:
    if len(sys.argv) < 2:
        console.print("Usage: python3 snapshot.py \"input\"")
        sys.exit(1)

    raw_input = sys.argv[1]
    try:
        result = run_snapshot(raw_input)
    except phonenumbers.NumberParseException:
        result = run_snapshot(raw_input.strip())
    txt_path, json_path = save_reports(result)
    render_terminal(result, txt_path, json_path)


if __name__ == "__main__":
    main()
