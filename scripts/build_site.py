#!/usr/bin/env python3
"""
build_site.py — 由 _data/*.yaml 生成整個網站（中英雙語）

用法：
    .venv/bin/python scripts/build_site.py

需求：
    ~/.local/bin/uv venv --python 3.12 .venv
    ~/.local/bin/uv pip install --python .venv/bin/python -r requirements.txt

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

import functools
import html
import json
import pathlib
import re
import struct
import sys
from datetime import date

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pubfmt import format_authors  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"
SITE = "https://iclulab.com"
LANGS = ("en", "zh", "vi")
HTML_LANG = {"en": "en", "zh": "zh-Hant", "vi": "vi"}
OG_LOCALE = {"en": "en_US", "zh": "zh_TW", "vi": "vi_VN"}

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


@functools.lru_cache(maxsize=None)
def img_dim(rel):
    """讀 JPEG／PNG 檔頭取得原始像素尺寸，輸出成 width／height 屬性。
    瀏覽器在圖片下載完成前就知道該留多少位置，版面不會跳動。
    SVG 與讀不到的檔案回空字串（不寫屬性，行為與以前相同）。"""
    f = ROOT / rel
    if not f.exists() or f.suffix.lower() == ".svg":
        return ""
    data = f.read_bytes()
    w = h = 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
    elif data[:2] == b"\xff\xd8":                      # JPEG：逐段找 SOF 取長寬
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xD8 or 0xD0 <= marker <= 0xD9:
                i += 2
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                break
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return f' width="{w}" height="{h}"' if w and h else ""


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
VI = load("vi")


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


def tri(lang, en, zh, vi):
    """頁面標題與描述這類三語各寫一份的字串。"""
    return {"en": en, "zh": zh, "vi": vi}[lang]


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
        "group_body": "The group's work spans ionization mechanisms, analytical method "
                      "development, and reaction dynamics, so members with quite different "
                      "interests and strengths can each find a project that suits them.",
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
        "phd": "Doctoral Students",
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
        "eyebrow": "Lu Lab · Department of Chemistry, National Chung Hsing University",
        "claim": "Seeing the world other<br>methods struggle to observe",
        "hero_alt": "Custom-built mass spectrometry inlet on the optical table",
        "claim_lede": "The work begins with the mechanisms of ion formation and "
                      "applies that understanding to rapid clinical screening of "
                      "carbohydrates, material identification for plastic recycling, "
                      "and the direct detection of intermediates in catalysis.",
        "cta_research": "What we work on →",
        "cta_join": "Join the lab →",
        "themes_h": "Research directions",
        "r_problem": "Background",
        "r_approach": "Approach",
        "r_result": "Progress",
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
        "join_body": "The group welcomes students with an interest in the principles "
                     "behind a measurement, not only its operation. Projects range across "
                     "ionization mechanisms, instrument and method development, and the "
                     "machine-learning analysis of spectra, so students from different "
                     "backgrounds can find a suitable entry point.",
        "what": "Research topics available",
        "touch": "Get in touch",
        "touch_body": "Please write with a short account of the direction that interests "
                      "you, together with a CV if available. NCHU undergraduates are also "
                      "welcome to call at Room 508 or at the laboratory in Room 102.",
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
        "roles": "Who can join",
        "role_ug_t": "Undergraduate research students",
        "role_ug_b": "Chemistry and related majors are welcome to take up a research "
                     "project in the group. You start with sample preparation, "
                     "instrument operation and data handling, then take on a question "
                     "of your own; several of our undergraduates have gone on to win "
                     "NSTC undergraduate research grants and paper competitions.",
        "role_ms_t": "Master's students",
        "role_ms_b": "Master's students carry most of the group's day-to-day research, "
                     "from ionization mechanisms and method development to the "
                     "detection of reactive intermediates in catalysis. A topic is "
                     "chosen together, matching your background and what you want to "
                     "learn.",
        "role_phd_t": "Doctoral students",
        "role_phd_b": "Suited to those who want to stay with one question long enough "
                      "to publish on it, and to work across the group's collaborations "
                      "in theoretical calculation, electrochemistry and organic "
                      "synthesis.",
        "role_intl_t": "International students",
        "role_intl_b": "Applications are made through NCHU's international admission "
                       "system rather than to the laboratory directly. A page in "
                       "Vietnamese sets out the schedule, scholarships and official "
                       "links:",
        "notfound": "That page does not exist.",
        "home_link": "Back to the homepage →",
        "see_dyn": "See the reaction dynamics publications →",
    },
    "zh": {
        "nav": ["首頁", "研究", "技術平台", "著作", "團隊", "生活", "教學", "加入我們"],
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
        "group_body": "實驗室的研究橫跨游離機制、分析方法開發與反應動力學研究，"
                      "不同興趣與專長的成員都能找到適合自己的研究主題。",
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
        "phd": "博士班學生",
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
        "eyebrow": "盧臆中實驗室 · 國立中興大學化學系",
        "claim": "用質譜看見<br>其它方法難以觀察的世界",
        "hero_alt": "光學桌上的客製化質譜進樣系統",
        "claim_lede": "研究工作由離子生成機制的探討出發，"
                      "並將所得認識應用於醣類的臨床快速篩檢、塑膠回收的材料辨識，"
                      "以及催化反應中間體的直接偵測。",
        "cta_research": "我們在做什麼 →",
        "cta_join": "加入實驗室 →",
        "themes_h": "研究主軸",
        "r_problem": "研究背景",
        "r_approach": "研究方法",
        "r_result": "研究進展",
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
        "join_body": "實驗室歡迎對量測原理本身感興趣的同學，而不僅止於儀器操作。"
                     "研究題目涵蓋游離機制、儀器與方法開發，以及質譜資料的機器學習分析，"
                     "不同背景與專長的同學都能找到合適的切入點。",
        "what": "可參與的研究題目",
        "touch": "聯絡方式",
        "touch_body": "來信請簡述感興趣的研究方向，若有履歷請一併附上。"
                      "中興大學部同學亦可逕至化學館 508 室或 102 實驗室洽談。",
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
        "roles": "歡迎加入的身分",
        "role_ug_t": "專題生（大學部）",
        "role_ug_b": "歡迎化學系與相關科系的大學部同學修習專題研究。從樣品製備、"
                     "儀器操作與資料處理入門，再逐步接手自己的題目；"
                     "實驗室已有多位專題生以此獲得國科會大專生計畫補助與論文競賽獎項。",
        "role_ms_t": "碩士班學生",
        "role_ms_b": "碩士生是實驗室研究的主力，題目涵蓋游離機制、分析方法與儀器開發，"
                     "以及催化反應中間體的偵測。題目會依你的背景與想學的東西一起討論決定。",
        "role_phd_t": "博士班學生",
        "role_phd_b": "適合想在同一個問題上深入到能發表成果的同學，"
                      "也能參與實驗室與理論計算、電化學、有機合成等團隊的跨領域合作。",
        "role_intl_t": "國際學生",
        "role_intl_b": "國際學生循中興大學國際學生招生管道申請，不直接向實驗室報名。"
                       "另有越南文頁面整理了申請期程、獎學金與官方連結：",
        "notfound": "找不到這個頁面。",
        "home_link": "回到首頁 →",
        "see_dyn": "查看反應動力學時期的著作 →",
    },
    # 越南文介面。內容欄位若 _data 裡沒有 *_vi，pick() 會自動退回英文。
    # 2026-11-03 由 Claude 依中英文版翻譯，建議請越南籍學生校稿。
    "vi": {
        "nav": ["Trang chủ", "Nghiên cứu", "Thiết bị", "Công bố", "Thành viên",
                "Đời sống", "Giảng dạy", "Tham gia"],
        "addr": "145 Xingda Rd., South Dist., Taichung City 40227, Taiwan",
        "footer_org": "Khoa Hóa học, Đại học Quốc lập Chung Hsing",
        "inst": "Đại học Quốc lập Chung Hsing",
        "lab": "Phòng thí nghiệm: Phòng 102, Tòa nhà Hóa học",
        "office": "Văn phòng: Phòng 508, Tòa nhà Hóa học",
        "role_title": "Phó Giáo sư · Khoa Hóa học",
        "research": "Nghiên cứu",
        "selected": "Công bố tiêu biểu",
        "all_pubs": "Toàn bộ công bố →",
        "read_more": "Tìm hiểu thêm về nghiên cứu →",
        "news": "Tin tức",
        "group": "Nhóm nghiên cứu",
        "group_body": "Công việc của nhóm trải từ cơ chế ion hóa, phát triển phương pháp "
                      "phân tích, đến động học phản ứng, nên thành viên với sở trường và "
                      "hứng thú khác nhau đều tìm được đề tài phù hợp.",
        "meet": "Xem thành viên →",
        "publications": "Công bố",
        "earlier": "Giai đoạn đầu — động học phản ứng (2003–2008)",
        "earlier_h": "Giai đoạn đầu",
        "grants": "Đề tài nghiên cứu",
        "education": "Học vấn",
        "appointments": "Quá trình công tác",
        "awards": "Giải thưởng",
        "pi": "Trưởng nhóm",
        "assistant": "Trợ lý nghiên cứu",
        "phd": "Nghiên cứu sinh",
        "master": "Học viên thạc sĩ",
        "undergrad": "Sinh viên đại học",
        "alumni": "Cựu thành viên",
        "alumni_lede": "Những người từng học tập trong phòng thí nghiệm, nay đã tiếp tục "
                       "học lên, làm việc trong ngành hoặc nghiên cứu ở nơi khác.",
        "alumni_link": "Xem toàn bộ cựu thành viên →",
        "back_group": "← Quay lại trang thành viên",
        "life": "Đời sống phòng thí nghiệm",
        "life_lede": "Hội nghị, leo núi, chuyển thiết bị vào phòng, và rất nhiều bữa ăn. "
                     "Một nhóm nghiên cứu cũng chính là những con người trong đó.",
        "life_home": "Hội nghị, các chuyến đi và công việc thường ngày của phòng thí nghiệm.",
        "life_more": "Xem đời sống phòng thí nghiệm →",
        "eyebrow": "Phòng thí nghiệm Lu · Khoa Hóa học, Đại học Quốc lập Chung Hsing",
        "claim": "Nhìn thấy thế giới mà các<br>phương pháp khác khó quan sát",
        "hero_alt": "Hệ thống đưa mẫu khối phổ tự chế trên bàn quang học",
        "claim_lede": "Nghiên cứu bắt đầu từ cơ chế hình thành ion, rồi áp dụng hiểu biết đó "
                      "vào sàng lọc lâm sàng nhanh cho carbohydrate, nhận dạng vật liệu phục "
                      "vụ tái chế nhựa, và phát hiện trực tiếp các chất trung gian trong xúc tác.",
        "cta_research": "Chúng tôi làm gì →",
        "cta_join": "Tham gia nhóm →",
        "themes_h": "Hướng nghiên cứu",
        "r_problem": "Bối cảnh",
        "r_approach": "Phương pháp",
        "r_result": "Tiến triển",
        "skip": "Đến nội dung chính",
        "top": "Lên đầu trang",
        "pubs_lede": "Từ động học phản ứng chùm phân tử giao nhau và cơ chế ion hóa, đến "
                     "những ứng dụng phân tích mà nhóm tự phát triển hiện nay.",
        "teaching": "Giảng dạy",
        "teaching_body": "Tôi giảng dạy hóa lý cho cả bậc đại học và sau đại học tại "
                         "Đại học Quốc lập Chung Hsing.",
        "t_awards": "Giải thưởng giảng dạy",
        "courses": "Các môn đã dạy",
        "c_year": "Năm học",
        "c_term": "Học kỳ",
        "c_code": "Mã môn",
        "c_dept": "Dành cho",
        "c_name": "Tên môn",
        "c_type": "Loại",
        "c_req": "Bắt buộc",
        "c_ele": "Tự chọn",
        "courses_note": "Năm học ghi theo lịch Dân Quốc mà các trường đại học Đài Loan sử "
                        "dụng; năm 114 tương ứng với 2025–26. Các môn thí nghiệm và nghiên "
                        "cứu độc lập không được liệt kê.",
        "yt_h": "Hóa lý trên YouTube",
        "yt_name": "狐獴老師的物化課 (Lớp hóa lý của thầy Chồn đất)",
        "yt_body": "Hóa lý không nên đọc như kinh sách. Đó là một cuộc phiêu lưu thú vị "
                   "giữa cái trừu tượng và cái có thật.",
        "yt_cta": "Xem kênh →",
        "join": "Tham gia nhóm",
        "join_body": "Nhóm chào đón những bạn quan tâm đến nguyên lý đằng sau phép đo, không "
                     "chỉ đến thao tác thiết bị. Đề tài trải từ cơ chế ion hóa, phát triển "
                     "thiết bị và phương pháp, đến phân tích phổ bằng học máy, nên sinh viên "
                     "từ nhiều nền tảng khác nhau đều tìm được điểm bắt đầu phù hợp.",
        "what": "Các hướng đề tài có thể tham gia",
        "touch": "Liên hệ",
        "touch_body": "Thư xin ghi ngắn gọn hướng nghiên cứu bạn quan tâm, kèm sơ yếu lý lịch "
                      "nếu có. Sinh viên Đại học Chung Hsing cũng có thể đến trực tiếp phòng "
                      "508 hoặc phòng thí nghiệm 102.",
        "legend": "<b>*</b> là tác giả liên hệ. Tên in <b>đậm</b> là I-Chung Lu. Với các bài "
                  "tổng quan cộng đồng nhiều tác giả viết chung cùng S. Trimpin, danh sách "
                  "tác giả được rút gọn; các bài còn lại liệt kê đầy đủ mọi tác giả.",
        "facility": "Nền tảng khối phổ tùy chỉnh",
        "fac_short": "Thiết bị",
        "fac_why": "Vì sao cần tùy chỉnh",
        "fac_cap": "Chúng tôi làm được gì",
        "fac_svc": "Dịch vụ",
        "fac_case": "Các hợp tác đã thực hiện",
        "fac_apply": "Đăng ký dịch vụ kỹ thuật →",
        "fac_note": "Vận hành như một hạng mục thuộc chương trình thiết bị dùng chung "
                    "A-Core Plus của Hội đồng Khoa học và Công nghệ Quốc gia (NSTC).",
        "fac_home": "Chúng tôi vận hành một nền tảng khối phổ tùy chỉnh mở cho các nhóm "
                    "nghiên cứu khác, phục vụ những phép đo mà trung tâm thiết bị thông "
                    "thường không thực hiện được.",
        "fac_more": "Tìm hiểu nền tảng →",
        "refs": "Công bố liên quan",
        "f_all": "Tất cả",
        "f_lead": "Tác giả chính / liên hệ",
        "s_pubs": "Công bố",
        "s_lead": "Tác giả chính / liên hệ",
        "s_grants": "Đề tài NSTC",
        "s_ongoing": "Đang thực hiện",
        "b_corr": "Tác giả liên hệ",
        "b_cocorr": "Đồng tác giả liên hệ",
        "b_first": "Tác giả thứ nhất",
        "b_inv": "Bài tổng quan được mời",
        "dyn_note": "Động học chùm phân tử giao nhau và quang phân ly, từ thời kỳ nghiên cứu "
                    "sinh và sau tiến sĩ giai đoạn đầu.",
        "updated": "Cập nhật",
        "source": "Mã nguồn",
        "roles": "Chúng tôi nhận những ai",
        "role_ug_t": "Sinh viên đại học làm nghiên cứu",
        "role_ug_b": "Sinh viên ngành hóa và các ngành liên quan có thể tham gia một đề tài "
                     "nghiên cứu trong nhóm. Bạn bắt đầu từ chuẩn bị mẫu, vận hành thiết bị "
                     "và xử lý dữ liệu, rồi nhận một câu hỏi của riêng mình; nhiều sinh viên "
                     "của nhóm đã giành được đề tài nghiên cứu sinh viên của NSTC và giải "
                     "trong các cuộc thi báo cáo khoa học.",
        "role_ms_t": "Học viên thạc sĩ",
        "role_ms_b": "Học viên thạc sĩ đảm nhiệm phần lớn công việc nghiên cứu hằng ngày của "
                     "nhóm, từ cơ chế ion hóa và phát triển phương pháp đến phát hiện chất "
                     "trung gian hoạt động trong phản ứng xúc tác. Đề tài được chọn cùng nhau, "
                     "phù hợp với nền tảng và điều bạn muốn học.",
        "role_phd_t": "Nghiên cứu sinh",
        "role_phd_b": "Phù hợp với người muốn theo đuổi một câu hỏi đủ lâu để công bố, và làm "
                      "việc cùng các hợp tác của nhóm về tính toán lý thuyết, điện hóa và "
                      "tổng hợp hữu cơ.",
        "role_intl_t": "Sinh viên quốc tế",
        "role_intl_b": "Hồ sơ nộp qua hệ thống tuyển sinh quốc tế của Đại học Chung Hsing, "
                       "không nộp trực tiếp cho phòng thí nghiệm. Lịch nộp hồ sơ, học bổng "
                       "và các liên kết chính thức nằm ở phần dưới trang này.",
        "notfound": "Không tìm thấy trang này.",
        "home_link": "Về trang chủ →",
        "see_dyn": "Xem các công bố thời kỳ động học phản ứng →",
    },
}


# ------------------------------------------------------------------
def url(page, lang):
    return f"{page}.html" if lang == "en" else f"{lang}/{page}.html"


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

_GC = (P.get("analytics") or {}).get("goatcounter") or ""
# 沒填代碼就一行程式碼都不放，網站保持零追蹤
ANALYTICS = (
    f'\n<script data-goatcounter="https://{_GC}.goatcounter.com/count"'
    f'\n        async src="//gc.zgo.at/count.js"></script>'
) if _GC else ""


# 語言切換選單。三種語言放在同一顆按鈕底下，按鈕上顯示目前所在的語言。
# 用 <details>／<summary>，沒有 JavaScript 也能展開；位置放在 nav 外面，
# 否則手機版導覽列的橫向捲動會把展開的選單裁掉。
LANG_NAMES = {"en": "English", "zh": "中文", "vi": "Tiếng Việt"}


def lang_switcher(page, cur):
    """三種語言都有完整頁面，切換時停在同一頁。"""
    up = "../" if cur != "en" else ""
    targets = {
        "zh": f"{page}.html" if cur == "zh" else f"{up}zh/{page}.html",
        "en": f"{up}{page}.html",
        "vi": f"{page}.html" if cur == "vi" else f"{up}vi/{page}.html",
    }
    items = ""
    for code in ("zh", "en", "vi"):
        label = e(LANG_NAMES[code])
        if code == cur:
            items += f'<span aria-current="true">{label}</span>'
        else:
            items += f'<a href="{targets[code]}">{label}</a>'
    return (
        f'<details class="langsw"><summary aria-label="Language">{e(LANG_NAMES[cur])}</summary>'
        f'<div class="lang-menu">{items}</div></details>'
    )


def layout(page, lang, title, description, body, jsonld=None):
    t = T[lang]
    ACTIVE = ' class="active"'
    nav = "".join(
        '<a href="{}"{}>{}</a>'.format(rel(p, lang), ACTIVE if p == page else "", label)
        for p, label in zip(PAGES, t["nav"])
    )
    labos = (P.get("links") or {}).get("labos")
    if labos:
        nav += f'<a href="{e(labos)}" target="_blank" rel="noopener">LabOS</a>'
    switch = lang_switcher(page, lang)
    ld = (
        f'\n<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
        if jsonld
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="{HTML_LANG[lang]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}/{url(page, lang)}">
<link rel="alternate" hreflang="en" href="{SITE}/{url(page, 'en')}">
<link rel="alternate" hreflang="zh-Hant" href="{SITE}/{url(page, 'zh')}">
<link rel="alternate" hreflang="vi" href="{SITE}/{url(page, 'vi')}">
<link rel="alternate" hreflang="x-default" href="{SITE}/{url(page, 'en')}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}/{url(page, lang)}">
<meta property="og:image" content="{SITE}/assets/img/lu.jpg?v={asset_hash('assets/img/lu.jpg')}">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
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
  <nav class="main">{nav}</nav>
  {switch}
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
// 語言選單：點選單以外的地方或按 Esc 就收起來（沒有這段也能用，只是要再點一次按鈕）
(function () {{
  var d = document.querySelector('.langsw');
  if (!d) return;
  document.addEventListener('click', function (ev) {{
    if (d.open && !d.contains(ev.target)) d.open = false;
  }});
  document.addEventListener('keydown', function (ev) {{
    if (ev.key === 'Escape' && d.open) {{ d.open = false; d.querySelector('summary').focus(); }}
  }});
}})();
</script>
<footer class="site-footer"><div class="wrap">
  <p>{e(t['footer_org'])}<br>{e(t['addr'])}</p>
  <p>{e(t['office'])} · {e(t['lab'])}</p>
  <p><a href="mailto:{P['contact']['email']}">{P['contact']['email']}</a> ·
     Tel {e(P['contact']['phone'])}</p>
  <p>{e(t['updated'])} {date.today().isoformat()} ·
     <a href="https://github.com/iclulab/iclulab.github.io">{e(t['source'])}</a></p>
</div></footer>{ANALYTICS}
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
    if p.get("feature"):
        f = p["feature"]
        out += f'<a class="badge inv" href="{e(f["url"])}">{e(f["label"])}</a>'
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
            f'aria-label="{e(alt)}"><img src="{src}" alt="{e(alt)}"'
            f'{img_dim(f"assets/img/pubs/{fn}")} loading="lazy"></a>')


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
    <span class="pub-title">{e(p.get(f'title_{lang}') or p['title'])}</span>
    <span class="pub-meta"><em>{e(p.get(f'journal_{lang}') or p['journal'])}</em> <b>{p['year']}</b>{vol}</span>
    <span class="pub-badges">{badges(p, lang)}{doi}</span>
  </div>{fig}
</li>"""


def news_items(lang, limit=None):
    """消息依年份分組成時間軸，年份標在左欄，事件排右欄。"""
    items = NEWS[:limit] if limit else NEWS
    key = f"text_{lang}"
    groups = []
    for n in items:
        y = str(n["date"])[:4]
        if not groups or groups[-1][0] != y:
            groups.append((y, []))
        groups[-1][1].append(n)
    def text_of(n):
        """該語言沒有就退回英文，再退回中文；html_* 欄位可帶連結，原樣輸出。"""
        html = n.get(f"html_{lang}") or n.get("html_en") or n.get("html_zh")
        return html or e(n.get(key) or n.get("text_en") or n["text_zh"])

    out = []
    for y, ns in groups:
        rows = "".join(
            f'<li><time datetime="{e(str(n["date"]))}">{e(str(n["date"])[5:])}</time>'
            f'<span>{text_of(n)}</span></li>'
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


# 著作頁篩選鈕的中文標籤。data-f 仍用英文 key，只有顯示文字換成中文；
# 沒列到的主題自動退回英文（把連字號換成空白）。
TOPIC_ZH = {
    "ambient-ionization": "常壓游離",
    "carbohydrate": "醣類",
    "catalysis": "催化",
    "coordination-chemistry": "配位化學",
    "electrochemistry": "電化學",
    "instrumentation": "儀器開發",
    "ionic-liquid": "離子液體",
    "ionization-mechanism": "游離機制",
    "maldi": "MALDI",
    "molecular-beam": "分子束",
    "organic-synthesis": "有機合成",
    "photodissociation": "光解離",
    "portable-ms": "可攜式質譜",
    "proteomics": "蛋白質體",
    "quantification": "定量分析",
    "reaction-dynamics": "反應動力學",
    "reactive-intermediates": "反應中間體",
    "review": "綜論",
    "water-oxidation": "水氧化",
}


def topic_label(topic, lang):
    if lang == "zh":
        return TOPIC_ZH.get(topic, topic.replace("-", " "))
    return topic.replace("-", " ")


def pub_cards(lang, n=6):
    """首頁的代表圖畫廊：有代表圖的最新幾篇，圖 + 標題 + 期刊年份。"""
    picked = [p for p in main_pubs if pub_figure(p, lang)][:n]
    cards = []
    for p in picked:
        fn = p["doi"].replace("/", "_") + ".jpg"
        src = asset(f"assets/img/pubs/{fn}", lang)
        cards.append(
            f"""<a class="pcard" href="https://doi.org/{p['doi']}">
  <span class="pcard-fig"><img src="{src}" alt="{e(p['title'][:80])}"{img_dim(f"assets/img/pubs/{fn}")} loading="lazy"></span>
  <span class="pcard-title">{e(p['title'])}</span>
  <span class="pcard-meta"><em>{e(p['journal'])}</em> {p['year']}</span>
</a>"""
        )
    return f'<div class="pcards">{"".join(cards)}</div>'


def person_card(p, lang, subdir=""):
    # 換照片時檔名通常不變，網址要帶內容雜湊，瀏覽器與 CDN 才不會繼續拿舊圖
    rel = f"assets/img/people/{subdir}{p['photo']}" if p.get("photo") else ""
    photo = (
        f'<img class="ph" src="{av(rel, lang)}" alt="{e(p["name_en"])}"'
        f'{img_dim(rel)} loading="lazy">'
        if p.get("photo")
        else f'<div class="ph">{e(p["name_zh"][0]) if p.get("name_zh") else "·"}</div>'
    )
    # 中文版以中文姓名為主、英文為輔；英文與越南文版相反
    zh_first = lang == "zh" and p.get("name_zh")
    primary = p["name_zh"] if zh_first else p["name_en"]
    secondary = p["name_en"] if zh_first else p.get("name_zh", "")
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
      <img src="{av('assets/img/hero.jpg', lang)}" alt="{e(t['hero_alt'])}"{img_dim('assets/img/hero.jpg')}>
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
    title = tri(
        lang,
        "I-Chung Lu | Mass Spectrometry & Physical Chemistry | NCHU",
        "盧臆中 I-Chung Lu ｜ 質譜與物理化學 ｜ 國立中興大學化學系",
        "I-Chung Lu | Khối phổ và Hóa lý | Đại học Chung Hsing",
    )
    desc = tri(
        lang,
        "I-Chung Lu, Associate Professor of Chemistry at National Chung Hsing University. "
        "Research on MALDI ionization mechanisms, carbohydrate mass spectrometry with AI "
        "classification, smart plastic identification, and reactive intermediates in catalysis.",
        "盧臆中，國立中興大學化學系副教授。研究領域涵蓋 MALDI 游離機制、"
        "醣類質譜結合 AI 分類、塑膠智慧辨識與回收，以及催化反應中間體的捕捉。",
        "I-Chung Lu, Phó Giáo sư Khoa Hóa học, Đại học Quốc lập Chung Hsing. Nghiên cứu về "
        "cơ chế ion hóa MALDI, khối phổ carbohydrate kết hợp phân loại bằng AI, nhận dạng "
        "nhựa và các chất trung gian hoạt động trong xúc tác.",
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
    def theme_long(th):
        """一條主軸展開成：研究背景 → 研究方法 → 研究進展。"""
        parts = []
        for key in ("problem", "approach", "result"):
            txt = tidy(pick(th, key, lang))
            if txt:
                parts.append(f'<div class="step"><span class="step-k">{e(t["r_" + key])}</span>'
                             f'<p>{e(txt)}</p></div>')
        if not parts:                       # 沒填新欄位就退回原本的一段式
            parts.append(f'<p>{e(tidy(pick(th, "body", lang)))}</p>')
        return f"""<section class="theme-long" id="{th['id']}">
  <div class="theme-head">
    <span class="tag">{e(th['tag'])}</span>
    <h3>{e(pick(th, 'title', lang))}<span class="zh"> · {e(th['title_zh'] if lang != 'zh' else th['title_en'])}</span></h3>
  </div>
  {''.join(parts)}
</section>"""

    themes = "".join(theme_long(th) for th in RESEARCH["themes"])
    body = page_hero(t["research"], pick(RESEARCH, "intro", lang)) + f"""<div class="wrap">
{themes}

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
    title = tri(lang, "Research | I-Chung Lu | NCHU", "研究 ｜ 盧臆中 ｜ 中興大學化學系",
                "Nghiên cứu | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        "Ionization mechanisms, carbohydrate mass spectrometry with AI classification, "
        "smart plastic identification, and reactive intermediates in catalysis.",
        "游離機制、醣類質譜結合 AI 分類、塑膠智慧辨識與回收、催化反應中間體捕捉。",
        "Cơ chế ion hóa, khối phổ carbohydrate kết hợp phân loại bằng AI, nhận dạng nhựa "
        "và chất trung gian hoạt động trong xúc tác.",
    )
    return layout("research", lang, title, desc, body)


def page_publications(lang):
    t = T[lang]
    topics = sorted({x for p in PUBS for x in (p.get("topics") or [])})
    filters = (
        f'<button aria-pressed="true" data-f="all">{e(t["f_all"])}</button>'
        f'<button data-f="lead">{e(t["f_lead"])}</button>'
        + "".join(
            f'<button data-f="t:{e(x)}">{e(topic_label(x, lang))}</button>' for x in topics
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
    title = tri(lang, "Publications | I-Chung Lu | NCHU", "著作 ｜ 盧臆中 ｜ 中興大學化學系",
                "Công bố | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        f"{len(PUBS)} peer-reviewed publications by I-Chung Lu in mass spectrometry, "
        "ionization mechanisms, catalysis, and reaction dynamics.",
        f"盧臆中的 {len(PUBS)} 篇學術著作，涵蓋質譜、游離機制、催化與反應動力學。",
        f"{len(PUBS)} công bố khoa học của I-Chung Lu về khối phổ, cơ chế ion hóa, "
        "xúc tác và động học phản ứng.",
    )
    return layout("publications", lang, title, desc, body)


def page_people(lang):
    t = T[lang]
    def loc(x, k):
        return x.get(f"{k}_{lang}") or x[k]

    ed = "".join(
        f'<li><span class="g-title">{e(loc(x, "degree"))}</span>'
        f'<div class="g-id">{e(loc(x, "institution"))} · {e(loc(x, "years"))}</div></li>'
        for x in P["education"]
    )
    ap = "".join(
        f'<li><span class="g-title">{e(loc(x, "position"))}</span>'
        f'<div class="g-id">{e(loc(x, "org"))} · {e(loc(x, "years"))}</div></li>'
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
  <img class="hero-photo" src="{av('assets/img/lu.jpg', lang)}" alt="I-Chung Lu"{img_dim('assets/img/lu.jpg')}>
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
    + people_group(t["phd"], PEOPLE.get("phd_students") or [], lang) \
    + people_group(t["master"], PEOPLE.get("master_students") or [], lang) \
    + people_group(t["undergrad"], PEOPLE.get("undergraduate_students") or [], lang) \
    + f"""<section>
  <h2>{e(t['alumni'])}</h2>
  <div class="people alumni-preview">{''.join(person_card(m, lang, 'alumni/') for m in ALUMNI_RECENT)}</div>
  <p style="margin-top:18px"><a href="{rel('alumni', lang)}">{e(t['alumni_link'])}</a></p>
</section>""" \
    + "</div>"
    title = tri(lang, "Group | I-Chung Lu | NCHU", "團隊 ｜ 盧臆中 ｜ 中興大學化學系",
                "Thành viên | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        "Members of the Lu group at the Department of Chemistry, National Chung Hsing University.",
        "國立中興大學化學系盧臆中實驗室成員。",
        "Thành viên nhóm nghiên cứu Lu, Khoa Hóa học, Đại học Quốc lập Chung Hsing.",
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
        f'<img src="{base}{fn}" alt="{e(title)}"{img_dim(f"assets/img/album/{fn}")} loading="lazy"></a>'
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
    <img src="{base}{cover}" alt="{e(title)}"{img_dim(f"assets/img/album/{cover}")} loading="lazy">
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
    title = tri(lang, "Lab Life | I-Chung Lu | NCHU", "實驗室生活 ｜ 盧臆中 ｜ 中興大學化學系",
                "Đời sống phòng thí nghiệm | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        "Photos from conferences, group outings, and everyday work in the Lu group "
        "at National Chung Hsing University.",
        "盧臆中實驗室的研討會、出遊與日常照片。",
        "Hình ảnh hội nghị, các chuyến đi và công việc thường ngày của nhóm nghiên cứu Lu.",
    )
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
    title = tri(lang, "Lab Alumni | I-Chung Lu | NCHU", "歷屆成員 ｜ 盧臆中 ｜ 中興大學化學系",
                "Cựu thành viên | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        f"{len(ALUMNI)} former members of the Lu group, Department of Chemistry, "
        "National Chung Hsing University.",
        f"國立中興大學化學系盧臆中實驗室的 {len(ALUMNI)} 位歷屆成員。",
        f"{len(ALUMNI)} cựu thành viên của nhóm nghiên cứu Lu, Khoa Hóa học, "
        "Đại học Quốc lập Chung Hsing.",
    )
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
      <img src="{av('assets/img/pchem-logo.png', lang)}" alt="{e(t['yt_name'])}"{img_dim('assets/img/pchem-logo.png')}>
    </a>
    <div>
      <h3>{e(t['yt_name'])}</h3>
      <p class="yt-tag">{e(t['yt_body'])}</p>
      <p><a class="cta" href="{P['links']['youtube']}">{e(t['yt_cta'])}</a></p>
    </div>
  </div>
</section>
</div>"""
    title = tri(lang, "Teaching | I-Chung Lu | NCHU", "教學 ｜ 盧臆中 ｜ 中興大學化學系",
                "Giảng dạy | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        "Physical chemistry teaching at NCHU by I-Chung Lu, recipient of the "
        "NCHU Distinguished Teaching Award.",
        "盧臆中於中興大學講授物理化學，曾獲中興大學教學特優獎與特優導師。",
        "I-Chung Lu giảng dạy hóa lý tại Đại học Chung Hsing, từng nhận giải thưởng "
        "Giảng dạy Xuất sắc của trường.",
    )
    return layout("teaching", lang, title, desc, body)


def admission_block():
    """越南文版「加入我們」頁下半部：國際學生的申請期程、獎學金與官方連結。
    期程與獎學金取自中興大學國際事務處公告，內容在 _data/vi.yaml。"""
    v = VI
    intakes = "".join(
        f'<li><span class="g-title">{e(i["term"])}</span>'
        f'<div class="g-id">{e(i["apply"])} · {e(i["result"])}<br>{e(i["note"])}</div></li>'
        for i in v["admission"]["intakes"]
    )
    links = "".join(
        f'<li><span class="g-title"><a href="{e(it["url"])}">{e(it["text"])}</a></span></li>'
        for it in v["links"]["items"]
    )
    return f"""<section>
  <h2>{e(v['admission']['heading'])}</h2>
  <p class="justify">{e(v['admission']['lede'])}</p>
  <ul class="grants">{intakes}</ul>
  <p class="justify">{e(v['admission']['caveat'])}</p>
</section>
<section>
  <h2>{e(v['scholarship']['heading'])}</h2>
  <p class="justify">{e(v['scholarship']['body'])}</p>
</section>
<section>
  <h2>{e(v['links']['heading'])}</h2>
  <ul class="grants">{links}</ul>
</section>"""


def page_join(lang):
    t = T[lang]
    roles = "".join(
        f'<li><span class="g-title">{e(t[f"role_{k}_t"])}</span>'
        f'<div class="g-id">{e(t[f"role_{k}_b"])}</div></li>'
        for k in ("ug", "ms", "phd")
    )
    intl = f'<div class="g-id">{e(t["role_intl_b"])}'
    if lang != "vi":                                   # 越南文版本頁下方就是申請資訊
        vi_href = "vi/join.html" if lang == "en" else "../vi/join.html"
        intl += f' <a href="{vi_href}">Tiếng Việt →</a>'
    roles += f'<li><span class="g-title">{e(t["role_intl_t"])}</span>{intl}</div></li>'

    body = page_hero(t["join"], t["join_body"]) + f"""<div class="wrap">
<section style="padding-top:34px"><h2>{e(t['roles'])}</h2><ul class="grants">{roles}</ul></section>
<section><h2>{e(t['what'])}</h2>{theme_blocks(lang)}</section>
{admission_block() if lang == "vi" else ""}
<section>
  <h2>{e(t['touch'])}</h2>
  <p>{e(t['touch_body'])}</p>
  <p><a class="cta" href="mailto:{P['contact']['email']}">{P['contact']['email']}</a></p>
</section>
</div>"""
    titles = {
        "en": "Join Us | I-Chung Lu | NCHU",
        "zh": "加入我們 ｜ 盧臆中 ｜ 中興大學化學系",
        "vi": "Tham gia nhóm | I-Chung Lu | NCHU",
    }
    descs = {
        "en": "Openings for graduate and undergraduate students in the Lu group, NCHU.",
        "zh": "盧臆中實驗室歡迎碩士班與大學部同學加入，研究題目涵蓋質譜、儀器開發與機器學習。",
        "vi": VI["subtitle"],
    }
    return layout("join", lang, titles[lang], descs[lang], body)


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
    title = tri(lang, "Customized Mass Spectrometry Platform | I-Chung Lu | NCHU",
                "客製化質譜探測服務平台 ｜ 盧臆中 ｜ 中興大學化學系",
                "Nền tảng khối phổ tùy chỉnh | I-Chung Lu | NCHU")
    desc = tri(
        lang,
        "A customized mass spectrometry service platform for reaction intermediates, "
        "cold-spray ionization, and bespoke measurement design. NSTC A-Core Plus.",
        "客製化質譜探測服務平台：液相反應中間體觀測、低溫噴灑游離質譜、"
        "客製化量測設計。國科會 A-Core Plus 尖端核心設施。",
        "Nền tảng dịch vụ khối phổ tùy chỉnh: quan sát chất trung gian trong phản ứng "
        "pha lỏng, ion hóa phun lạnh và thiết kế phép đo theo yêu cầu. NSTC A-Core Plus.",
    )
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
    written = []
    for lang in LANGS:
        outdir = ROOT if lang == "en" else ROOT / lang
        outdir.mkdir(exist_ok=True)
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
