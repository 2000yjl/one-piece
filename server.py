from __future__ import annotations

import json
import os
import re
import threading
import time
import base64
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public" if (ROOT / "public").is_dir() else ROOT
LIMITLESS = "https://onepiece.limitlesstcg.com"
DATA = ROOT / "data" if (ROOT / "data").is_dir() else ROOT
HISTORY_FILE = DATA / "history.jsonl"
SNK_HISTORY_FILE = DATA / "snkrdunk_history.jsonl"
BANDAI_CATALOG_FILE = DATA / "bandai_catalog.json"
HISTORY_LOCK = threading.Lock()
CARD_CACHE: dict[str, tuple[float, dict]] = {}
MARKET_CACHE: tuple[float, dict] | None = None
POP_CACHE: tuple[float, dict] | None = None
BANDAI_SEARCH_CACHE: dict[str, tuple[float, dict]] = {}
BANDAI_ALL_CACHE: tuple[float, list[dict]] | None = None
MERCARI_CACHE: dict[str, tuple[float, dict]] = {}
WATCHLIST = [
    "OP05-119",
    "OP01-003",
    "OP06-118",
    "OP09-119",
    "OP04-112",
    "OP01-025",
    "OP05-067",
    "OP05-069",
    "OP02-013",
    "OP03-122",
    "OP01-121",
    "OP06-086",
]
SCRYDEX_API_KEY = os.environ.get("SCRYDEX_API_KEY", "")
SCRYDEX_TEAM_ID = os.environ.get("SCRYDEX_TEAM_ID", "")
SCRYDEX = "https://api.scrydex.com/onepiece/v1"


def official_image(code: str) -> str:
    return f"https://en.onepiece-cardgame.com/images/cardlist/card/{code}.png"


DEMO_CATALOG = [
    {"id": "OP01-003", "name": "Monkey.D.Luffy", "rarity": "Leader", "character": "luffy"},
    {"id": "OP02-062", "name": "Monkey.D.Luffy", "rarity": "Leader", "character": "luffy"},
    {"id": "OP05-060", "name": "Monkey.D.Luffy", "rarity": "Leader", "character": "luffy"},
    {"id": "OP05-119", "name": "Monkey.D.Luffy", "rarity": "Secret Rare", "character": "luffy"},
    {"id": "OP07-109", "name": "Monkey.D.Luffy", "rarity": "Super Rare", "character": "luffy"},
    {"id": "OP09-061", "name": "Monkey.D.Luffy", "rarity": "Leader", "character": "luffy"},
    {"id": "OP09-119", "name": "Monkey.D.Luffy", "rarity": "Secret Rare", "character": "luffy"},
    {"id": "OP13-118", "name": "Monkey.D.Luffy", "rarity": "Secret Rare", "character": "luffy"},
    {"id": "OP01-001", "name": "Roronoa Zoro", "rarity": "Leader", "character": "zoro"},
    {"id": "OP01-025", "name": "Roronoa Zoro", "rarity": "Super Rare", "character": "zoro"},
    {"id": "OP06-118", "name": "Roronoa Zoro", "rarity": "Secret Rare", "character": "zoro"},
    {"id": "OP01-016", "name": "Nami", "rarity": "Rare", "character": "nami"},
    {"id": "OP02-013", "name": "Portgas.D.Ace", "rarity": "Super Rare", "character": "ace"},
    {"id": "OP05-069", "name": "Trafalgar Law", "rarity": "Super Rare", "character": "law"},
    {"id": "OP01-121", "name": "Yamato", "rarity": "Secret Rare", "character": "yamato"},
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,zh-CN;q=0.7",
    }
)

ALIASES = {
    "路飞": "luffy",
    "路費": "luffy",
    "路费": "luffy",
    "鲁夫": "luffy",
    "ルフィ": "luffy",
    "モンキー": "luffy",
    "索隆": "zoro",
    "ゾロ": "zoro",
    "娜美": "nami",
    "ナミ": "nami",
    "罗": "law",
    "ロー": "law",
    "艾斯": "ace",
    "エース": "ace",
    "山治": "sanji",
    "サンジ": "sanji",
}

SNK_ALIASES = {
    "luffy": "ルフィ",
    "路飞": "ルフィ",
    "路費": "ルフィ",
    "路费": "ルフィ",
    "鲁夫": "ルフィ",
    "ルフィ": "ルフィ",
    "zoro": "ゾロ",
    "索隆": "ゾロ",
    "ゾロ": "ゾロ",
    "nami": "ナミ",
    "娜美": "ナミ",
    "ナミ": "ナミ",
    "ace": "エース",
    "艾斯": "エース",
    "エース": "エース",
    "sanji": "サンジ",
    "山治": "サンジ",
    "サンジ": "サンジ",
    "law": "ロー",
    "罗": "ロー",
    "ロー": "ロー",
    "shanks": "シャンクス",
    "香克斯": "シャンクス",
    "シャンクス": "シャンクス",
    "hancock": "ハンコック",
    "汉库克": "ハンコック",
    "漢庫克": "ハンコック",
    "ハンコック": "ハンコック",
    "robin": "ロビン",
    "罗宾": "ロビン",
    "羅賓": "ロビン",
    "ロビン": "ロビン",
    "chopper": "チョッパー",
    "乔巴": "チョッパー",
    "喬巴": "チョッパー",
    "チョッパー": "チョッパー",
    "sabo": "サボ",
    "萨博": "サボ",
    "サボ": "サボ",
    "kaido": "カイドウ",
    "凯多": "カイドウ",
    "カイドウ": "カイドウ",
    "yamato": "ヤマト",
    "大和": "ヤマト",
    "ヤマト": "ヤマト",
    "mihawk": "ミホーク",
    "鹰眼": "ミホーク",
    "鷹眼": "ミホーク",
    "ミホーク": "ミホーク",
    "teach": "ティーチ",
    "黑胡子": "ティーチ",
    "黒ひげ": "ティーチ",
    "ティーチ": "ティーチ",
    "boa": "ハンコック",
    "perona": "ペローナ",
    "佩罗娜": "ペローナ",
    "ペローナ": "ペローナ",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_data_dir() -> None:
    DATA.mkdir(exist_ok=True)


def read_history() -> list[dict]:
    ensure_data_dir()
    if not HISTORY_FILE.exists():
        return []
    rows = []
    with HISTORY_LOCK:
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def read_jsonl(path: Path) -> list[dict]:
    ensure_data_dir()
    if not path.exists():
        return []
    rows = []
    with HISTORY_LOCK:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    ensure_data_dir()
    with HISTORY_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_snapshot(card: dict) -> dict | None:
    prices = card.get("prices") or []
    if not prices:
        return None
    highest = max(prices, key=lambda item: float(item.get("usd") or 0))
    row = {
        "code": card["code"],
        "name": card.get("name") or card["code"],
        "image": card.get("image"),
        "at": now_iso(),
        "usd": highest.get("usd"),
        "print": highest.get("print"),
    }
    ensure_data_dir()
    with HISTORY_LOCK:
        with HISTORY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def history_for(code: str, rows: list[dict] | None = None) -> list[dict]:
    matches = [row for row in (rows or read_history()) if row.get("code") == code and row.get("usd") is not None]
    compact = []
    for row in matches:
        if not compact or compact[-1]["usd"] != row["usd"]:
            compact.append(row)
        else:
            compact[-1] = row
    return compact[-30:]


def trend_for(code: str, current: float | None, rows: list[dict]) -> dict:
    history = history_for(code, rows)
    previous = next((row for row in reversed(history) if row.get("usd") != current), None)
    if not previous or not current:
        return {"percent": None, "previous": None, "status": "collecting"}
    percent = round((current - previous["usd"]) / previous["usd"] * 100, 1)
    return {"percent": percent, "previous": previous["usd"], "status": "ready"}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_query(raw: str) -> str:
    q = clean(unquote(raw))
    low = q.lower().replace("_", "-")
    for key, value in ALIASES.items():
        if key in q:
            return value
    promo = re.search(r"\b(p)-?(\d{1,3})\b", low)
    if promo:
        return f"P-{int(promo.group(2)):03d}"
    code = re.search(r"\b([a-z]{1,3})\s*-?\s*(\d{1,2})\s*-?\s*(\d{1,3})\b", low)
    if code:
        prefix = code.group(1).upper()
        set_no = int(code.group(2))
        card_no = int(code.group(3))
        return f"{prefix}{set_no:02d}-{card_no:03d}"
    code = re.search(r"\b([a-z]{1,3}\d{2})-(\d{1,3})\b", low)
    if code:
        return f"{code.group(1).upper()}-{int(code.group(2)):03d}"
    return low


def fetch(url: str, timeout: int = 12) -> tuple[str | None, dict]:
    started = time.perf_counter()
    meta = {"url": url, "fetched_at": now_iso(), "ok": False, "status": None, "error": None}
    try:
        response = SESSION.get(url, timeout=timeout)
        meta["status"] = response.status_code
        meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            meta["error"] = f"HTTP {response.status_code}"
            return None, meta
        meta["ok"] = True
        return response.text, meta
    except requests.RequestException as exc:
        meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        meta["error"] = str(exc)
        return None, meta


def image_url_from_code(code: str) -> str:
    set_code = code.split("-")[0]
    return f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set_code}/{code}_EN.webp"


def parse_bandai_search(query: str) -> dict:
    normalized = normalize_query(query)
    cached = BANDAI_SEARCH_CACHE.get(normalized)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    url = f"https://asia-en.onepiece-cardgame.com/cardlist/?freewords={quote_plus(normalized)}&search=true"
    html, meta = fetch(url, timeout=30)
    cards = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for node in soup.select(".modalCol"):
            variant_id = node.get("id", "")
            name_node = node.select_one(".cardName")
            image_node = node.select_one("img[data-src]")
            info = [clean(span.get_text(" ", strip=True)) for span in node.select("dt .infoCol span")]
            if not variant_id or not name_node or not image_node:
                continue
            code = re.sub(r"_[a-z]\d+$", "", variant_id, flags=re.I)
            name = clean(name_node.get_text(" ", strip=True))
            haystack = f"{variant_id} {code} {name}".lower()
            if normalized and normalized.lower() not in haystack:
                continue
            image_source = image_node.get("data-src", "").replace("../", "https://asia-en.onepiece-cardgame.com/")
            image = f"/api/image?url={quote_plus(image_source)}"
            cards.append(
                {
                    "variant_id": variant_id,
                    "code": code,
                    "name": name,
                    "rarity": info[1] if len(info) > 1 else "",
                    "card_type": info[2] if len(info) > 2 else "",
                    "image": image,
                    "official_url": url,
                }
            )
    result = {
        "query": query,
        "normalized": normalized,
        "fetched_at": now_iso(),
        "status": "ok" if cards else ("blocked-or-empty" if html else "failed"),
        "source": {"name": "Bandai official One Piece Card List", **meta},
        "cards": cards,
    }
    BANDAI_SEARCH_CACHE[normalized] = (time.time(), result)
    return result


def bandai_card_from_node(node, source_url: str, series_name: str = "") -> dict | None:
    variant_id = node.get("id", "")
    name_node = node.select_one(".cardName")
    image_node = node.select_one("img[data-src]")
    info = [clean(span.get_text(" ", strip=True)) for span in node.select("dt .infoCol span")]
    if not variant_id or not name_node or not image_node:
        return None
    code = re.sub(r"_[a-z]\d+$", "", variant_id, flags=re.I)
    image_source = image_node.get("data-src", "").replace("../", "https://asia-en.onepiece-cardgame.com/")
    return {
        "variant_id": variant_id,
        "code": code,
        "name": clean(name_node.get_text(" ", strip=True)),
        "rarity": info[1] if len(info) > 1 else "",
        "card_type": info[2] if len(info) > 2 else "",
        "series": series_name,
        "image": f"/api/image?url={quote_plus(image_source)}",
        "official_url": source_url,
    }


def parse_bandai_all_cards() -> list[dict]:
    global BANDAI_ALL_CACHE
    if BANDAI_ALL_CACHE and time.time() - BANDAI_ALL_CACHE[0] < 3600:
        return BANDAI_ALL_CACHE[1]
    if BANDAI_CATALOG_FILE.exists() and time.time() - BANDAI_CATALOG_FILE.stat().st_mtime < 86400:
        try:
            cards = json.loads(BANDAI_CATALOG_FILE.read_text(encoding="utf-8"))
            BANDAI_ALL_CACHE = (time.time(), cards)
            return cards
        except (OSError, json.JSONDecodeError):
            pass
    url = "https://asia-en.onepiece-cardgame.com/cardlist/"
    html, _meta = fetch(url, timeout=30)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    series_options = []
    for option in soup.select('select[name="series"] option[value]'):
        value = option.get("value", "").strip()
        if value:
            series_options.append((value, clean(option.get_text(" ", strip=True))))

    def fetch_series(option: tuple[str, str]) -> list[dict]:
        value, name = option
        try:
            response = SESSION.post(url, data={"search": "true", "series": value}, timeout=35)
            response.raise_for_status()
        except requests.RequestException:
            return []
        page = BeautifulSoup(response.text, "html.parser")
        return [card for node in page.select(".modalCol") if (card := bandai_card_from_node(node, url, name))]

    cards_by_variant = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for cards in pool.map(fetch_series, series_options):
            for card in cards:
                cards_by_variant.setdefault(card["variant_id"], card)
    cards = sorted(cards_by_variant.values(), key=lambda card: (card["code"], card["variant_id"]))
    DATA.mkdir(parents=True, exist_ok=True)
    BANDAI_CATALOG_FILE.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    BANDAI_ALL_CACHE = (time.time(), cards)
    return cards


def bandai_catalog_page(query: str, page: int, per_page: int) -> dict:
    cards = parse_bandai_all_cards()
    normalized = normalize_query(query)
    if normalized:
        needle = normalized.lower()
        cards = [
            card for card in cards
            if needle in f'{card["code"]} {card["variant_id"]} {card["name"]} {card["series"]}'.lower()
        ]
    total = len(cards)
    page = max(1, page)
    per_page = max(24, min(per_page, 120))
    start = (page - 1) * per_page
    return {
        "status": "ok",
        "query": query,
        "normalized": normalized,
        "fetched_at": now_iso(),
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
        "cards": cards[start:start + per_page],
        "source": {"name": "Bandai official One Piece Card List", "url": "https://asia-en.onepiece-cardgame.com/cardlist/"},
    }


def parse_limitless_search(query: str) -> dict:
    normalized = normalize_query(query)
    if re.fullmatch(r"(?:[A-Z]{1,4}\d{2}-\d{3}|P-\d{3})", normalized):
        return {
            "query": query,
            "normalized": normalized,
            "results": [{"code": normalized, "url": f"{LIMITLESS}/cards/{normalized}", "image": image_url_from_code(normalized)}],
            "source": {"name": "Limitless One Piece", "url": f"{LIMITLESS}/cards/{normalized}", "status": "direct-code"},
        }

    url = f"{LIMITLESS}/cards?q={quote_plus(normalized)}"
    html, meta = fetch(url)
    results: list[dict] = []
    if html:
        for code in dict.fromkeys(re.findall(r"/cards/([A-Z]{2,4}\d{2}-\d{3}|P-\d{3})", html)):
            results.append({"code": code, "url": f"{LIMITLESS}/cards/{code}", "image": image_url_from_code(code)})
            if len(results) >= 24:
                break
        if not results:
            for set_code, number in dict.fromkeys(re.findall(r"/one-piece/([A-Z]{1,4}\d{2}|P)/([A-Z]{2,4}\d{2}-\d{3}|P-\d{3})_EN\.webp", html)):
                results.append({"code": number, "url": f"{LIMITLESS}/cards/{number}", "image": image_url_from_code(number)})
                if len(results) >= 24:
                    break
    return {"query": query, "normalized": normalized, "results": results, "source": {"name": "Limitless One Piece", **meta}}


def parse_limitless_card(code: str, use_cache: bool = True) -> dict:
    code = normalize_query(code)
    cached = CARD_CACHE.get(code)
    if use_cache and cached and time.time() - cached[0] < 300:
        return cached[1]
    url = f"{LIMITLESS}/cards/{code}"
    html, meta = fetch(url)
    source = {"name": "Limitless One Piece", **meta}
    if not html:
        return {"ok": False, "source": source, "error": meta.get("error") or "no html"}

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [clean(x) for x in text.splitlines() if clean(x)]
    image_match = re.search(r"https://limitlesstcg[^\"]+?%s_EN\.webp" % re.escape(code), html)
    image = image_match.group(0).replace("\\/", "/") if image_match else image_url_from_code(code)

    name = None
    for idx, line in enumerate(lines):
        if line == code and idx > 0:
            name = lines[idx - 1]
            break
        if line.endswith(code) and len(line) > len(code):
            name = line[: -len(code)].strip()
            break
    if not name:
        title = soup.find("title")
        name = clean(title.get_text().split("(")[0]) if title else code

    subtitle = ""
    for idx, line in enumerate(lines):
        if line == code and idx + 1 < len(lines):
            subtitle = lines[idx + 1]
            break

    details = {
        "name": name,
        "code": code,
        "subtitle": subtitle,
        "image": image,
        "url": url,
        "source": source,
        "prices": [],
        "leaders": [],
        "deck_appearances": [],
    }

    prices: list[dict] = []
    for row in soup.select("table.card-prints-versions tr"):
        usd_node = row.select_one(".card-price.usd")
        eur_node = row.select_one(".card-price.eur")
        if not usd_node or not eur_node:
            continue
        label_node = row.select_one("td:first-child")
        variant_node = row.select_one(".prints-table-card-number")
        set_name = clean(label_node.get_text(" ", strip=True)) if label_node else "Print"
        variant = clean(variant_node.get_text(" ", strip=True)) if variant_node else ""
        if variant and set_name.lower().endswith(variant.lower()):
            set_name = clean(set_name[: -len(variant)])
        if variant.lower() == "aa":
            variant = "Alternate Art"
        label = f"{set_name} · {variant}" if variant else f"{set_name} · Standard"
        prices.append(
            {
                "print": label,
                "usd": float(usd_node.get_text(strip=True).replace("$", "").replace(",", "")),
                "eur": float(eur_node.get_text(strip=True).replace("€", "").replace(",", "")),
                "source": "Limitless/TCGplayer/Cardmarket",
            }
        )
    details["prices"] = prices[:12]

    if "Leader Count" in text:
        leader_block = text.split("Leader Count", 1)[1].split("Price History", 1)[0]
        leader_matches = re.findall(r"([A-Za-z0-9'. -]+)\s+([A-Z]{2,3}\d{2}-\d{3})\s+(\d+)", leader_block)
        details["leaders"] = [
            {"leader": clean(name), "code": c, "count": int(count)} for name, c, count in leader_matches[:10]
        ]

    card_type_line = next((line for line in lines if " • " in line and any(t in line for t in ["Leader", "Character", "Event", "Stage"])), "")
    details["card_type_line"] = card_type_line
    details["effect"] = ""
    for idx, line in enumerate(lines):
        if line.startswith("[") and idx > 15:
            details["effect"] = line
            break
    result = {"ok": True, "card": details}
    CARD_CACHE[code] = (time.time(), result)
    return result


def summarize_card(result: dict, rows: list[dict]) -> dict | None:
    if not result.get("ok"):
        return None
    card = result["card"]
    prices = card.get("prices") or []
    highest = max(prices, key=lambda item: float(item.get("usd") or 0), default={})
    current = highest.get("usd")
    return {
        "code": card["code"],
        "name": card.get("name") or card["code"],
        "image": card.get("image"),
        "url": card.get("url"),
        "usd": current,
        "print": highest.get("print") or "No price",
        "trend": trend_for(card["code"], current, rows),
    }


def overview() -> dict:
    previous_rows = read_history()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(parse_limitless_card, WATCHLIST))
    cards = []
    for result in results:
        if result.get("ok"):
            append_snapshot(result["card"])
        summary = summarize_card(result, previous_rows)
        if summary:
            cards.append(summary)
    priced = [card for card in cards if card.get("usd") is not None]
    gainers = sorted(
        [card for card in priced if card["trend"]["percent"] is not None],
        key=lambda card: card["trend"]["percent"],
        reverse=True,
    )
    losers = sorted(gainers, key=lambda card: card["trend"]["percent"])
    return {
        "fetched_at": now_iso(),
        "watchlist_count": len(cards),
        "cards": cards,
        "rankings": {
            "high_price": sorted(priced, key=lambda card: card["usd"], reverse=True)[:8],
            "gainers": gainers[:8],
            "losers": losers[:8],
        },
        "psa": {
            "status": "source-restricted",
            "note": "PSA public search currently returns HTTP 403 to the local collector. No population ranking is fabricated.",
        },
    }


def parse_ebay(query: str) -> dict:
    normalized = normalize_query(query)
    search = f"One Piece Card Game {normalized}"
    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(search)}&LH_Sold=1&LH_Complete=1"
    html, meta = fetch(url)
    source = {"name": "eBay sold search", **meta}
    items = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for node in soup.select(".s-item"):
            title = clean(node.select_one(".s-item__title").get_text(" ")) if node.select_one(".s-item__title") else ""
            price = clean(node.select_one(".s-item__price").get_text(" ")) if node.select_one(".s-item__price") else ""
            link = node.select_one("a.s-item__link")
            href = link["href"] if link and link.has_attr("href") else ""
            if title and price and "Shop on eBay" not in title:
                items.append({"title": title, "price": price, "url": href.split("?")[0]})
            if len(items) >= 8:
                break
    numbers = []
    for item in items:
        found = re.search(r"\$([\d,]+(?:\.\d{2})?)", item["price"])
        if found:
            numbers.append(float(found.group(1).replace(",", "")))
    stats = {}
    if numbers:
        stats = {
            "count": len(numbers),
            "low": min(numbers),
            "high": max(numbers),
            "avg": round(sum(numbers) / len(numbers), 2),
        }
    status = "ok" if items else ("blocked-or-empty" if html else "failed")
    return {"status": status, "source": source, "query": search, "items": items, "stats": stats}


def parse_snkrdunk(query: str) -> dict:
    normalized = normalize_query(query)
    search = f"one piece {normalized}"
    urls = [
        f"https://snkrdunk.com/en/search/result?keyword={quote_plus(search)}",
        f"https://snkrdunk.com/en/magazine/?s={quote_plus(search)}",
    ]
    outputs = []
    for url in urls:
        html, meta = fetch(url)
        entry = {"name": "SNKRDUNK", **meta, "items": []}
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                title = clean(a.get_text(" "))
                href = a["href"]
                if normalized.lower().replace("-", "")[:4] in (title + href).lower().replace("-", ""):
                    if href.startswith("/"):
                        href = "https://snkrdunk.com" + href
                    entry["items"].append({"title": title[:160] or href, "url": href})
                if len(entry["items"]) >= 5:
                    break
        outputs.append(entry)
    best = next((x for x in outputs if x["items"]), outputs[0])
    return {"status": "ok" if best["items"] else "blocked-or-empty", "source": best, "query": search, "items": best["items"]}


def normalize_snkrdunk_query(raw: str) -> str:
    query = clean(unquote(raw))
    lowered = query.lower()
    for key, value in SNK_ALIASES.items():
        if key.lower() in lowered or key in query:
            return value
    return query


def catalog_query(raw: str) -> str:
    query = clean(unquote(raw))
    lowered = query.lower()
    alias_map = {
        "路飞": "luffy", "路費": "luffy", "路费": "luffy", "ルフィ": "luffy",
        "索隆": "zoro", "ゾロ": "zoro", "娜美": "nami", "ナミ": "nami",
        "艾斯": "ace", "エース": "ace", "罗": "law", "ロー": "law",
        "大和": "yamato", "ヤマト": "yamato",
    }
    for key, value in alias_map.items():
        if key in query:
            return value
    return lowered


def scrydex_headers() -> dict:
    return {"X-Api-Key": SCRYDEX_API_KEY, "X-Team-ID": SCRYDEX_TEAM_ID, "Accept": "application/json"}


def demo_card(card: dict) -> dict:
    return {
        "id": card["id"],
        "name": card["name"],
        "rarity": card["rarity"],
        "image": official_image(card["id"]),
        "official_url": f"https://en.onepiece-cardgame.com/cardlist/?freewords={quote_plus(card['id'])}&search=true",
        "raw_market": None,
        "trend_7d": None,
        "pop_total": None,
        "psa10_rate": None,
        "source": "Bandai official card list demo",
    }


def provider_search(query: str) -> dict:
    normalized = catalog_query(query)
    if not SCRYDEX_API_KEY or not SCRYDEX_TEAM_ID:
        matches = []
        for card in DEMO_CATALOG:
            haystack = f"{card['id']} {card['name']} {card['character']}".lower()
            if not normalized or normalized in haystack:
                matches.append(demo_card(card))
        return {
            "mode": "demo",
            "provider": "Bandai official card list demo",
            "note": "Configure SCRYDEX_API_KEY and SCRYDEX_TEAM_ID to enable licensed full catalog, raw prices, trends, and pop reports.",
            "query": query,
            "normalized": normalized,
            "cards": matches,
            "fetched_at": now_iso(),
        }

    url = f"{SCRYDEX}/cards?q={quote_plus(normalized)}&page_size=250&include=prices"
    started = time.perf_counter()
    response = SESSION.get(url, headers=scrydex_headers(), timeout=25)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data") or payload.get("cards") or payload.get("results") or []
    cards = []
    for card in rows:
        variants = card.get("variants") or []
        variant_prices = [price for variant in variants for price in (variant.get("prices") or []) if price.get("type") == "raw"]
        raw = max(variant_prices, key=lambda item: item.get("market") or 0, default={})
        cards.append({
            "id": card.get("id"),
            "name": card.get("name"),
            "rarity": card.get("rarity"),
            "image": ((card.get("images") or [{}])[0]).get("medium") or official_image(card.get("id", "")),
            "official_url": f"https://en.onepiece-cardgame.com/cardlist/?freewords={quote_plus(card.get('id', ''))}&search=true",
            "raw_market": raw.get("market"),
            "trend_7d": ((raw.get("trends") or {}).get("days_7") or {}).get("percent_change"),
            "pop_total": card.get("pop_total"),
            "psa10_rate": card.get("psa10_rate"),
            "source": "Scrydex licensed API",
        })
    return {
        "mode": "live",
        "provider": "Scrydex licensed API",
        "query": query,
        "normalized": normalized,
        "cards": cards,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "fetched_at": now_iso(),
    }


def provider_market() -> dict:
    search = provider_search("")
    cards = search["cards"]
    priced = [card for card in cards if card.get("raw_market") is not None]
    trended = [card for card in priced if card.get("trend_7d") is not None]
    return {
        **search,
        "rankings": {
            "popular": cards[:12],
            "gainers": sorted(trended, key=lambda card: card["trend_7d"], reverse=True)[:12],
            "losers": sorted(trended, key=lambda card: card["trend_7d"])[:12],
            "price": sorted(priced, key=lambda card: card["raw_market"], reverse=True)[:12],
        },
    }


def snkrdunk_trend(product_id: str, price_jpy: int | None, rows: list[dict]) -> dict:
    matches = [row for row in rows if row.get("product_id") == product_id and row.get("price_jpy")]
    previous = next((row for row in reversed(matches) if row.get("price_jpy") != price_jpy), None)
    if not previous or not price_jpy:
        return {"percent": None, "previous_jpy": None, "status": "collecting"}
    percent = round((price_jpy - previous["price_jpy"]) / previous["price_jpy"] * 100, 1)
    return {"percent": percent, "previous_jpy": previous["price_jpy"], "status": "ready"}


def snkrdunk_condition_sales(product_id: str, condition_id: int, condition: str) -> dict:
    all_sales = []
    payload = {}
    url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-history?page=1&per_page=20&condition_id={condition_id}"
    html, _meta = fetch(url, timeout=10)
    if html:
        try:
            payload = json.loads(html)
        except json.JSONDecodeError:
            payload = {}
        for row in payload.get("history", []):
            if row.get("price"):
                all_sales.append({"condition": condition, **row})
    if not all_sales:
        return {"sales_count": 0, "sample_limit": 20, "sample_capped": False, "listing_min_jpy": payload.get("minPrice"), "latest_jpy": None, "trend": {"percent": None, "status": "collecting"}}
    latest = all_sales[0]
    previous = next((row for row in all_sales[1:] if row.get("price") != latest["price"]), None)
    percent = None
    if previous:
        percent = round((latest["price"] - previous["price"]) / previous["price"] * 100, 1)
    return {
        "sales_count": len(all_sales),
        "sample_limit": 20,
        "sample_capped": len(all_sales) >= 20,
        "listing_min_jpy": payload.get("minPrice"),
        "latest_jpy": latest["price"],
        "latest_at": latest.get("date"),
        "condition": latest["condition"],
        "trend": {
            "percent": percent,
            "previous_jpy": previous.get("price") if previous else None,
            "status": "ready" if previous else "collecting",
        },
    }


def snkrdunk_psa10_listings(product_id: str) -> dict:
    url = f"https://snkrdunk.com/v1/apparels/{product_id}/used?perPage=100&page=1&sizeId=0&isSaleOnly=true"
    html, meta = fetch(url, timeout=12)
    listings = []
    if html:
        try:
            payload = json.loads(html)
        except json.JSONDecodeError:
            payload = {}
        for row in payload.get("apparelUsedItems", []):
            if row.get("isDisplaySold"):
                continue
            if clean(row.get("displayShortConditionTitle")) != "PSA10":
                continue
            price = row.get("price")
            if not price:
                continue
            listing_id = row.get("id")
            size = row.get("size") or {}
            listings.append(
                {
                    "id": listing_id,
                    "price_jpy": int(price),
                    "condition": "PSA10",
                    "size_label": size.get("localizedName") or "",
                    "image": ((row.get("primaryPhoto") or {}).get("imageUrl") or ""),
                    "url": f"https://snkrdunk.com/apparels/{product_id}/used/{listing_id}?slide=right" if listing_id else f"https://snkrdunk.com/apparels/{product_id}/used?slide=right",
                    "updated_at": row.get("updatedAt"),
                }
            )
    return {
        "status": "ok" if listings else ("empty" if html else "failed"),
        "source": meta,
        "sample_limit": 100,
        "sample_capped": len(listings) >= 100,
        "count": len(listings),
        "listings": sorted(listings, key=lambda item: item["price_jpy"]),
    }


def snkrdunk_live_naked_sales(product_id: str) -> dict:
    return snkrdunk_condition_sales(product_id, 18, "A")


def snkrdunk_live_psa10_sales(product_id: str) -> dict:
    sales = snkrdunk_condition_sales(product_id, 22, "PSA10")
    listing_payload = snkrdunk_psa10_listings(product_id)
    sales["listing_count"] = listing_payload["count"]
    sales["listing_sample_capped"] = listing_payload["sample_capped"]
    sales["listings"] = listing_payload["listings"]
    if listing_payload["listings"]:
        sales["listing_min_jpy"] = listing_payload["listings"][0]["price_jpy"]
    return sales


def parse_snkrdunk_search(query: str) -> dict:
    normalized = normalize_snkrdunk_query(query)
    url = (
        "https://snkrdunk.com/search?"
        f"brandIds=onepiece&keywords={quote_plus(normalized)}&searchCategoryIds=6%2F33&sort=popular"
    )
    html, meta = fetch(url, timeout=20)
    previous_rows = read_jsonl(SNK_HISTORY_FILE)
    cards = []
    pages = [html] if html else []
    if html:
        page_numbers = [int(value) for value in re.findall(r"(?:amp;)?page=(\d+)", html)]
        max_page = min(max(page_numbers, default=1), 10)
        if max_page > 1:
            with ThreadPoolExecutor(max_workers=6) as pool:
                extra_pages = list(pool.map(lambda page: fetch(f"{url}&page={page}", timeout=20)[0], range(2, max_page + 1)))
            pages.extend(page for page in extra_pages if page)
    if pages:
        for page_html in pages:
            soup = BeautifulSoup(page_html, "html.parser")
            seen = {card["product_id"] for card in cards}
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"]
                match = re.fullmatch(r"(?:https://snkrdunk\.com)?/apparels/(\d+)", href)
                if not match or match.group(1) in seen:
                    continue
                text = clean(anchor.get_text(" ", strip=True))
                price_match = re.search(r"¥\s*([\d,]+)", text)
                code_match = re.search(r"\[([A-Z]{1,4}-?\d{2,3}-\d{3}|[A-Z]{1,4}-\d{3})\]", text)
                rank_match = re.match(r"(\d+)\s+", text)
                image_node = anchor.find("img")
                product_id = match.group(1)
                price_jpy = int(price_match.group(1).replace(",", "")) if price_match else None
                title = re.sub(r"^\d+\s+", "", text)
                title = re.sub(r"\s*¥\s*[\d,]+\s*$", "", title)
                card = {
                    "product_id": product_id,
                    "rank": int(rank_match.group(1)) if rank_match else len(cards) + 1,
                    "title": title,
                    "code": code_match.group(1) if code_match else "",
                    "price_jpy": price_jpy,
                    "image": image_node.get("src") if image_node else "",
                    "url": f"https://snkrdunk.com/apparels/{product_id}",
                    "sales_url": f"https://snkrdunk.com/apparels/{product_id}/sales-histories",
                }
                card["trend"] = snkrdunk_trend(product_id, price_jpy, previous_rows)
                cards.append(card)
                seen.add(product_id)
                append_jsonl(
                    SNK_HISTORY_FILE,
                    {"product_id": product_id, "at": now_iso(), "price_jpy": price_jpy, "title": title, "code": card["code"]},
                )
                if len(cards) >= 200:
                    break
            if len(cards) >= 200:
                break
    with ThreadPoolExecutor(max_workers=20) as pool:
        live_sales = list(pool.map(lambda card: snkrdunk_live_naked_sales(card["product_id"]), cards))
        psa10_sales = list(pool.map(lambda card: snkrdunk_live_psa10_sales(card["product_id"]), cards))
    for card, sales, psa10 in zip(cards, live_sales, psa10_sales):
        card["naked_sales"] = sales
        card["psa10_sales"] = psa10
        card["trend"] = psa10["trend"]
    return {
        "query": query,
        "normalized": normalized,
        "fetched_at": now_iso(),
        "status": "ok" if cards else ("blocked-or-empty" if html else "failed"),
        "source": {"name": "SNKRDUNK One Piece singles", **meta},
        "cards": cards,
    }


def snkrdunk_market_overview() -> dict:
    global MARKET_CACHE
    if MARKET_CACHE and time.time() - MARKET_CACHE[0] < 300:
        return MARKET_CACHE[1]
    payload = parse_snkrdunk_search("")
    cards = payload["cards"]
    with_sales = [card for card in cards if card.get("psa10_sales", {}).get("sales_count")]
    with_trend = [card for card in with_sales if card.get("trend", {}).get("percent") is not None]
    result = {
        "fetched_at": now_iso(),
        "source": payload["source"],
        "card_count": len(cards),
        "cards": cards,
        "rankings": {
            "popular": cards[:12],
            "gainers": sorted(with_trend, key=lambda card: card["trend"]["percent"], reverse=True)[:12],
            "losers": sorted(with_trend, key=lambda card: card["trend"]["percent"])[:12],
            "active": sorted(with_sales, key=lambda card: card["psa10_sales"]["sales_count"], reverse=True)[:12],
        },
    }
    MARKET_CACHE = (time.time(), result)
    return result


def population_overview() -> dict:
    global POP_CACHE
    if POP_CACHE and time.time() - POP_CACHE[0] < 1800:
        return POP_CACHE[1]
    codes = ["OP05-119", "OP06-118", "OP01-003", "OP09-119", "OP01-025", "OP02-013", "OP01-121", "OP03-122"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(parse_pricecharting_population, codes))
    variants = []
    for payload in payloads:
        for variant in payload.get("variants", []):
            if variant.get("psa_total") or variant.get("cgc_total"):
                variant["code"] = payload["query"]
                variant["graded_total"] = (variant.get("psa_total") or 0) + (variant.get("cgc_total") or 0)
                variants.append(variant)
    result = {
        "fetched_at": now_iso(),
        "status": "ok" if variants else "empty",
        "note": "Fallback population leaderboard from PriceCharting PSA/CGC pages. PSA official search remains restricted.",
        "variants": sorted(variants, key=lambda item: item["graded_total"], reverse=True)[:16],
    }
    POP_CACHE = (time.time(), result)
    return result


def parse_snkrdunk_sales(product_id: str) -> dict:
    items = []
    charts = {}
    listing_min = {}
    meta = {}
    for condition_id, condition in [(18, "A"), (22, "PSA10")]:
        url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-history?page=1&per_page=100&condition_id={condition_id}"
        html, meta = fetch(url)
        if html:
            try:
                payload = json.loads(html)
            except json.JSONDecodeError:
                payload = {}
            listing_min[condition] = payload.get("minPrice")
            for row in payload.get("history", []):
                if row.get("price"):
                    items.append({"condition": condition, **row})
        chart_url = f"https://snkrdunk.com/v1/apparels/{product_id}/sales-chart/used?range=all&salesChartOptionId={condition_id}"
        chart_html, _chart_meta = fetch(chart_url)
        try:
            charts[condition] = json.loads(chart_html).get("points", []) if chart_html else []
        except json.JSONDecodeError:
            charts[condition] = []
    grouped_counts = Counter((item["condition"], item.get("date"), item.get("price")) for item in items)
    for item in items:
        item["same_time_price_records"] = grouped_counts[(item["condition"], item.get("date"), item.get("price"))]
    naked = [item for item in items if item["condition"] == "A"]
    psa10 = [item for item in items if item["condition"] == "PSA10"]
    prices = [item.get("price") for item in naked if item.get("price")]
    psa10_prices = [item.get("price") for item in psa10 if item.get("price")]
    return {
        "status": "ok" if items else "empty",
        "product_id": product_id,
        "source": f"https://snkrdunk.com/apparels/{product_id}/sales-histories",
        "items": items[:200],
        "charts": charts,
        "record_note": "SNKRDUNK does not expose order quantity. Repeated rows are public sale records; matching displayed time and price does not prove one buyer or one batch order.",
        "naked": {
            "sales_count": len(naked),
            "sample_limit": 100,
            "sample_capped": len(naked) >= 100,
            "listing_min_jpy": listing_min.get("A"),
            "latest_jpy": naked[0].get("price") if naked else None,
            "low_jpy": min(prices) if prices else None,
            "high_jpy": max(prices) if prices else None,
        },
        "psa10": {
            "sales_count": len(psa10),
            "sample_limit": 100,
            "sample_capped": len(psa10) >= 100,
            "listing_min_jpy": listing_min.get("PSA10"),
            "latest_jpy": psa10[0].get("price") if psa10 else None,
            "low_jpy": min(psa10_prices) if psa10_prices else None,
            "high_jpy": max(psa10_prices) if psa10_prices else None,
        },
    }


def parse_psa(query: str) -> dict:
    normalized = normalize_query(query)
    search = f"2022 2023 2024 One Piece {normalized} PSA"
    url = f"https://www.psacard.com/search/?q={quote_plus(search)}"
    html, meta = fetch(url)
    source = {"name": "PSA search", **meta}
    items = []
    pop = {}
    if html:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ")
        p10 = re.search(r"PSA\s*10\s*(?:pop|population)?\s*[:#]?\s*([\d,]+)", text, re.I)
        total = re.search(r"Total\s*PSA\s*(?:pop|population)?\s*[:#]?\s*([\d,]+)", text, re.I)
        if p10:
            pop["psa10"] = int(p10.group(1).replace(",", ""))
        if total:
            pop["total"] = int(total.group(1).replace(",", ""))
        if pop.get("psa10") and pop.get("total"):
            pop["psa10_rate"] = round(pop["psa10"] / pop["total"] * 100, 1)
        for a in soup.find_all("a", href=True):
            title = clean(a.get_text(" "))
            href = a["href"]
            if normalized.split("-")[-1] in title or "one piece" in title.lower():
                if href.startswith("/"):
                    href = "https://www.psacard.com" + href
                items.append({"title": title[:160] or href, "url": href})
            if len(items) >= 6:
                break
    return {"status": "ok" if (items or pop) else ("blocked-or-empty" if html else "failed"), "source": source, "query": search, "items": items, "population": pop}


def parse_pricecharting_pop_page(url: str, title: str) -> dict:
    pop_url = url.replace("/game/", "/pop/item/")
    html, meta = fetch(pop_url)
    result = {"title": title, "url": pop_url, "source": meta, "psa10": None, "psa_total": None, "cgc10": None, "cgc_total": None}
    if not html:
        return result
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("table tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) < 4:
            continue
        if cells[0] == "10":
            result["psa10"] = int(cells[1].replace(",", "")) if cells[1].replace(",", "").isdigit() else None
            result["cgc10"] = int(cells[2].replace(",", "")) if cells[2].replace(",", "").isdigit() else None
        if cells[0] == "Total":
            result["psa_total"] = int(cells[1].replace(",", "")) if cells[1].replace(",", "").isdigit() else None
            result["cgc_total"] = int(cells[2].replace(",", "")) if cells[2].replace(",", "").isdigit() else None
    if result["psa10"] is not None and result["psa_total"]:
        result["psa10_rate"] = round(result["psa10"] / result["psa_total"] * 100, 1)
    return result


def parse_pricecharting_population(query: str) -> dict:
    normalized = normalize_query(query)
    url = f"https://www.pricecharting.com/search-products?type=prices&q={quote_plus(normalized)}"
    html, meta = fetch(url, timeout=20)
    variants = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        seen = set()
        pages = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/game/one-piece" not in href or normalized.lower() not in (href + anchor.get_text(" ")).lower():
                continue
            if href.startswith("/"):
                href = "https://www.pricecharting.com" + href
            if href in seen:
                continue
            seen.add(href)
            pages.append((href, clean(anchor.get_text(" ", strip=True)) or href.rsplit("/", 1)[-1]))
            if len(pages) >= 12:
                break
        with ThreadPoolExecutor(max_workers=8) as pool:
            variants = list(pool.map(lambda args: parse_pricecharting_pop_page(*args), pages))
    return {
        "status": "ok" if variants else ("blocked-or-empty" if html else "failed"),
        "query": normalized,
        "source": {"name": "PriceCharting PSA/CGC population fallback", **meta},
        "variants": variants,
    }


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def mercari_dpop(url: str, device_id: str) -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    header = {
        "typ": "dpop+jwt",
        "alg": "ES256",
        "jwk": {
            "crv": "P-256",
            "kty": "EC",
            "x": base64url(public.x.to_bytes(32, "big")),
            "y": base64url(public.y.to_bytes(32, "big")),
        },
    }
    payload = {"iat": int(time.time()), "jti": str(uuid.uuid4()), "htu": url, "htm": "POST", "uuid": device_id}
    signing_input = ".".join(
        base64url(json.dumps(part, separators=(",", ":")).encode("utf-8")) for part in (header, payload)
    )
    r, s = decode_dss_signature(key.sign(signing_input.encode("ascii"), ec.ECDSA(hashes.SHA256())))
    return f"{signing_input}.{base64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def mercari_search(query: str) -> dict:
    cached = MERCARI_CACHE.get(query)
    if cached and time.time() - cached[0] < 180:
        return cached[1]
    url = "https://api.mercari.jp/v2/entities:search"
    device_id = str(uuid.uuid4())
    body = {
        "userId": "",
        "config": {"responseToggles": ["QUERY_SUGGESTION_WEB_1"]},
        "pageSize": 40,
        "pageToken": "",
        "searchSessionId": uuid.uuid4().hex,
        "source": "BaseSerp",
        "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
        "thumbnailTypes": [],
        "searchCondition": {
            "keyword": query,
            "excludeKeyword": "",
            "sort": "SORT_SCORE",
            "order": "ORDER_DESC",
            "status": [],
            "sizeId": [],
            "categoryId": [],
            "brandId": [],
            "sellerId": [],
            "priceMin": 0,
            "priceMax": 0,
            "itemConditionId": [],
            "shippingPayerId": [],
            "shippingFromArea": [],
            "shippingMethod": [],
            "colorId": [],
            "hasCoupon": False,
            "attributes": [],
            "itemTypes": [],
            "skuIds": [],
            "shopIds": [],
            "excludeShippingMethodIds": [],
        },
        "serviceFrom": "suruga",
        "withItemBrand": True,
        "withItemSize": False,
        "withItemPromotions": True,
        "withItemSizes": True,
        "withShopname": False,
        "useDynamicAttribute": True,
        "withSuggestedItems": True,
        "withOfferPricePromotion": True,
        "withProductSuggest": True,
        "withParentProducts": False,
        "withProductArticles": True,
        "withSearchConditionId": False,
        "withAuction": True,
        "laplaceDeviceUuid": device_id,
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Accept-Language": "ja",
        "Origin": "https://jp.mercari.com",
        "Referer": "https://jp.mercari.com/",
        "x-platform": "web",
        "x-country-code": "JP",
        "dpop": mercari_dpop(url, device_id),
    }
    try:
        response = SESSION.post(url, json=body, headers=headers, timeout=25)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        return {"status": "failed", "error": str(exc), "items": [], "item_count": 0}
    items = []
    for item in payload.get("items", []):
        price = int(item.get("price") or 0)
        auction = item.get("auction")
        items.append(
            {
                "id": item.get("id"),
                "title": item.get("name"),
                "price_jpy": price,
                "type": "auction" if auction else "listing",
                "type_label": "拍卖" if auction else "挂售",
                "auction_bids": int(auction.get("totalBid") or 0) if auction else None,
                "image": (item.get("thumbnails") or [""])[0],
                "url": f"https://jp.mercari.com/item/{item.get('id')}",
            }
        )
    listings = [item["price_jpy"] for item in items if item["type"] == "listing" and item["price_jpy"]]
    auctions = [item["price_jpy"] for item in items if item["type"] == "auction" and item["price_jpy"]]
    result = {
        "status": "ok",
        "query": query,
        "item_count": int(payload.get("meta", {}).get("numFound") or len(items)),
        "sample_count": len(items),
        "lowest_listing_jpy": min(listings) if listings else None,
        "lowest_auction_jpy": min(auctions) if auctions else None,
        "items": items[:8],
    }
    MERCARI_CACHE[query] = (time.time(), result)
    return result


def market_compare(query: str) -> dict:
    normalized = normalize_query(query)
    return {
        "query": normalized,
        "fetched_at": now_iso(),
        "platforms": [
            {
                "name": "SNKRDUNK",
                "region": "日本",
                "types": ["挂售", "已成交"],
                "status": "live",
                "note": "本站已接入 A 品裸卡与 PSA10 公开成交。",
                "url": f"https://snkrdunk.com/search?brandIds=onepiece&keywords={quote_plus(normalized)}&searchCategoryIds=6%2F33&sort=popular",
            },
            {
                "name": "Mercari",
                "region": "日本",
                "types": ["挂售", "拍卖"],
                "status": "verify-required",
                "note": "Mercari 公开搜索无法可靠确认具体插画版本、数量与品相。本站不展示未经确认的最低价，请打开平台逐项核验。",
                "url": f"https://jp.mercari.com/search?keyword={quote_plus(normalized)}",
            },
        ],
    }


def dashboard(query: str) -> dict:
    normalized = normalize_query(query)
    search = parse_limitless_search(normalized)
    code = normalized if re.fullmatch(r"(?:[A-Z]{1,4}\d{2}-\d{3}|P-\d{3})", normalized) else (search["results"][0]["code"] if search["results"] else normalized)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_card = pool.submit(parse_limitless_card, code)
        fut_ebay = pool.submit(parse_ebay, code)
        fut_snk = pool.submit(parse_snkrdunk, code)
        fut_psa = pool.submit(parse_psa, code)
        card = fut_card.result()
        ebay = fut_ebay.result()
        snkrdunk = fut_snk.result()
        psa = fut_psa.result()
    if card.get("ok"):
        append_snapshot(card["card"])
    return {
        "query": query,
        "normalized": normalized,
        "resolved_code": code,
        "fetched_at": now_iso(),
        "search": search,
        "card": card,
        "markets": {"ebay": ebay, "snkrdunk": snkrdunk, "psa": psa},
        "history": history_for(code),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path == "/api/image":
            url = parse_qs(parsed.query).get("url", [""])[0]
            allowed = "https://asia-en.onepiece-cardgame.com/images/cardlist/card/"
            if not url.startswith(allowed):
                self.send_error(403)
                return
            try:
                response = SESSION.get(url, timeout=20)
                response.raise_for_status()
                self.send_response(200)
                self.send_header("Content-Type", response.headers.get("Content-Type", "image/png"))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)
            except requests.RequestException:
                self.send_error(502)
            return
        if parsed.path == "/api/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            self.send_json(parse_limitless_search(q))
            return
        if parsed.path == "/api/catalog/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json(parse_bandai_search(q))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 502)
            return
        if parsed.path == "/api/catalog/all":
            params = parse_qs(parsed.query)
            q = params.get("q", [""])[0]
            try:
                page = int(params.get("page", ["1"])[0])
                per_page = int(params.get("per_page", ["72"])[0])
                self.send_json(bandai_catalog_page(q, page, per_page))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 502)
            return
        if parsed.path == "/api/overview":
            try:
                self.send_json(overview())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        if parsed.path == "/api/snkrdunk/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json(parse_snkrdunk_search(q or "ルフィ"))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 502)
            return
        if parsed.path == "/api/snkrdunk/sales":
            product_id = parse_qs(parsed.query).get("product_id", [""])[0]
            if not product_id.isdigit():
                self.send_json({"ok": False, "error": "product_id must be numeric"}, 400)
                return
            try:
                self.send_json(parse_snkrdunk_sales(product_id))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 502)
            return
        if parsed.path == "/api/pop":
            q = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json(parse_pricecharting_population(q))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        if parsed.path == "/api/markets/compare":
            q = parse_qs(parsed.query).get("q", [""])[0]
            self.send_json(market_compare(q))
            return
        if parsed.path == "/api/mercari/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            self.send_json(
                {
                    "status": "verify-required",
                    "query": normalize_query(q),
                    "note": "Mercari public search cannot reliably confirm the exact artwork variant, quantity, and condition. Unverified prices are not published.",
                    "items": [],
                }
            )
            return
        if parsed.path == "/api/snkrdunk/market":
            try:
                self.send_json(snkrdunk_market_overview())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 502)
            return
        if parsed.path == "/api/pop/overview":
            try:
                self.send_json(population_overview())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        if parsed.path == "/api/provider/search":
            q = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json(provider_search(q))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        if parsed.path == "/api/provider/market":
            try:
                self.send_json(provider_market())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        if parsed.path == "/api/card":
            q = parse_qs(parsed.query).get("q", [""])[0]
            try:
                self.send_json(dashboard(q or "OP01-003"))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "fetched_at": now_iso()}, 500)
            return
        super().do_GET()


def main() -> None:
    port = int(os.environ.get("PORT") or os.environ.get("OPCARD_PORT", "8787"))
    host = os.environ.get("OPCARD_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"One Piece live card dashboard: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
