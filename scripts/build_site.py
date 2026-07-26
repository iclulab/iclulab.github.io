#!/usr/bin/env python3
"""
build_site.py — 由 _data/*.yaml 生成整個網站（中英雙語）

用法：
    python3 scripts/build_site.py

需求：
    pip3 install pyyaml

輸出：
    英文版 → /index.html, /research.html, ...
    中文版 → /zh/index.html, /zh/research.html, ...
    另有 sitemap.xml, robots.txt, 404.html

雙語設計說明
------------
英文與中文各有獨立網址，而不是用 JavaScript 切換顯示。
理由是搜尋引擎會把兩種語言各自建立索引，中文使用者搜「盧臆中 質譜」
與英文使用者搜 "I-Chung Lu mass spectrometry" 都能命中對應版本。
兩邊以 <link rel="alternate" hreflang> 互指，Google 就知道它們是同一內容的不同語言版。

改內容請改 _data/ 底下的 YAML，不要直接改生成出來的 HTML，
下次執行本腳本會被覆蓋。
"""

import html
import json
import pathlib
import re
import sys
from datetime import date

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pubfmt import format_authors  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"
SITE = "https://iclulab.github.io"
LANGS = ("en", "zh")

# 主導覽列的頁面
PAGES = ["index", "research", "facility", "publications", "people", "life", "teaching", "join"]
# 不進導覽列、但要生成的子頁（由其他頁面連入）
SUBPAGES = ["alumni"]
ALL_PAGES = PAGES + SUBPAGES

e = html.escape


def asset_hash(rel):
    """以檔案內容雜湊做為版本號，避免 CDN／瀏覽器沿用舊版樣式。"""
    import hashlib
    f = ROOT / rel
    return hashlib.md5(f.read_bytes()).hexdigest()[:8] if f.exists() else "0"


def load(name):
    return yaml.safe_load((DATA / f"{name}.yaml").read_text(encoding="utf-8"))


P = load("profile")
PUBS = load("publications")
PEOPLE = load("people")
NEWS = load("news")
RESEARCH = load("research")
SECTIONS = load("sections")
FACILITY = load("facility")
ALBUMS = load("albums")["albums"]
COURSES = load("courses")


def pubs_in(section_id):
    """取某分區的著作；無 section 欄位者歸入第一區。"""
    default = SECTIONS[0]["id"]
    return [p for p in PUBS if p.get("section", default) == section_id]


_CJK = r"　-〿㐀-䶿一-鿿＀-￯"


def tidy(s):
    """收攏空白。YAML 折疊字串會在換行處插入空格，中文之間的空格要拿掉。"""
    s = " ".join((s or "").split())
    # 兩側都是中日韓字元／全形標點時，中間的空格是折行造成的，刪掉
    prev = None
    while prev != s:
        prev = s
        s = re.sub(f"([{_CJK}]) ([{_CJK}])", r"\1\2", s)
    return s


def paras(text, cls=""):
    """YAML 折疊字串（>）把段落之間的空行保留成單一 \\n，據此分段。"""
    c = f' class="{cls}"' if cls else ""
    return "".join(
        f"<p{c}>{e(tidy(blk))}</p>"
        for blk in (text or "").split("\n") if blk.strip()
    )


def pick(obj, key, lang):
    """取 key_en / key_zh，缺中文時退回英文。"""
    return obj.get(f"{key}_{lang}") or obj.get(f"{key}_en") or ""


# ------------------------------------------------------------------
# UI 字串
# ------------------------------------------------------------------
T = {
    "en": {
        "nav": ["Home", "Research", "Facility", "Publications", "Group", "Life",
                "Teaching", "Join Us"],
        "switch": "中文",
        "role_title": f"{P['title_en']} · {P['department_en']}",
        "inst": P["institution_en"],
        "addr": P["contact"]["address_en"],
        "footer_org": f"{P['department_en']}, {P['institution_en']}",
        "office": P["contact"]["office_en"],
        "lab": P["contact"]["lab_en"],
        "research": "Research",
        "selected": "Selected publications",
        "all_pubs": "All publications →",
        "read_more": "Read more about the research →",
        "news": "News",
        "group": "The group",
        "group_body": "The lab brings together students working on ionization fundamentals, "
                      "instrument development, and applied classification problems.",
        "meet": "Meet the group →",
        "publications": "Publications",
        "earlier": "Earlier work — reaction dynamics (2003–2008)",
        "earlier_h": "Earlier work",
        "grants": "Research grants",
        "education": "Education",
        "appointments": "Appointments",
        "awards": "Awards",
        "pi": "Principal Investigator",
        "assistant": "Research Assistant",
        "master": "Master's Students",
        "undergrad": "Undergraduate Students",
        "alumni": "Lab Alumni",
        "alumni_lede": "Students who trained in the lab and have since moved on to "
                       "graduate school, industry, and research positions elsewhere.",
        "alumni_link": "See all lab alumni →",
        "back_group": "← Back to the group",
        "life": "Lab Life",
        "life_lede": "Conferences, hiking trips, moving the instruments in, and a great "
                     "many meals. A research group is also the people in it.",
        "life_home": "Conferences, outings, and the everyday work of the lab.",
        "life_more": "See lab life →",
        "photos_n": "{n} photos",
        "eyebrow": "Lu Lab · Department of Chemistry, National Chung Hsing University",
        "claim": "Seeing the world other<br>methods struggle to observe",
        "hero_alt": "Custom-built mass spectrometry inlet on the optical table",
        "claim_lede": "We begin with a basic question: how are ions actually formed? "
                      "That understanding becomes measurement capability that reaches "
                      "real problems, from rapid screening of carbohydrates to smart "
                      "sorting of plastics and the fleeting intermediates of catalytic "
                      "cycles.",
        "cta_research": "What we work on →",
        "cta_join": "Join the lab →",
        "themes_h": "Research directions",
        "skip": "Skip to main content",
        "top": "Back to top",
        "pubs_lede": "From crossed molecular-beam reaction dynamics and ionization "
                     "mechanisms, to the analytical applications the group develops "
                     "independently today.",
        "teaching": "Teaching",
        "teaching_body": "I teach physical chemistry at both undergraduate and graduate "
                         "level at National Chung Hsing University.",
        "t_awards": "Teaching awards",
        "courses": "Courses taught",
        "c_year": "Year",
        "c_term": "Term",
        "c_code": "Course no.",
        "c_dept": "Offered to",
        "c_name": "Course",
        "c_type": "Type",
        "c_req": "Required",
        "c_ele": "Elective",
        "courses_note": "Academic years are given in the Republic of China calendar used by "
                        "Taiwanese universities; year 114 corresponds to 2025–26. "
                        "Laboratory courses and independent-study units are not listed.",
        "yt_h": "Physical chemistry on YouTube",
        "yt_name": "狐獴老師的物化課 (Meerkat Teacher's Physical Chemistry)",
        "yt_body": "Physical chemistry should not read like scripture. It is a splendid "
                   "adventure between the abstract and the real.",
        "yt_cta": "Visit the channel →",
        "join": "Join Us",
        "join_body": "We are looking for students who are curious about how measurements "
                     "actually work, not just how to run them. Projects span ionization "
                     "fundamentals, instrument building, and machine-learning classification "
                     "of spectra, so there is room for people with quite different strengths.",
        "what": "What you can work on",
        "touch": "Get in touch",
        "touch_body": "Email me with a short note about what interests you and, if you have "
                      "one, a CV. NCHU undergraduates are welcome to drop by my office "
                      "(Room 508) or come and see the lab (Room 102).",
        "legend": "<b>*</b> marks the corresponding author. Names in <b>bold</b> indicate "
                  "I-Chung Lu. For the large multi-author community reviews co-authored with "
                  "S. Trimpin the author list is abbreviated; all other papers list every "
                  "author in full.",
        "facility": "Customized Mass Spectrometry Platform",
        "fac_short": "Technical Platform",
        "fac_why": "Why customization",
        "fac_cap": "What we do",
        "fac_svc": "Services",
        "fac_case": "Collaboration cases",
        "fac_apply": "Apply for technical service →",
        "fac_note": "Operated as a sub-project of the NSTC A-Core Plus advanced core facility programme.",
        "fac_home": "We run a customized mass spectrometry platform open to other research groups, "
                    "for measurements that standard instrument centres cannot make.",
        "fac_more": "About the platform →",
        "refs": "Related publications",
        "f_all": "All",
        "f_lead": "First / corresponding",
        "s_pubs": "Publications",
        "s_lead": "First / corresponding",
        "s_grants": "NSTC grants",
        "s_ongoing": "Ongoing",
        "b_corr": "Corresponding author",
        "b_cocorr": "Co-corresponding author",
        "b_first": "First author",
        "b_inv": "Invited review",
        "dyn_note": "Crossed molecular-beam and photodissociation dynamics from the PhD and "
                    "early postdoctoral years.",
        "updated": "Last updated",
        "source": "Source",
        "notfound": "That page does not exist.",
        "home_link": "Back to the homepage →",
        "see_dyn": "See the reaction dynamics publications →",
    },
    "zh": {
        "nav": ["首頁", "研究", "技術平台", "著作", "團隊", "生活", "教學", "加入我們"],
        "switch": "EN",
        "role_title": f"{P['title_zh']} · {P['department_zh']}",
        "inst": P["institution_zh"],
        "addr": P["contact"]["address_zh"],
        "footer_org": f"{P['institution_zh']} {P['department_zh']}",
        "office": P["contact"]["office_zh"],
        "lab": P["contact"]["lab_zh"],
        "research": "研究",
        "selected": "近期著作",
        "all_pubs": "全部著作 →",
        "read_more": "閱讀完整研究介紹 →",
        "news": "消息",
        "group": "實驗室",
        "group_body": "實驗室的研究橫跨游離機制、儀器開發與分類應用，"
                      "不同專長的同學都能找到位置。",
        "meet": "認識團隊成員 →",
        "publications": "著作",
        "earlier": "早期研究 — 反應動力學（2003–2008）",
        "earlier_h": "早期研究",
        "grants": "研究計畫",
        "education": "學歷",
        "appointments": "經歷",
        "awards": "獲獎",
        "pi": "實驗室主持人",
        "assistant": "研究助理",
        "master": "碩士班學生",
        "undergrad": "大學部學生",
        "alumni": "歷屆成員",
        "alumni_lede": "我們曾在實驗室一起成長共事，如今分布在各研究所、產業界與研究單位。",
        "alumni_link": "查看全部歷屆成員 →",
        "back_group": "← 回到團隊",
        "life": "實驗室生活",
        "life_lede": "研討會、爬山、搬儀器，還有很多頓飯。實驗室除了研究，也是一群人。",
        "life_home": "研討會、出遊，以及實驗室的日常。",
        "life_more": "看看實驗室生活 →",
        "photos_n": "{n} 張",
        "eyebrow": "盧臆中實驗室 · 國立中興大學化學系",
        "claim": "用質譜看見<br>其它方法難以觀察的世界",
        "hero_alt": "光學桌上的客製化質譜進樣系統",
        "claim_lede": "我們從一個基礎問題出發：離子究竟是怎麼生成的？"
                      "再把這份理解變成能碰到真實問題的量測能力，"
                      "包括醣類的快速篩檢、塑膠的智慧分選，以及催化循環中一閃即逝的中間體。",
        "cta_research": "我們在做什麼 →",
        "cta_join": "加入實驗室 →",
        "themes_h": "研究主軸",
        "skip": "跳至主要內容",
        "top": "回到頂端",
        "pubs_lede": "從交叉分子束的反應動力學、游離機制，"
                     "到實驗室獨立發展的分析應用。",
        "teaching": "教學",
        "teaching_body": "於國立中興大學講授大學部與研究所的物理化學課程。",
        "t_awards": "教學獲獎",
        "courses": "近五年開課",
        "c_year": "學年",
        "c_term": "學期",
        "c_code": "選課號碼",
        "c_dept": "選課系所",
        "c_name": "課程名稱",
        "c_type": "必選修",
        "c_req": "必修",
        "c_ele": "選修",
        "courses_note": "不含實驗課與專題研究。",
        "yt_h": "YouTube 教學頻道",
        "yt_name": "狐獴老師的物化課",
        "yt_body": "物化不該是天書，而是我們穿梭在抽象與現實間的華麗冒險。",
        "yt_cta": "前往頻道 →",
        "join": "加入我們",
        "join_body": "我們歡迎對「量測背後的原理」感到好奇的同學，而不只是會操作儀器。"
                     "研究題目橫跨游離機制、儀器開發、以及光譜的機器學習分類，"
                     "不同專長的人都能找到位置。",
        "what": "你可以做的題目",
        "touch": "聯絡方式",
        "touch_body": "來信簡述你感興趣的方向，有履歷的話一併附上。"
                      "中興大學部同學也歡迎直接到化學館 508 室找我聊聊，"
                      "或到 102 實驗室看看我們在做什麼。",
        "legend": "星號 <b>*</b> 標示通訊作者，<b>粗體</b>為本人。"
                  "與 S. Trimpin 合著的大型社群綜論因作者眾多而省略中間作者，"
                  "其餘論文一律完整列出所有作者。",
        "facility": "客製化質譜探測服務平台",
        "fac_short": "技術平台",
        "fac_why": "為什麼質譜需要客製化",
        "fac_cap": "我們提供什麼",
        "fac_svc": "服務項目",
        "fac_case": "合作案例",
        "fac_apply": "前往申請技術服務 →",
        "fac_note": "本平台為國科會 A-Core Plus 尖端核心設施技術服務計畫子項目。",
        "fac_home": "我們經營一個對外開放的客製化質譜平台，"
                    "承接常設儀器中心做不到的量測需求。",
        "fac_more": "了解平台 →",
        "refs": "相關著作",
        "f_all": "全部",
        "f_lead": "第一/通訊作者",
        "s_pubs": "篇著作",
        "s_lead": "第一/通訊作者",
        "s_grants": "國科會計畫",
        "s_ongoing": "執行中",
        "b_corr": "通訊作者",
        "b_cocorr": "共同通訊作者",
        "b_first": "第一作者",
        "b_inv": "邀稿綜論",
        "dyn_note": "博士班與早期博後時期的交叉分子束與光解離動力學研究。",
        "updated": "最後更新",
        "source": "原始碼",
        "notfound": "找不到這個頁面。",
        "home_link": "回到首頁 →",
        "see_dyn": "查看反應動力學時期的著作 →",
    },
}


# ------------------------------------------------------------------
def url(page, lang):
    return f"{page}.html" if lang == "en" else f"zh/{page}.html"


def rel(page, lang):
    """同語言內的頁面連結（相對路徑）。"""
    return f"{page}.html"


def asset(path, lang):
    return path if lang == "en" else f"../{path}"


def av(path, lang):
    """圖片加上內容雜湊當版本號。換圖但沿用同一個檔名時，
    瀏覽器與 GitHub Pages 的 CDN 才不會繼續拿舊的快取。"""
    return f"{asset(path, lang)}?v={asset_hash(path)}"


CSS_V = asset_hash("assets/css/style.css")


def layout(page, lang, title, description, body, jsonld=None):
    t = T[lang]
    ACTIVE = ' class="active"'
    nav = "".join(
        '<a href="{}"{}>{}</a>'.format(rel(p, lang), ACTIVE if p == page else "", label)
        for p, label in zip(PAGES, t["nav"])
    )
    other = "zh" if lang == "en" else "en"
    switch = f'<a href="{"zh/" if other == "zh" else "../"}{page}.html" class="lang">{T[lang]["switch"]}</a>'
    ld = (
        f'\n<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
        if jsonld
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="{'en' if lang == 'en' else 'zh-Hant'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}/{url(page, lang)}">
<link rel="alternate" hreflang="en" href="{SITE}/{url(page, 'en')}">
<link rel="alternate" hreflang="zh-Hant" href="{SITE}/{url(page, 'zh')}">
<link rel="alternate" hreflang="x-default" href="{SITE}/{url(page, 'en')}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}/{url(page, lang)}">
<meta property="og:image" content="{SITE}/assets/img/lu.jpg?v={asset_hash('assets/img/lu.jpg')}">
<meta property="og:locale" content="{'en_US' if lang == 'en' else 'zh_TW'}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<link rel="stylesheet" href="{asset('assets/css/style.css', lang)}?v={CSS_V}">
<link rel="icon" href="{asset('assets/img/favicon-32.png', lang)}" sizes="32x32">
<link rel="icon" href="{asset('assets/img/logo-mark.svg', lang)}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{asset('assets/img/favicon-180.png', lang)}">{ld}
</head>
<body>
<a class="skip" href="#main">{e(t['skip'])}</a>
<header class="site-header"><div class="wrap">
  <a class="brand" href="{rel('index', lang)}">
    <img src="{av('assets/img/logo.svg', lang)}" alt="Lu Lab — I-Chung Lu 盧臆中" class="logo">
  </a>
  <nav class="main">{nav}{switch}</nav>
</div></header>
<main id="main">
{body}
</main>
<button class="to-top" type="button" aria-label="{e(t['top'])}" title="{e(t['top'])}">
  <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"
       stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 19V5"/><path d="M5.5 11.5 12 5l6.5 6.5"/></svg>
</button>
<script>
(function () {{
  var b = document.querySelector('.to-top');
  if (!b) return;
  var show = function () {{ b.classList.toggle('on', window.scrollY > 700); }};
  window.addEventListener('scroll', show, {{ passive: true }});
  b.addEventListener('click', function () {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }});
  show();
}})();
</script>
<footer class="site-footer"><div class="wrap">
  <p>{e(t['footer_org'])}<br>{e(t['addr'])}</p>
  <p>{e(t['office'])} · {e(t['lab'])}</p>
  <p><a href="mailto:{P['contact']['email']}">{P['contact']['email']}</a> ·
     Tel {e(P['contact']['phone'])}</p>
  <p>{e(t['updated'])} {date.today().isoformat()} ·
     <a href="https://github.com/iclulab/iclulab.github.io">{e(t['source'])}</a></p>
</div></footer>
</body>
</html>
"""


# ------------------------------------------------------------------
# Fragments
# ------------------------------------------------------------------
def badges(p, lang):
    t = T[lang]
    m = {
        "corresponding": f'<span class="badge corr">{t["b_corr"]}</span>',
        "co-corresponding": f'<span class="badge corr">{t["b_cocorr"]}</span>',
        "first": f'<span class="badge first">{t["b_first"]}</span>',
        "co-author": "",
    }
    out = m[p["role"]]
    if p.get("invited_review"):
        out += f'<span class="badge inv">{t["b_inv"]}</span>'
    return out


ROLE_KEY = {"corresponding": "corr", "co-corresponding": "corr", "first": "first", "co-author": "co"}


PUBFIG_DIR = ROOT / "assets" / "img" / "pubs"


def pub_figure(p, lang):
    """代表圖：檔名取自 DOI（/ 換成 _）。檔案存在才輸出。"""
    if not p.get("doi"):
        return ""
    fn = p["doi"].replace("/", "_") + ".jpg"
    if not (PUBFIG_DIR / fn).exists():
        return ""
    src = asset(f"assets/img/pubs/{fn}", lang)
    alt = f'Graphical abstract: {p["title"][:80]}'
    return (f'<a class="pub-fig" href="https://doi.org/{p["doi"]}" '
            f'aria-label="{e(alt)}"><img src="{src}" alt="{e(alt)}" loading="lazy"></a>')


def pub_li(p, lang):
    doi = (
        f'<a class="doi" href="https://doi.org/{p["doi"]}">doi:{e(p["doi"])}</a>'
        if p.get("doi")
        else ""
    )
    vol = f", {e(p['volume'])}" if p.get("volume") else ""
    topics = " ".join(p.get("topics") or [])
    fig = pub_figure(p, lang)
    cls = "has-fig" if fig else ""
    return f"""<li class="{cls}" data-role="{ROLE_KEY[p['role']]}" data-topics="{e(topics)}">
  <div class="pub-body">
    <span class="pub-authors">{format_authors(p['authors'], highlight=True)}</span>
    <span class="pub-title">{e(p['title'])}</span>
    <span class="pub-meta"><em>{e(p['journal'])}</em> <b>{p['year']}</b>{vol}</span>
    <span class="pub-badges">{badges(p, lang)}{doi}</span>
  </div>{fig}
</li>"""


def news_items(lang, limit=None):
    """消息依年份分組成時間軸，年份標在左欄，事件排右欄。"""
    items = NEWS[:limit] if limit else NEWS
    key = "text_zh" if lang == "zh" else "text_en"
    groups = []
    for n in items:
        y = str(n["date"])[:4]
        if not groups or groups[-1][0] != y:
            groups.append((y, []))
        groups[-1][1].append(n)
    out = []
    for y, ns in groups:
        rows = "".join(
            f'<li><time datetime="{e(str(n["date"]))}">{e(str(n["date"])[5:])}</time>'
            f'<span>{e(n.get(key) or n["text_zh"])}</span></li>'
            for n in ns
        )
        out.append(f'<div class="tl-group"><div class="tl-year">{e(y)}</div>'
                   f'<ul class="tl-items">{rows}</ul></div>')
    return f'<div class="timeline">{"".join(out)}</div>'


def idlinks(lang):
    L = P["links"]
    return (
        '<div class="idlinks">'
        f'<a href="{L["google_scholar"]}">Google Scholar</a>'
        f'<a href="{L["orcid"]}">ORCID</a>'
        f'<a href="{rel("publications", lang)}">{T[lang]["publications"]}</a>'
        f'<a href="mailto:{P["contact"]["email"]}">Email</a>'
        "</div>"
    )


def theme_blocks(lang):
    out = []
    for th in RESEARCH["themes"]:
        out.append(
            f"""<div class="theme">
  <span class="tag">{e(th['tag'])}</span>
  <h3>{e(pick(th, 'title', lang))}</h3>
  <p>{e(tidy(pick(th, 'body', lang)))}</p>
</div>"""
        )
    return f'<div class="themes">{"".join(out)}</div>'


def _build_peaks(seed=20260726):
    """畫一段像真實質譜的峰線：峰位不等距、強度落差大，並帶同位素叢集。
    用固定亂數種子產生，所以每次 build 出來的圖案都一樣。"""
    import random
    rng = random.Random(seed)
    peaks, x = [], 6.0
    while x < 794:
        # 主峰：強度取對數分布，少數很高、多數偏低
        h = 6 + 88 * (rng.random() ** 2.1)
        peaks.append((round(x, 1), round(100 - h, 1)))
        # 同位素叢集：高峰後面常跟著兩三根遞減的小峰
        if h > 45 and rng.random() < 0.75:
            k = rng.choice((1, 2, 2, 3))
            hh, xx = h, x
            for _ in range(k):
                xx += rng.uniform(4.5, 7.5)
                hh *= rng.uniform(0.28, 0.62)
                if xx < 794 and hh > 3:
                    peaks.append((round(xx, 1), round(100 - hh, 1)))
            x = xx
        # 峰間距不規則，偶爾留一段空白基線
        x += rng.uniform(6, 20) if rng.random() > 0.12 else rng.uniform(26, 52)
    return peaks


SPECTRUM = (
    '<svg class="hero-spectrum" viewBox="0 0 800 100" preserveAspectRatio="none" aria-hidden="true">'
    + "".join(f'<line x1="{x}" y1="100" x2="{x}" y2="{y}"/>' for x, y in _build_peaks())
    + '<line class="baseline" x1="0" y1="100" x2="800" y2="100"/></svg>'
)

# 研究主軸的線條圖示（24×24，stroke 繼承 currentColor）
ICONS = {
    "foundations":
        '<path d="M12 3v6"/><path d="M9 6l3 3 3-3"/><path d="M3 15h18"/>'
        '<circle cx="7" cy="19" r="1.6"/><circle cx="12" cy="20.4" r="1.6"/>'
        '<circle cx="17" cy="19" r="1.6"/>',
    "health":
        '<path d="M8 4.2l3.2 1.9v3.7L8 11.7 4.8 9.8V6.1z"/>'
        '<path d="M11.2 6.1L14.4 4.2"/>'
        '<circle cx="18" cy="14" r="2"/><circle cx="12.5" cy="17.5" r="2"/>'
        '<circle cx="18.5" cy="20" r="2"/><path d="M16.4 15.3l-2.3 1.4"/>'
        '<path d="M14.3 18.6l2.4 1"/>',
    "sustainability":
        '<path d="M12 3.6l3.4 5.9H8.6z"/><path d="M4.4 17.6l3.4-5.9 3.4 5.9z"/>'
        '<path d="M19.6 17.6l-3.4-5.9-3.4 5.9z"/><path d="M4.4 17.6h15.2"/>',
    "mechanisms":
        '<path d="M20 12a8 8 0 1 1-3.2-6.4"/><path d="M17.2 3.4v2.6h-2.6"/>'
        '<circle cx="12" cy="12" r="2.4"/>',
}


def theme_cards(lang):
    """首頁用：四張主題卡，一句話講完一條研究主軸。"""
    out = []
    for th in RESEARCH["themes"]:
        blurb = tidy(pick(th, "blurb", lang)) or tidy(pick(th, "body", lang))
        icon = ICONS.get(th["id"], "")
        svg = (f'<svg class="ticon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
               f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
               f'aria-hidden="true">{icon}</svg>') if icon else ""
        out.append(
            f"""<a class="tcard" href="{rel('research', lang)}#{th['id']}">
  <div class="tcard-head">{svg}<span class="tag">{e(th['tag'])}</span></div>
  <h3>{e(pick(th, 'title', lang))}</h3>
  <p>{e(blurb)}</p>
</a>"""
        )
    return f'<div class="tcards">{"".join(out)}</div>'


def page_hero(title, lede=""):
    """內頁的標題區，與首頁共用同一套視覺語彙（襯線標題 + 底部峰線）。"""
    sub = f'<p class="claim-lede">{e(tidy(lede))}</p>' if lede else ""
    return f"""<div class="hero page-hero">
  {SPECTRUM}
  <div class="wrap">
    <h1 class="claim">{e(title)}</h1>
    {sub}
  </div>
</div>"""


def pub_cards(lang, n=6):
    """首頁的代表圖畫廊：有代表圖的最新幾篇，圖 + 標題 + 期刊年份。"""
    picked = [p for p in main_pubs if pub_figure(p, lang)][:n]
    cards = []
    for p in picked:
        fn = p["doi"].replace("/", "_") + ".jpg"
        src = asset(f"assets/img/pubs/{fn}", lang)
        cards.append(
            f"""<a class="pcard" href="https://doi.org/{p['doi']}">
  <span class="pcard-fig"><img src="{src}" alt="{e(p['title'][:80])}" loading="lazy"></span>
  <span class="pcard-title">{e(p['title'])}</span>
  <span class="pcard-meta"><em>{e(p['journal'])}</em> {p['year']}</span>
</a>"""
        )
    return f'<div class="pcards">{"".join(cards)}</div>'


def person_card(p, lang, subdir=""):
    base = asset(f"assets/img/people/{subdir}", lang)
    photo = (
        f'<img class="ph" src="{base}{e(p["photo"])}" alt="{e(p["name_en"])}" loading="lazy">'
        if p.get("photo")
        else f'<div class="ph">{e(p["name_zh"][0]) if p.get("name_zh") else "·"}</div>'
    )
    primary = p["name_zh"] if lang == "zh" and p.get("name_zh") else p["name_en"]
    secondary = p["name_en"] if lang == "zh" and p.get("name_zh") else p.get("name_zh", "")
    extra = pick(p, "note", lang) or p.get("degree", "") or p.get("topic", "")
    topic = f'<div class="topic">{e(extra)}</div>' if extra else ""
    return (
        f'<div class="person">{photo}<div class="nm">{e(primary)}</div>'
        f'<div class="nm-zh">{e(secondary)}</div>{topic}</div>'
    )


def people_group(heading, members, lang, subdir=""):
    if not members:
        return ""
    cards = "".join(person_card(m, lang, subdir) for m in members)
    return f'<section><h2>{e(heading)}</h2><div class="people">{cards}</div></section>'


# ------------------------------------------------------------------
ALUMNI = PEOPLE.get("alumni") or []
# 團隊頁只放最近幾位當引子，完整名單在 alumni.html
ALUMNI_RECENT = ALUMNI[::-1][:6]

main_pubs = pubs_in(SECTIONS[0]["id"])
n_lead = sum(1 for p in PUBS if p["role"] in ("first", "corresponding", "co-corresponding"))
# public: false 的計畫不上網頁（例如平台維運類），資料仍留在 YAML 供 CV 用
GRANTS = [g for g in P["grants"] if g.get("public", True)]
n_ongoing = sum(1 for g in GRANTS if g["status"] == "ongoing")


def stats(lang):
    t = T[lang]
    return f"""<div class="stats">
  <div class="stat"><div class="n">{len(PUBS)}</div><div class="k">{t['s_pubs']}</div></div>
  <div class="stat"><div class="n">{n_lead}</div><div class="k">{t['s_lead']}</div></div>
  <div class="stat"><div class="n">{len(GRANTS)}</div><div class="k">{t['s_grants']}</div></div>
  <div class="stat"><div class="n">{n_ongoing}</div><div class="k">{t['s_ongoing']}</div></div>
</div>"""


# ------------------------------------------------------------------
# Pages
# ------------------------------------------------------------------
def page_index(lang):
    t = T[lang]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "I-Chung Lu",
        "alternateName": ["盧臆中", "Lu, I-Chung"],
        "jobTitle": P["title_en"],
        "email": f"mailto:{P['contact']['email']}",
        "url": SITE,
        "image": f"{SITE}/assets/img/lu.jpg",
        "identifier": P["links"]["orcid"],
        "sameAs": [P["links"]["orcid"], P["links"]["google_scholar"], P["links"]["github"]],
        "affiliation": {
            "@type": "CollegeOrUniversity",
            "name": P["institution_en"],
            "department": P["department_en"],
            "address": P["contact"]["address_en"],
        },
        "alumniOf": [
            {"@type": "CollegeOrUniversity", "name": ed["institution"]} for ed in P["education"]
        ],
        "knowsAbout": P["research_interests"],
        "description": tidy(P["bio_short_en"]),
    }
    body = f"""<div class="hero home-hero">
  {SPECTRUM}
  <div class="wrap"><div class="home-grid">
    <div>
      <p class="eyebrow">{e(t['eyebrow'])}</p>
      <h1 class="claim">{t['claim']}</h1>
      <p class="claim-lede">{e(t['claim_lede'])}</p>
      <div class="cta-row">
        <a class="cta" href="{rel('research', lang)}">{e(t['cta_research'])}</a>
        <a href="{rel('join', lang)}">{e(t['cta_join'])}</a>
      </div>
    </div>
    <figure class="hero-shot">
      <img src="{av('assets/img/hero.jpg', lang)}" alt="{e(t['hero_alt'])}">
    </figure>
  </div></div>
</div>

<div class="wrap">
<section>
  <h2>{e(t['themes_h'])}</h2>
  {theme_cards(lang)}
  <p style="margin-top:24px"><a href="{rel('research', lang)}">{e(t['read_more'])}</a></p>
</section>

<section>
  <h2>{e(t['news'])}</h2>
  <div class="news-scroll">{news_items(lang)}</div>
</section>

<section>
  <h2>{e(t['selected'])}</h2>
  {pub_cards(lang)}
  <p style="margin-top:22px"><a href="{rel('publications', lang)}">{e(t['all_pubs'])}</a></p>
</section>

<section>
  <h2>{e(t['fac_short'])}</h2>
  <p>{e(t['fac_home'])} <a href="{rel('facility', lang)}">{e(t['fac_more'])}</a></p>
</section>

<section>
  <h2>{e(t['group'])}</h2>
  <p>{e(t['group_body'])} <a href="{rel('people', lang)}">{e(t['meet'])}</a></p>
</section>

<section>
  <h2>{e(t['life'])}</h2>
  <p>{e(t['life_home'])} <a href="{rel('life', lang)}">{e(t['life_more'])}</a></p>
  <div class="shots strip">{LIFE_STRIP(lang)}</div>
</section>
</div>"""
    title = (
        "I-Chung Lu | Mass Spectrometry & Physical Chemistry | NCHU"
        if lang == "en"
        else "盧臆中 I-Chung Lu ｜ 質譜與物理化學 ｜ 國立中興大學化學系"
    )
    desc = (
        "I-Chung Lu, Associate Professor of Chemistry at National Chung Hsing University. "
        "Research on MALDI ionization mechanisms, carbohydrate mass spectrometry with AI "
        "classification, smart plastic identification, and reactive intermediates in catalysis."
        if lang == "en"
        else "盧臆中，國立中興大學化學系副教授。研究領域涵蓋 MALDI 游離機制、"
        "醣類質譜結合 AI 分類、塑膠智慧辨識與回收，以及催化反應中間體的捕捉。"
    )
    return layout("index", lang, title, desc, body, jsonld)


def page_research(lang):
    t = T[lang]
    grants = "".join(
        f"""<li><div class="g-head">
      <span class="g-title">{e(pick(g, 'title', lang))}</span>
      <span class="g-id">{e(g['id'])}</span>
    </div>
    <div class="g-id">{e(g['agency'])} · {e(g['period'])} ·
      {'PI' if g['role'] == 'PI' else 'Co-PI'} · {e(g['status'])}</div></li>"""
        for g in GRANTS
    )
    themes = "".join(
        f"""<div class="theme" id="{th['id']}">
  <span class="tag">{e(th['tag'])}</span>
  <h3>{e(th['title_en'])}<span class="zh"> · {e(th['title_zh'])}</span></h3>
  <p>{e(tidy(pick(th, 'body', lang)))}</p>
</div>"""
        for th in RESEARCH["themes"]
    )
    body = page_hero(t["research"], pick(RESEARCH, "intro", lang)) + f"""<div class="wrap">
<section style="padding-top:34px"><div class="themes">{themes}</div></section>

<section>
  <h2>{e(t['earlier_h'])}</h2>
  <p>{e(tidy(pick(RESEARCH, 'earlier', lang)))}</p>
  <p><a href="{rel('publications', lang)}#ionization-techniques">{e(t['see_dyn'])}</a></p>
</section>

<section>
  <h2>{e(t['grants'])}</h2>
  <ul class="grants">{grants}</ul>
</section>
</div>"""
    title = "Research | I-Chung Lu | NCHU" if lang == "en" else "研究 ｜ 盧臆中 ｜ 中興大學化學系"
    desc = (
        "Ionization mechanisms, carbohydrate mass spectrometry with AI classification, "
        "smart plastic identification, and reactive intermediates in catalysis."
        if lang == "en"
        else "游離機制、醣類質譜結合 AI 分類、塑膠智慧辨識與回收、催化反應中間體捕捉。"
    )
    return layout("research", lang, title, desc, body)


def page_publications(lang):
    t = T[lang]
    topics = sorted({x for p in PUBS for x in (p.get("topics") or [])})
    filters = (
        f'<button aria-pressed="true" data-f="all">{e(t["f_all"])}</button>'
        f'<button data-f="lead">{e(t["f_lead"])}</button>'
        + "".join(
            f'<button data-f="t:{e(x)}">{e(x.replace("-", " "))}</button>' for x in topics
        )
    )
    script = """
<script>
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed','false'));
  b.setAttribute('aria-pressed','true');
  const f = b.dataset.f;
  document.querySelectorAll('ol.pubs li').forEach(li => {
    let show = true;
    if (f === 'lead') show = li.dataset.role !== 'co';
    else if (f.startsWith('t:')) show = li.dataset.topics.split(' ').includes(f.slice(2));
    li.style.display = show ? '' : 'none';
  });
}));
</script>"""
    blocks = []
    for i, s in enumerate(SECTIONS):
        items = pubs_in(s["id"])
        if not items:
            continue
        # 分區說明與作者標示說明皆不顯示（使用者要求：清單本身就夠清楚）
        head = f"""<h2>{e(pick(s, 'title', lang))} <span class="yrs">{e(pick(s, 'years', lang))}</span></h2>"""
        # 篩選器只放在第一區，套用到全頁
        controls = f'<div class="filters">{filters}</div>' if i == 0 else ""
        blocks.append(
            f"""<section id="{s['id']}">
  {head}
  {controls}
  <ol class="pubs">{''.join(pub_li(p, lang) for p in items)}</ol>
</section>"""
        )
    jump = "".join(
        f'<a href="#{s["id"]}">{e(pick(s, "title", lang))}</a>'
        for s in SECTIONS
        if pubs_in(s["id"])
    )
    script += """
<script>
(function () {
  var links = [...document.querySelectorAll('.jump a')];
  var secs = links.map(a => document.querySelector(a.getAttribute('href')));
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var i = secs.indexOf(en.target);
      links.forEach(function (a, j) { a.classList.toggle('on', i === j); });
    });
  }, { rootMargin: '-30% 0px -60% 0px' });
  secs.forEach(function (s) { if (s) io.observe(s); });
})();
</script>"""
    body = page_hero(t["publications"], t["pubs_lede"]) + f"""<nav class="jump" aria-label="{e(t['publications'])}">
  <div class="wrap">{jump}</div>
</nav>
<div class="wrap">
{''.join(blocks)}
</div>{script}"""
    title = "Publications | I-Chung Lu | NCHU" if lang == "en" else "著作 ｜ 盧臆中 ｜ 中興大學化學系"
    desc = (
        f"{len(PUBS)} peer-reviewed publications by I-Chung Lu in mass spectrometry, "
        "ionization mechanisms, catalysis, and reaction dynamics."
        if lang == "en"
        else f"盧臆中的 {len(PUBS)} 篇學術著作，涵蓋質譜、游離機制、催化與反應動力學。"
    )
    return layout("publications", lang, title, desc, body)


def page_people(lang):
    t = T[lang]
    ed = "".join(
        f'<li><span class="g-title">{e(x["degree"])}</span>'
        f'<div class="g-id">{e(x["institution"])} · {e(x["years"])}</div></li>'
        for x in P["education"]
    )
    ap = "".join(
        f'<li><span class="g-title">{e(x["position"])}</span>'
        f'<div class="g-id">{e(x["org"])} · {e(x["years"])}</div></li>'
        for x in P["appointments"]
    )
    aw = "".join(
        f'<li><span class="g-title">{e(pick(x, "name", lang))}</span>'
        f'<div class="g-id">{x["year"]}</div></li>'
        for x in P["awards"]
    )
    body = page_hero(t["nav"][PAGES.index("people")], t["group_body"]) + f"""<div class="wrap">
<section style="padding-top:34px"><h2>{e(t['pi'])}</h2>
<div class="hero-grid">
  <img class="hero-photo" src="{av('assets/img/lu.jpg', lang)}" alt="I-Chung Lu">
  <div>
    <h3>I-Chung Lu <span class="zh">盧臆中</span></h3>
    <p class="zh">{e(t['role_title'])}，{e(t['inst'])}</p>
    {paras(pick(P, 'bio_long', lang), 'justify')}
    {idlinks(lang)}
  </div>
</div></section>

<section><h2>{e(t['education'])}</h2><ul class="grants">{ed}</ul></section>
<section><h2>{e(t['appointments'])}</h2><ul class="grants">{ap}</ul></section>
<section><h2>{e(t['awards'])}</h2><ul class="grants">{aw}</ul></section>
""" + people_group(t["assistant"], PEOPLE.get("assistant") or [], lang) \
    + people_group(t["master"], PEOPLE.get("master_students") or [], lang) \
    + people_group(t["undergrad"], PEOPLE.get("undergraduate_students") or [], lang) \
    + f"""<section>
  <h2>{e(t['alumni'])}</h2>
  <div class="people alumni-preview">{''.join(person_card(m, lang, 'alumni/') for m in ALUMNI_RECENT)}</div>
  <p style="margin-top:18px"><a href="{rel('alumni', lang)}">{e(t['alumni_link'])}</a></p>
</section>""" \
    + "</div>"
    title = "Group | I-Chung Lu | NCHU" if lang == "en" else "團隊 ｜ 盧臆中 ｜ 中興大學化學系"
    desc = (
        "Members of the Lu group at the Department of Chemistry, National Chung Hsing University."
        if lang == "en"
        else "國立中興大學化學系盧臆中實驗室成員。"
    )
    return layout("people", lang, title, desc, body)


ALBUM_DIR = ROOT / "assets" / "img" / "album"


def album_photos(aid):
    """掃描 assets/img/album/{id}-N.jpg，序號連續，從 0 開始。"""
    out = []
    i = 0
    while (ALBUM_DIR / f"{aid}-{i}.jpg").exists():
        out.append(f"{aid}-{i}.jpg")
        i += 1
    return out


def LIFE_STRIP(lang, n=6):
    """首頁的一排縮圖：各相簿的封面，取最新的幾本。"""
    out = []
    for a in ALBUMS:
        if a.get("pinned"):
            continue
        photos = album_photos(a["id"])
        if not photos:
            continue
        cover = photos[a.get("cover", 0)] if a.get("cover", 0) < len(photos) else photos[0]
        out.append((pick(a, "title", lang), cover))
        if len(out) == n:
            break
    base = asset("assets/img/album/", lang)
    return "".join(
        f'<a class="shot" href="{rel("life", lang)}">'
        f'<img src="{base}{fn}" alt="{e(title)}" loading="lazy"></a>'
        for title, fn in out
    )


def page_life(lang):
    """相簿改成封面牆：一本一張封面，點開才在燈箱裡逐張看。
    這樣整頁只載入 20 張封面，也不必一直往下捲。"""
    t = T[lang]
    base = asset("assets/img/album/", lang)
    cards = []
    for a in ALBUMS:
        photos = album_photos(a["id"])
        if not photos:
            continue
        ci = a.get("cover", 0)
        cover = photos[ci] if isinstance(ci, int) and ci < len(photos) else photos[0]
        title = pick(a, "title", lang)
        yr = f'<span class="acard-year">{a["year"]}</span>' if a.get("year") else ""
        srcs = json.dumps([base + fn for fn in photos], ensure_ascii=False)
        cards.append(
            f"""<button class="acard" data-photos='{e(srcs, quote=True)}'
        data-title="{e(title)}" aria-label="{e(title)}（{len(photos)}）">
  <span class="acard-fig">
    <img src="{base}{cover}" alt="{e(title)}" loading="lazy">
    <span class="acard-count">{len(photos)}</span>
  </span>
  <span class="acard-cap">{e(title)}{yr}</span>
</button>"""
        )
    blocks = [f'<section style="padding-top:32px"><div class="acards">{"".join(cards)}</div></section>']
    script = """
<script>
(function () {
  const box = document.createElement('div');
  box.className = 'lightbox'; box.hidden = true;
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.innerHTML = '<button class="lb-close" aria-label="Close">&times;</button>'
    + '<button class="lb-prev" aria-label="Previous">&#8249;</button>'
    + '<figure><img alt=""><figcaption></figcaption></figure>'
    + '<button class="lb-next" aria-label="Next">&#8250;</button>';
  document.body.appendChild(box);
  const img = box.querySelector('img');
  const cap = box.querySelector('figcaption');
  let list = [], title = '', at = 0, opener = null;

  function show(i) {
    at = (i + list.length) % list.length;
    img.src = list[at];
    img.alt = title + ' ' + (at + 1);
    cap.textContent = title + '　' + (at + 1) + ' / ' + list.length;
    // 預先載入前後各一張，翻頁不用等
    [at + 1, at - 1].forEach(function (j) {
      const k = (j + list.length) % list.length;
      const pre = new Image(); pre.src = list[k];
    });
  }
  function open(card) {
    list = JSON.parse(card.dataset.photos);
    title = card.dataset.title;
    opener = card; show(0);
    box.hidden = false;
    document.body.style.overflow = 'hidden';
    box.querySelector('.lb-close').focus();
  }
  function close() {
    box.hidden = true; img.src = ''; document.body.style.overflow = '';
    if (opener) opener.focus();
  }
  document.querySelectorAll('.acard').forEach(function (c) {
    c.addEventListener('click', function () { open(c); });
  });
  box.querySelector('.lb-close').addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function (e) { e.stopPropagation(); show(at - 1); });
  box.querySelector('.lb-next').addEventListener('click', function (e) { e.stopPropagation(); show(at + 1); });
  box.addEventListener('click', function (e) { if (e.target === box || e.target === img) close(); });
  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') show(at - 1);
    if (e.key === 'ArrowRight') show(at + 1);
  });
  // 手機滑動翻頁
  let x0 = null;
  box.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
  box.addEventListener('touchend', function (e) {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 45) show(at + (dx < 0 ? 1 : -1));
    x0 = null;
  }, { passive: true });
})();
</script>"""
    body = page_hero(t["life"], t["life_lede"]) + f"""<div class="wrap">
{''.join(blocks)}
</div>{script}"""
    title = ("Lab Life | I-Chung Lu | NCHU" if lang == "en"
             else "實驗室生活 ｜ 盧臆中 ｜ 中興大學化學系")
    desc = ("Photos from conferences, group outings, and everyday work in the Lu group "
            "at National Chung Hsing University."
            if lang == "en"
            else "盧臆中實驗室的研討會、出遊與日常照片。")
    return layout("life", lang, title, desc, body)


def page_alumni(lang):
    t = T[lang]
    cards = "".join(person_card(m, lang, "alumni/") for m in ALUMNI)
    body = page_hero(t["alumni"], t["alumni_lede"]) + f"""<div class="wrap">
<section style="padding-top:34px">
  <div class="people" id="alumni-grid">{cards}</div>
  <p style="margin-top:26px"><a href="{rel('people', lang)}">{e(t['back_group'])}</a></p>
</section>
</div>"""
    title = ("Lab Alumni | I-Chung Lu | NCHU" if lang == "en"
             else "歷屆成員 ｜ 盧臆中 ｜ 中興大學化學系")
    desc = (f"{len(ALUMNI)} former members of the Lu group, Department of Chemistry, "
            "National Chung Hsing University."
            if lang == "en"
            else f"國立中興大學化學系盧臆中實驗室的 {len(ALUMNI)} 位歷屆成員。")
    return layout("alumni", lang, title, desc, body)


def course_table(lang):
    """近五學年的開課紀錄。學年相同者以學期由大到小排，同一學年只在第一列顯示學年。"""
    t = T[lang]
    rows = COURSES["courses"]
    if rows:
        cutoff = max(c["year"] for c in rows) - COURSES.get("recent_years", 5) + 1
        rows = [c for c in rows if c["year"] >= cutoff]
    rows = sorted(rows, key=lambda c: (-c["year"], -c["term"], c["code"]))
    out, last_year = [], None
    for c in rows:
        newy = c["year"] != last_year
        last_year = c["year"]
        badge = t["c_req"] if c["required"] else t["c_ele"]
        cls = "req" if c["required"] else "ele"
        tr = '<tr class="newyear">' if newy else "<tr>"
        out.append(
            tr
            + f'<td class="yr">{c["year"] if newy else ""}</td>'
            f'<td class="tm">{c["term"]}</td>'
            f'<td class="code">{e(c["code"])}</td>'
            f'<td class="dept">{e(pick(c, "dept", lang))}</td>'
            f'<td class="cname">{e(pick(c, "name", lang))}</td>'
            f'<td><span class="ctype {cls}">{e(badge)}</span></td></tr>'
        )
    head = "".join(f"<th>{e(t[k])}</th>"
                   for k in ("c_year", "c_term", "c_code", "c_dept", "c_name", "c_type"))
    return (f'<div class="table-wrap"><table class="courses">'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(out)}</tbody></table></div>")


def page_teaching(lang):
    t = T[lang]
    aw = "".join(
        f'<li><span class="g-title">{e(pick(x, "name", lang))}</span>'
        f'<div class="g-id">{x["year"]}</div></li>'
        for x in P["awards"]
        if "Teach" in x["name_en"] or "Mentor" in x["name_en"]
    )
    body = page_hero(t["teaching"], t["teaching_body"]) + f"""<div class="wrap">
<section style="padding-top:34px"><h2>{e(t['courses'])}</h2>
  {course_table(lang)}
  <p class="sec-note" style="margin-top:14px">{e(t['courses_note'])}</p>
</section>
<section>
  <h2>{e(t['yt_h'])}</h2>
  <div class="yt">
    <a class="yt-logo" href="{P['links']['youtube']}" aria-label="{e(t['yt_name'])}">
      <img src="{av('assets/img/pchem-logo.png', lang)}" alt="{e(t['yt_name'])}">
    </a>
    <div>
      <h3>{e(t['yt_name'])}</h3>
      <p class="yt-tag">{e(t['yt_body'])}</p>
      <p><a class="cta" href="{P['links']['youtube']}">{e(t['yt_cta'])}</a></p>
    </div>
  </div>
</section>
</div>"""
    title = "Teaching | I-Chung Lu | NCHU" if lang == "en" else "教學 ｜ 盧臆中 ｜ 中興大學化學系"
    desc = (
        "Physical chemistry teaching at NCHU by I-Chung Lu, recipient of the "
        "NCHU Distinguished Teaching Award."
        if lang == "en"
        else "盧臆中於中興大學講授物理化學，曾獲中興大學教學特優獎與特優導師。"
    )
    return layout("teaching", lang, title, desc, body)


def page_join(lang):
    t = T[lang]
    body = page_hero(t["join"], t["join_body"]) + f"""<div class="wrap">
<section style="padding-top:34px"><h2>{e(t['what'])}</h2>{theme_blocks(lang)}</section>
<section>
  <h2>{e(t['touch'])}</h2>
  <p>{e(t['touch_body'])}</p>
  <p><a class="cta" href="mailto:{P['contact']['email']}">{P['contact']['email']}</a></p>
</section>
</div>"""
    title = "Join Us | I-Chung Lu | NCHU" if lang == "en" else "加入我們 ｜ 盧臆中 ｜ 中興大學化學系"
    desc = (
        "Openings for graduate and undergraduate students in the Lu group, NCHU."
        if lang == "en"
        else "盧臆中實驗室歡迎碩士班與大學部同學加入，研究題目涵蓋質譜、儀器開發與機器學習。"
    )
    return layout("join", lang, title, desc, body)


def page_facility(lang):
    t = T[lang]
    caps = "".join(
        f"""<div class="theme">
  <h3>{e(pick(c, 'title', lang))}</h3>
  <p>{e(tidy(pick(c, 'body', lang)))}</p>
</div>"""
        for c in FACILITY["capabilities"]
    )
    svcs = "".join(
        f'<li><span class="g-title">{e(pick(sv, "name", lang))}</span></li>'
        for sv in FACILITY["services"]
    )
    by_doi = {p["doi"]: p for p in PUBS if p.get("doi")}
    cases = []
    for c in FACILITY["cases"]:
        refs = "".join(
            f'<li><span class="g-title">{e(by_doi[d]["title"])}</span>'
            f'<div class="g-id"><em>{e(by_doi[d]["journal"])}</em> {by_doi[d]["year"]}, '
            f'{e(by_doi[d].get("volume",""))} · '
            f'<a href="https://doi.org/{d}">doi:{e(d)}</a></div></li>'
            for d in c["dois"] if d in by_doi
        )
        cases.append(
            f"""<div class="case">
  <h3>{e(pick(c, 'title', lang))}</h3>
  <p>{e(tidy(pick(c, 'body', lang)))}</p>
  <div class="case-refs"><span class="k">{e(t['refs'])}</span>
    <ul class="grants">{refs}</ul></div>
</div>"""
        )
    body = page_hero(t["facility"], pick(FACILITY, "tagline", lang)) + f"""<div class="wrap">
<section style="padding-top:34px">
  <p>{e(tidy(pick(FACILITY, 'positioning', lang)))}</p>
  <p><a class="cta" href="{FACILITY['apply_url']}">{e(t['fac_apply'])}</a></p>
  <p class="sec-note">{e(t['fac_note'])}</p>
</section>

<section>
  <h2>{e(t['fac_why'])}</h2>
  <p>{e(tidy(pick(FACILITY, 'intro', lang)))}</p>
</section>

<section>
  <h2>{e(t['fac_cap'])}</h2>
  <div class="themes">{caps}</div>
</section>

<section>
  <h2>{e(t['fac_svc'])}</h2>
  <ul class="grants">{svcs}</ul>
</section>

<section>
  <h2>{e(t['fac_case'])}</h2>
  {''.join(cases)}
</section>
</div>"""
    title = ("Customized Mass Spectrometry Platform | I-Chung Lu | NCHU" if lang == "en"
             else "客製化質譜探測服務平台 ｜ 盧臆中 ｜ 中興大學化學系")
    desc = ("A customized mass spectrometry service platform for reaction intermediates, "
            "cold-spray ionization, and bespoke measurement design. NSTC A-Core Plus."
            if lang == "en" else
            "客製化質譜探測服務平台：液相反應中間體觀測、低溫噴灑游離質譜、"
            "客製化量測設計。國科會 A-Core Plus 尖端核心設施。")
    return layout("facility", lang, title, desc, body)


BUILDERS = {
    "index": page_index,
    "facility": page_facility,
    "research": page_research,
    "publications": page_publications,
    "people": page_people,
    "life": page_life,
    "alumni": page_alumni,
    "teaching": page_teaching,
    "join": page_join,
}


# ------------------------------------------------------------------
def main():
    (ROOT / "zh").mkdir(exist_ok=True)
    written = []
    for lang in LANGS:
        outdir = ROOT if lang == "en" else ROOT / "zh"
        for page in ALL_PAGES:
            (outdir / f"{page}.html").write_text(BUILDERS[page](lang), encoding="utf-8")
            written.append(url(page, lang))

    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{SITE}/{u}</loc><lastmod>{today}</lastmod></url>" for u in written
    )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf-8",
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8"
    )
    (ROOT / "404.html").write_text(
        layout(
            "index",
            "en",
            "Page not found | I-Chung Lu",
            "Page not found.",
            '<div class="wrap"><section><h2>404</h2>'
            '<p>That page does not exist. <a href="index.html">Back to the homepage →</a></p>'
            "</section></div>",
        ),
        encoding="utf-8",
    )
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"✓ {len(written)} pages ({len(ALL_PAGES)} × {len(LANGS)} languages)")
    print(f"  en → /            zh → /zh/")
    print(f"  publications: {len(PUBS)}")
    for s in SECTIONS:
        items = pubs_in(s["id"])
        if items:
            yrs = [p["year"] for p in items]
            print(f"    · {s['title_en']:<42} {len(items):>2} ({min(yrs)}–{max(yrs)})")
    print(f"  grants: {len(GRANTS)}   news: {len(NEWS)}")
    print("  + sitemap.xml, robots.txt, 404.html, .nojekyll")


if __name__ == "__main__":
    main()
