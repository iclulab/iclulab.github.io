"""
pubfmt.py — 著作清單的共用格式化邏輯
build_site.py 與 build_cv.py 都從這裡取用，確保網站與 CV 顯示完全一致。

作者列截斷規則（2026-07-26 修訂）
--------------------------------
只有「Sarah Trimpin 為共同作者」且「作者數 >= 10」的論文才截斷。
其餘論文一律完整列出所有作者，不論人數多寡。

理由：Trimpin 的幾篇綜論屬於大型社群合著（最多 61 位作者），
完整列出會癱瘓版面；其他論文的作者多為實驗室學生與合作者，
名字被列出來本身就是一種肯定，不應省略。

截斷後格式：前三位 + I-Chung Lu + 最後一位，中間以 … 省略
  Sarah Trimpin*, Frank S. Yenchick, Chuping Lee, …, I-Chung Lu, …, Charles N. McEwen

要改規則只需修改本檔開頭的常數，資料檔不必動。
"""

THRESHOLD = 10              # 幾位作者以上才考慮截斷
HEAD_N = 3                  # 保留前幾位
SELF = "I-Chung Lu"
TRUNCATE_ONLY_IF = "Trimpin"  # 作者列須含此關鍵字才截斷；設為 None 則不限
ELLIPSIS = "…"


def split_authors(authors: str) -> list[str]:
    return [a.strip() for a in authors.split(",") if a.strip()]


def format_authors(authors: str, highlight: bool = False) -> str:
    """回傳顯示用的作者字串。highlight=True 時將本人姓名包成 <strong>。"""
    names = split_authors(authors)

    eligible = len(names) >= THRESHOLD and (
        TRUNCATE_ONLY_IF is None or TRUNCATE_ONLY_IF in authors
    )

    if not eligible:
        shown = names
    else:
        self_idx = next(
            (i for i, n in enumerate(names) if n.startswith(SELF)), None
        )
        last_idx = len(names) - 1
        keep = set(range(min(HEAD_N, len(names))))
        keep.add(last_idx)
        if self_idx is not None:
            keep.add(self_idx)

        shown, prev = [], -1
        for i in sorted(keep):
            if i - prev > 1:
                shown.append(ELLIPSIS)
            shown.append(names[i])
            prev = i

    if highlight:
        shown = [
            f"<strong>{n}</strong>" if n.startswith(SELF) else n for n in shown
        ]
    return ", ".join(shown)


ROLE_LABEL = {
    "corresponding":    ("通訊作者",       "Corresponding author"),
    "co-corresponding": ("共同通訊作者",   "Co-corresponding author"),
    "first":            ("第一作者",       "First author"),
    "co-author":        ("共同作者",       "Co-author"),
}


def format_citation(pub: dict, highlight: bool = False) -> str:
    """組出一筆完整引用（不含 DOI 連結）。"""
    return (
        f"{format_authors(pub['authors'], highlight)} "
        f"“{pub['title']}” "
        f"<em>{pub['journal']}</em> "
        f"{pub['year']}, {pub['volume']}."
    )


if __name__ == "__main__":
    import sys, pathlib, yaml

    data = pathlib.Path(__file__).resolve().parent.parent / "_data" / "publications.yaml"
    pubs = yaml.safe_load(data.read_text(encoding="utf-8"))

    print(f"共 {len(pubs)} 筆\n" + "=" * 100)
    for p in pubs:
        n = len(split_authors(p["authors"]))
        mark = f"  [{n} 位作者 → 已截斷]" if n >= THRESHOLD else ""
        print(f"\n{p['year']}  {p['journal']}  ({ROLE_LABEL[p['role']][0]}){mark}")
        print(f"  {format_authors(p['authors'])}")
