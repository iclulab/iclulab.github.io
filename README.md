# iclulab.github.io

I-Chung Lu（盧臆中）學術網站原始碼
Department of Chemistry, National Chung Hsing University

**網站**：https://iclulab.github.io （English） · https://iclulab.github.io/zh/ （中文）

---

## 更新內容的唯一方式

**所有內容都在 `_data/` 底下的 YAML 檔。不要直接改 HTML** — HTML 是生成出來的，下次執行 build 腳本就會被覆蓋。

| 檔案 | 內容 |
|---|---|
| `_data/publications.yaml` | 著作清單（唯一真相） |
| `_data/profile.yaml` | 學經歷、獲獎、國科會計畫、聯絡資訊 |
| `_data/research.yaml` | 四條研究主軸的敘事 |
| `_data/sections.yaml` | 著作頁的分區定義 |
| `_data/facility.yaml` | 客製化質譜平台 |
| `_data/people.yaml` | 實驗室成員 |
| `_data/news.yaml` | 動態消息 |

### 更新流程

```bash
pip3 install pyyaml            # 只需執行一次
python3 scripts/build_site.py  # 重新生成全站
```

然後打開 GitHub Desktop → Commit → Push。約兩分鐘後網站自動更新。

### 範例：新增一篇論文

在 `_data/publications.yaml` 最上方加入：

```yaml
- year: 2026
  authors: "Someone, Another, I-Chung Lu*"
  title: "Paper title"
  journal: "Anal. Chem."
  journal_full: "Analytical Chemistry"
  volume: "98, 1234–1240"
  doi: "10.1021/acs.analchem.6c00000"
  role: corresponding
  topics: [maldi, carbohydrate]
  verified: true
```

執行 build 腳本即可，中英文版同時更新。

---

## 設計決策（避免日後誤改）

**雙語採獨立網址而非 JS 切換。** 英文在根目錄、中文在 `/zh/`，兩邊以 `hreflang` 互指。這樣 Google 會分別索引，中文使用者搜「盧臆中 質譜」與英文使用者搜 "I-Chung Lu mass spectrometry" 各自命中對應版本。

**期刊名顯示 CASSI／ISO 4 標準縮寫**（`journal`），另存全名（`journal_full`）供 Schema.org 後設資料使用。縮寫給人看，全名給機器看。

**作者列只在含 Sarah Trimpin 的大型社群綜論才截斷。** 規則寫在 `scripts/pubfmt.py` 開頭的常數。其他論文完整列出所有作者 — 那些是實驗室學生與合作者，名字被列出來本身就是一種肯定。

**著作分三區，用「做了什麼」而非「多久以前」命名**，讀者掃過去看到的是一條研究軌跡：反應動力學 → 游離機制 → 獨立發展應用。

---

## 注意事項

**本倉庫是 Public。** 不要放進：

- 未發表的論文與原始數據
- 學生個資
- 計畫經費金額（已刻意從 `profile.yaml` 移除）

專案資料夾請放在本機（`~/Documents/`），**不要放進 iCloud** — 雲端卸載機制會與 Git 衝突。
