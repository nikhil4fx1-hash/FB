# -*- coding: utf-8 -*-
"""
കുട്ടേട്ടൻ - Facebook auto news poster bot
-------------------------------------------
ഒഴുക്ക്:
 1. Google News (മലയാളം) RSS -> ട്രെൻഡിങ് തലക്കെട്ടുകൾ
 2. Gemini (Google Search ഗ്രൗണ്ടിംഗ്) -> വിഷയം തിരഞ്ഞെടുത്ത് JSON പോസ്റ്റ്
 3. ഇമേജ്: ഏറ്റവും ചേരുന്നത് ആദ്യം, ഇല്ലെങ്കിൽ അടുത്തത് (IMAGE_ORDER)
 4. ഇമേജ് ഒന്നും കിട്ടിയില്ലെങ്കിലും ഭംഗിയുള്ള ഡിസൈൻ ബാക്ക്ഗ്രൗണ്ട് (കറുപ്പ് സ്ക്രീൻ വരില്ല)
 5. പോസ്റ്റർ + ക്യാപ്ഷൻ -> Facebook Page

ENV വേരിയബിളുകൾ:
  GEMINI_API_KEY        (നിർബന്ധം)
  FB_PAGE_ACCESS_TOKEN  (നിർബന്ധം)
  IMAGE_ORDER           ഓപ്ഷണൽ, ഡിഫോൾട്ട്: commons,openverse,gemini
                        ഉദാ: gemini,commons,openverse,bing
  ALLOW_WEB_SCRAPE=1    Bing സ്ക്രാപ്പിംഗ് ഓൺ ചെയ്യാൻ (കോപ്പിറൈറ്റ് റിസ്ക് ഉണ്ട്)
  PEXELS_API_KEY / PIXABAY_API_KEY   ഉണ്ടെങ്കിൽ മാത്രം ഉപയോഗിക്കും (ഓപ്ഷണൽ)
  GEMINI_MODEL          ഓപ്ഷണൽ, ഇഷ്ടമുള്ള മോഡൽ
  DRY_RUN=1             ഫേസ്ബുക്കിൽ പോസ്റ്റ് ചെയ്യാതെ fb_post.jpg മാത്രം ഉണ്ടാക്കും (ടെസ്റ്റിന്)
  POSTER_TEST=1         Gemini/ഇന്റർനെറ്റ് ഇല്ലാതെ ഡമ്മി ടെക്സ്റ്റ് വെച്ച് പോസ്റ്റർ ടെസ്റ്റ്
"""
import base64
import html
import json
import math
import os
import random
import re
import sys
import urllib.parse
from io import BytesIO

import feedparser
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat, features

# ================= കോൺഫിഗറേഷൻ =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL")
FB_API_VERSION = os.environ.get("FB_API_VERSION", "v21.0")
ALLOW_WEB_SCRAPE = os.environ.get("ALLOW_WEB_SCRAPE", "0") == "1"
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
POSTER_TEST = os.environ.get("POSTER_TEST", "0") == "1"
IMAGE_ORDER = [s.strip() for s in os.environ.get(
    "IMAGE_ORDER", "commons,openverse,gemini").split(",") if s.strip()]

PAGE_NAME = "കുട്ടേട്ടൻ"
POSTED_FILE = "posted.json"
FONT_FILE = "MalayalamFont.ttf"
FONT_PATHS = [
    FONT_FILE,
    "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMalayalam-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansMalayalam-Bold.ttf",
]
FONT_URLS = [  # ഫോണ്ട് ഇല്ലെങ്കിൽ തനിയെ ഡൗൺലോഡ് ചെയ്യാൻ ശ്രമിക്കും
    "https://github.com/notofonts/malayalam/raw/main/fonts/NotoSansMalayalam/hinted/ttf/NotoSansMalayalam-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/notosansmalayalam/NotoSansMalayalam%5Bwdth%2Cwght%5D.ttf",
]

W, H = 1080, 1350  # 4:5 - ഫേസ്ബുക്ക് ഫീഡിൽ ഏറ്റവും നല്ലത്
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
API_HEADERS = {"User-Agent": "KuttettanBot/1.0 (Facebook page news automation)"}
LAST_CREDIT = {"text": ""}
# =================================================


# ---------- 0. ഫോണ്ട് ----------
def ensure_font():
    for p in FONT_PATHS:
        if os.path.exists(p):
            return p
    for url in FONT_URLS:
        try:
            print("ഫോണ്ട് ഡൗൺലോഡ് ചെയ്യുന്നു:", url)
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 50000:
                with open(FONT_FILE, "wb") as f:
                    f.write(r.content)
                return FONT_FILE
        except Exception as e:
            print("Font download error:", e)
    print("!! മലയാളം ഫോണ്ട് കിട്ടിയില്ല. MalayalamFont.ttf (Noto Sans Malayalam Bold) ഫോൾഡറിൽ ഇടുക.")
    return None


FONT_PATH = None


def load_font(size):
    global FONT_PATH
    if FONT_PATH is None:
        FONT_PATH = ensure_font() or ""
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size, layout_engine=ImageFont.Layout.RAQM)
        except Exception:
            return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


# ---------- 1. ട്രെൻഡിങ് വാർത്തകൾ ----------
def get_trending_topics():
    base = "https://news.google.com/rss"
    feeds = [
        f"{base}?hl=ml&gl=IN&ceid=IN:ml",
        f"{base}/headlines/section/topic/TECHNOLOGY?hl=ml&gl=IN&ceid=IN:ml",
        f"{base}/headlines/section/topic/BUSINESS?hl=ml&gl=IN&ceid=IN:ml",
        f"{base}/headlines/section/topic/SCIENCE?hl=ml&gl=IN&ceid=IN:ml",
        f"{base}/headlines/section/topic/SPORTS?hl=ml&gl=IN&ceid=IN:ml",
    ]
    titles = []
    for f in feeds:
        try:
            r = requests.get(f, headers=HEADERS, timeout=30)
            feed = feedparser.parse(r.content)
            titles += [e.title for e in feed.entries[:6]]
        except Exception as e:
            print("Feed error:", e)
    return list(dict.fromkeys(titles))


def load_posted():
    try:
        with open(POSTED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_posted(items):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(items[-50:], f, ensure_ascii=False)
    except Exception:
        pass


# ---------- 2. Gemini (ടെക്സ്റ്റ്) ----------
def get_available_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    names = []
    try:
        data = requests.get(url, timeout=30).json()
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                names.append(m["name"].split("/")[-1])
    except Exception as e:
        print("Model Fetch Error:", e)
    return names


def pick_text_models():
    bad = ("image", "tts", "live", "embedding", "audio", "vision", "robotics", "computer-use", "native")
    good = [m for m in get_available_models()
            if ("flash" in m or "pro" in m) and not any(b in m for b in bad)]
    good.sort(reverse=True)
    if GEMINI_MODEL:
        good = [GEMINI_MODEL] + [m for m in good if m != GEMINI_MODEL]
    return good


PROMPT = """
താഴെ ഇന്നത്തെ വാർത്താ തലക്കെട്ടുകളാണ്:
{topics}

ഇതിനകം പോസ്റ്റ് ചെയ്ത വിഷയങ്ങൾ (ഇവ ഒഴിവാക്കുക):
{posted}

നിർദ്ദേശങ്ങൾ:
1. ഇതിൽ നിന്ന് ഒരു വിഷയം തിരഞ്ഞെടുക്കുക. ആളുകൾക്ക് ഉപകാരപ്പെടുന്നതും കൗതുകമുണർത്തുന്നതും
   ഷെയർ ചെയ്യാൻ തോന്നുന്നതുമായ വിഷയം വേണം (ടെക്നോളജി, ഗാഡ്ജറ്റ്, ജോലി/PSC, പണം/സ്വർണവില,
   ആരോഗ്യം, കേരളം, സ്പോർട്സ്, പുതിയ നിയമങ്ങൾ).
   കൊലപാതകം, പീഡനം, അപകട ദൃശ്യങ്ങൾ, രാഷ്ട്രീയ വിദ്വേഷം, മതപരമായ തർക്കങ്ങൾ എന്നിവ ഒഴിവാക്കുക.
2. ആ വിഷയത്തെക്കുറിച്ച് ഇന്റർനെറ്റിൽ തിരഞ്ഞ് ശരിയായ വസ്തുതകൾ മാത്രം ഉപയോഗിക്കുക. ഊഹം എഴുതരുത്.
3. ഉത്തരം താഴെ പറയുന്ന JSON മാത്രമായിരിക്കണം. മറ്റൊന്നും എഴുതരുത്. ഉദാഹരണത്തിലെ വാക്കുകൾ കോപ്പി ചെയ്യരുത്.

{{
  "topic_title": "വിഷയത്തിന്റെ ചെറിയ മലയാളം തലക്കെട്ട്",
  "tag": "പോസ്റ്ററിന്റെ മുകളിലെ ടാഗ്, 1-2 വാക്ക് (ടെക്, ജോലി, സ്വർണവില, ആരോഗ്യം, കേരളം, സ്പോർട്സ് എന്നിങ്ങനെ വിഷയത്തിന് ചേരുന്നത്)",
  "headline": "പോസ്റ്ററിലെ വലിയ തലക്കെട്ട്, പരമാവധി 8 വാക്ക്, ആകാംക്ഷ ഉണ്ടാക്കുന്നത്",
  "highlight": "പോസ്റ്ററിലെ മഞ്ഞ ഹൈലൈറ്റ് വരി, 2-4 വാക്ക്",
  "image_query_en": "stock photo keywords, 2-3 simple generic English words describing the scene. No names of people, no exact news titles",
  "image_prompt_en": "one sentence English description of a realistic photo that fits this news (no text, no logos, no real person)",
  "caption": "ക്യാപ്ഷൻ"
}}

caption എഴുതേണ്ട രീതി:
- ആദ്യ വരി: ആളുകളെ പിടിച്ചിരുത്തുന്ന ഒരു ഹുക്ക് വാക്യം (ഒരു ഇമോജി ആകാം).
- പിന്നെ 2-3 പാരഗ്രാഫ്: എന്ത് സംഭവിച്ചു, ആരെ ബാധിക്കും, എപ്പോൾ മുതൽ, സംഖ്യകൾ/തീയതികൾ,
  ഇനി എന്ത് ചെയ്യണം എന്നിവ വ്യക്തമായി.
- പിന്നെ ആളുകളോട് അഭിപ്രായം ചോദിക്കുന്ന ഒരു ചോദ്യം.
- പിന്നെ "ഇതുപോലുള്ള ഉപകാരപ്രദമായ വാർത്തകൾക്കായി പേജ് ഫോളോ ചെയ്യൂ" എന്ന സ്നേഹപൂർവ്വമായ അഭ്യർത്ഥന.
- അവസാനം 5-8 ഹാഷ്‌ടാഗുകൾ.
"""


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def get_post_content(topics, posted):
    models = pick_text_models()
    if not models:
        print("Gemini മോഡലുകൾ കിട്ടിയില്ല (API key പരിശോധിക്കുക).")
        return None
    prompt = PROMPT.format(topics="\n".join(topics), posted="\n".join(posted[-15:]) or "ഒന്നുമില്ല")

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        for use_search in (True, False):  # ആദ്യം Google Search ഗ്രൗണ്ടിംഗോടെ
            body = {"contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.8}}
            if use_search:
                body["tools"] = [{"google_search": {}}]
            try:
                print(f"{model} (search={use_search}) ഉപയോഗിച്ച് പോസ്റ്റ് തയ്യാറാക്കുന്നു...")
                res = requests.post(url, json=body, timeout=120).json()
                parts = res["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts)
                data = extract_json(text)
                if data and all(data.get(k) for k in ("headline", "caption", "highlight")):
                    return data
            except Exception as e:
                print("Gemini error:", e)
    return None


# ---------- 3. ഇമേജ് ഉറവിടങ്ങൾ ----------
def valid_image(content, min_side=700):
    """വലുപ്പം, മുഴുവൻ കറുപ്പ്/വെള്ള, വിചിത്ര ആകൃതി എന്നിവ പരിശോധിക്കുന്നു."""
    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        if min(img.width, img.height) < min_side:
            return None
        ratio = max(img.width, img.height) / min(img.width, img.height)
        if ratio > 3:
            return None
        mean = ImageStat.Stat(img.resize((64, 64)).convert("L")).mean[0]
        if mean < 25 or mean > 235:
            return None
        return img
    except Exception:
        return None


def download(url, timeout=20, headers=None):
    try:
        r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def src_commons(data):
    q = data.get("image_query_en")
    if not q:
        return None
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=API_HEADERS, timeout=25, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": q + " filetype:bitmap", "gsrlimit": 15, "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata", "iiurlwidth": 1400})
        pages = list(((r.json().get("query") or {}).get("pages") or {}).values())
        random.shuffle(pages)
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            content = download(info.get("thumburl") or info.get("url"), headers=API_HEADERS)
            img = valid_image(content) if content else None
            if img:
                meta = info.get("extmetadata", {})
                lic = meta.get("LicenseShortName", {}).get("value", "")
                artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
                LAST_CREDIT["text"] = f"\n\n📷 {artist or 'Wikimedia Commons'} / {lic} (Wikimedia Commons)"
                return img
    except Exception as e:
        print("Commons error:", e)
    return None


def src_openverse(data):
    q = data.get("image_query_en")
    if not q:
        return None
    try:
        r = requests.get("https://api.openverse.org/v1/images/", headers=API_HEADERS, timeout=25,
                         params={"q": q, "license_type": "commercial", "page_size": 20, "mature": "false"})
        if r.status_code != 200:
            print("Openverse status:", r.status_code)
            return None
        results = r.json().get("results", [])
        random.shuffle(results)
        for item in results[:10]:
            content = download(item.get("url"), timeout=15)
            img = valid_image(content) if content else None
            if img:
                lic = (item.get("license") or "").lower()
                if lic in ("cc0", "pdm"):
                    LAST_CREDIT["text"] = ""
                else:
                    LAST_CREDIT["text"] = f"\n\n📷 {item.get('creator') or 'Unknown'} / CC {lic.upper()} (Openverse)"
                return img
    except Exception as e:
        print("Openverse error:", e)
    return None


def src_gemini(data):
    if not GEMINI_API_KEY:
        return None
    desc = data.get("image_prompt_en") or data.get("image_query_en") or data.get("topic_title")
    prompt = (f"Create a realistic, high quality, vivid news-style photograph for a social media post: {desc}. "
              f"No text, no letters, no logos, no watermarks, no recognisable real people.")
    names = [m for m in get_available_models() if "image" in m and "tts" not in m]
    names.sort(reverse=True)
    for model in names[:3]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            print("Gemini ഇമേജ്:", model)
            res = requests.post(url, timeout=120, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}).json()
            for part in res["candidates"][0]["content"]["parts"]:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline:
                    img = valid_image(base64.b64decode(inline["data"]), 500)
                    if img:
                        LAST_CREDIT["text"] = ""
                        return img
        except Exception as e:
            print("Gemini image error:", e)
    return None


def src_pexels(data):
    q = data.get("image_query_en")
    if not (PEXELS_API_KEY and q):
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_API_KEY},
                         params={"query": q, "per_page": 15}, timeout=20)
        photos = r.json().get("photos", []) if r.status_code == 200 else []
        random.shuffle(photos)
        for p in photos[:8]:
            content = download(p["src"]["large2x"])
            img = valid_image(content) if content else None
            if img:
                LAST_CREDIT["text"] = ""
                return img
    except Exception as e:
        print("Pexels error:", e)
    return None


def src_pixabay(data):
    q = data.get("image_query_en")
    if not (PIXABAY_API_KEY and q):
        return None
    try:
        r = requests.get("https://pixabay.com/api/", timeout=20, params={
            "key": PIXABAY_API_KEY, "q": q, "image_type": "photo", "safesearch": "true",
            "per_page": 20, "min_width": 800})
        hits = r.json().get("hits", []) if r.status_code == 200 else []
        random.shuffle(hits)
        for h in hits[:8]:
            content = download(h["largeImageURL"])
            img = valid_image(content) if content else None
            if img:
                LAST_CREDIT["text"] = ""
                return img
    except Exception as e:
        print("Pixabay error:", e)
    return None


def src_bing(data):
    """കോപ്പിറൈറ്റ് റിസ്ക് ഉണ്ട്. ALLOW_WEB_SCRAPE=1 ആണെങ്കിൽ മാത്രം."""
    if not ALLOW_WEB_SCRAPE:
        return None
    for q in (data.get("topic_title"), data.get("image_query_en")):
        if not q:
            continue
        try:
            print("Bing തിരയുന്നു:", q)
            page = requests.get("https://www.bing.com/images/search?q=" + urllib.parse.quote(q) + "&first=1",
                                headers=HEADERS, timeout=20).text
            urls = [html.unescape(u) for u in re.findall(r"murl&quot;:&quot;(.*?)&quot;", page)]
            for u in urls[:12]:
                if any(x in u.lower() for x in ("logo", "icon", "avatar", "sprite")):
                    continue
                content = download(u, timeout=10)
                img = valid_image(content) if content else None
                if img:
                    LAST_CREDIT["text"] = ""
                    return img
        except Exception as e:
            print("Bing error:", e)
    return None


SOURCES = {
    "commons": src_commons,
    "openverse": src_openverse,
    "gemini": src_gemini,
    "pexels": src_pexels,
    "pixabay": src_pixabay,
    "bing": src_bing,
}


def fetch_image(data):
    """IMAGE_ORDER-ലെ ക്രമത്തിൽ ഓരോന്നായി പരീക്ഷിക്കും. ഒന്നും കിട്ടിയില്ലെങ്കിൽ None."""
    LAST_CREDIT["text"] = ""
    for name in IMAGE_ORDER:
        fn = SOURCES.get(name)
        if not fn:
            continue
        print(f"ഇമേജ് ഉറവിടം പരീക്ഷിക്കുന്നു: {name}")
        try:
            img = fn(data)
        except Exception as e:
            print(name, "error:", e)
            img = None
        if img:
            print("ഇമേജ് കിട്ടി:", name)
            return img
    print("ഒരു ഉറവിടത്തിൽ നിന്നും ഫോട്ടോ കിട്ടിയില്ല - ഡിസൈൻ ബാക്ക്ഗ്രൗണ്ട് ഉപയോഗിക്കുന്നു")
    return None


# ---------- 4. പോസ്റ്റർ ----------
PALETTES = [
    ((8, 24, 80), (200, 20, 50), (255, 214, 0)),
    ((0, 50, 90), (0, 150, 120), (255, 214, 0)),
    ((45, 0, 90), (220, 40, 100), (255, 230, 80)),
    ((10, 10, 30), (170, 20, 20), (255, 200, 0)),
    ((0, 40, 70), (30, 120, 220), (255, 120, 40)),
]


def designed_background():
    """ഫോട്ടോ ഇല്ലാത്തപ്പോൾ: ഗ്രേഡിയന്റ് + വൃത്തങ്ങൾ + ഡയഗണൽ വരകൾ (കറുപ്പ് സ്ക്രീൻ അല്ല)."""
    c1, c2, accent = random.choice(PALETTES)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    img = img.convert("RGBA")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(7):  # മങ്ങിയ വലിയ വൃത്തങ്ങൾ
        r = random.randint(120, 380)
        cx, cy = random.randint(-100, W + 100), random.randint(-100, H + 100)
        col = random.choice([accent, (255, 255, 255), c2])
        ld.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (random.randint(18, 45),))
    for x in range(-H, W, 70):  # ഡയഗണൽ വരകൾ
        ld.line([(x, H), (x + H, 0)], fill=(255, 255, 255, 14), width=18)
    ld.ellipse([W - 330, 120, W + 120, 570], outline=accent + (90,), width=14)
    ld.ellipse([-140, H - 700, 300, H - 260], outline=(255, 255, 255, 60), width=10)
    layer = layer.filter(ImageFilter.GaussianBlur(2))
    return Image.alpha_composite(img, layer).convert("RGB")


def cover_crop(img, w, h):
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.Resampling.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def wrap(draw, text, font, max_w):
    lines, cur = [], []
    for word in text.split():
        test = " ".join(cur + [word])
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur.append(word)
        else:
            lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def fit_lines(draw, text, max_w, max_lines, start, end):
    for size in range(start, end - 1, -4):
        font = load_font(size)
        lines = wrap(draw, text, font, max_w)
        if len(lines) <= max_lines and all(draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines
    font = load_font(end)
    return font, wrap(draw, text, font, max_w)[:max_lines]


def line_metrics(font, pad_y, gap):
    asc, desc = font.getmetrics()
    return asc + desc, asc + desc + pad_y * 2 + gap


def draw_boxed_lines(draw, lines, font, y, box_color, text_color, pad_x=34, pad_y=16, gap=12, stroke=0):
    lh, step = line_metrics(font, pad_y, gap)
    for line in lines:
        tw = draw.textlength(line, font=font)
        x = (W - tw) / 2
        draw.rectangle([x - pad_x, y - pad_y, x + tw + pad_x, y + lh + pad_y], fill=box_color)
        draw.text((x, y), line, font=font, fill=text_color, stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += step
    return y


def make_poster(photo, headline, highlight, tag):
    has_photo = photo is not None
    if has_photo:
        img = cover_crop(photo, W, H)
        img = ImageEnhance.Brightness(img).enhance(0.72).convert("RGBA")
    else:
        img = designed_background().convert("RGBA")

    # മുകളിലും താഴെയും ഇരുണ്ട ഗ്രേഡിയന്റ് (ടെക്സ്റ്റ് വായിക്കാൻ)
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    max_bottom = 215 if has_photo else 120
    for y in range(H):
        a = 0
        if y > H * 0.30:
            a = int(max_bottom * ((y - H * 0.30) / (H * 0.70)))
        if y < H * 0.12:
            a = max(a, int(150 * (1 - y / (H * 0.12))))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img, shade).convert("RGB")
    draw = ImageDraw.Draw(img)

    # മുകളിൽ: ചുവപ്പ് ടാഗ് + പേജ് പേര്
    tag_text = (tag or "ട്രെൻഡിംഗ്").strip()
    tag_font = load_font(40)
    tw = draw.textlength(tag_text, font=tag_font)
    asc, desc = tag_font.getmetrics()
    draw.rectangle([40, 40, 40 + tw + 60, 40 + asc + desc + 28], fill=(204, 0, 0))
    draw.rectangle([40, 40, 52, 40 + asc + desc + 28], fill=(255, 214, 0))
    draw.text((70, 54), tag_text, font=tag_font, fill=(255, 255, 255))
    pn_font = load_font(36)
    pw = draw.textlength(PAGE_NAME, font=pn_font)
    draw.text((W - pw - 45, 58), PAGE_NAME, font=pn_font, fill=(255, 255, 255),
              stroke_width=3, stroke_fill=(0, 0, 0))

    # താഴെ നേവി ബാനർ (CTA)
    cta_font = load_font(44)
    cta = "പൂർണ്ണ വിവരങ്ങൾ ക്യാപ്ഷനിൽ വായിക്കൂ ▼"
    cta_h = 130
    draw.rectangle([0, H - cta_h, W, H], fill=(0, 45, 120))
    draw.rectangle([0, H - cta_h - 8, W, H - cta_h], fill=(255, 214, 0))
    cw = draw.textlength(cta, font=cta_font)
    ca, cd = cta_font.getmetrics()
    draw.text(((W - cw) / 2, H - cta_h + (cta_h - ca - cd) / 2 - 4), cta, font=cta_font, fill=(255, 255, 255))

    # ഹെഡ്‌ലൈൻ + ഹൈലൈറ്റ് (ഫോണ്ട് തനിയെ ഫിറ്റ് ആകും)
    max_w = W - 170
    h_font, h_lines = fit_lines(draw, headline, max_w, 4, 96, 48)
    hl_font, hl_lines = fit_lines(draw, highlight, max_w, 2, 80, 44)
    total = (len(h_lines) * line_metrics(h_font, 16, 12)[1] + 26
             + len(hl_lines) * line_metrics(hl_font, 16, 12)[1])
    y = H - cta_h - 70 - total
    y = draw_boxed_lines(draw, h_lines, h_font, y, (204, 0, 0), (255, 255, 255), stroke=2)
    y += 26
    draw_boxed_lines(draw, hl_lines, hl_font, y, (255, 214, 0), (0, 0, 0))

    path = "fb_post.jpg"
    img.save(path, quality=95)
    return path


# ---------- 5. ഫേസ്ബുക്ക് ----------
def post_to_facebook(image_path, caption):
    print("ഫേസ്ബുക്കിലേക്ക് പോസ്റ്റ് ചെയ്യുന്നു...")
    url = f"https://graph.facebook.com/{FB_API_VERSION}/me/photos"
    try:
        with open(image_path, "rb") as f:
            r = requests.post(url, data={"caption": caption, "access_token": FB_PAGE_ACCESS_TOKEN},
                              files={"source": f}, timeout=120)
        return r.json()
    except Exception as e:
        return {"error": f"Connection error: {e}"}


def main():
    print("സ്ക്രിപ്റ്റ് തുടങ്ങി...")
    if not features.check("raqm"):
        print("!! libraqm ഇല്ല - മലയാളം കൂട്ടക്ഷരങ്ങൾ പൊട്ടിപ്പോകും. "
              "apt-get install -y libraqm0 libfribidi0 libharfbuzz0b")

    if POSTER_TEST:
        data = {"headline": "ആൻഡ്രോയിഡിൽ APK ഇൻസ്റ്റാൾ ഇനി എളുപ്പമല്ല!",
                "highlight": "ഇത് അറിയാതെ പോകരുത്!", "tag": "ടെക് ന്യൂസ്",
                "caption": "ടെസ്റ്റ്"}
        path = make_poster(None, data["headline"], data["highlight"], data["tag"])
        print("ടെസ്റ്റ് പോസ്റ്റർ സേവ് ചെയ്തു:", path)
        return

    topics = get_trending_topics()
    if not topics:
        print("വാർത്തകൾ കിട്ടിയില്ല.")
        return
    posted = load_posted()

    data = get_post_content(topics, posted)
    if not data:
        print("പോസ്റ്റ് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല.")
        return

    print("\nഹെഡ്‌ലൈൻ:", data["headline"])
    print("ഹൈലൈറ്റ്:", data["highlight"])

    photo = fetch_image(data)
    path = make_poster(photo, data["headline"], data["highlight"], data.get("tag"))
    caption = data["caption"] + LAST_CREDIT["text"]

    if DRY_RUN:
        print("DRY_RUN: പോസ്റ്റ് ചെയ്തില്ല. fb_post.jpg പരിശോധിക്കുക.\n\nക്യാപ്ഷൻ:\n", caption)
        return

    res = post_to_facebook(path, caption)
    print("ഫേസ്ബുക്ക് മറുപടി:", res)

    if "id" in res or "post_id" in res:
        posted.append(data.get("topic_title", data["headline"]))
        save_posted(posted)


if __name__ == "__main__":
    main()