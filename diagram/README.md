# 圖表來源

這個目錄裡的 `.drawio` 是所有課程圖表的唯一來源。`labs/workshop/diagrams/` 與
`labs/self-study/diagrams/` 底下的 `.svg` 是產生出來的，不要手動編輯：下一次 build
會直接覆蓋掉。

```text
diagram/*.drawio  ->  drawio -x -f svg  ->  infra/svg_flatten  ->  labs/*/diagrams/*.svg
```

## 改一張圖

用 draw.io 打開 `.drawio`，改完存檔，然後跑：

```bash
python infra/build_diagrams.py --only lab02_detection_methods
python infra/build_diagrams.py                 # 全部重建
python infra/build_diagrams.py --check         # 只檢查有沒有落後於來源
```

沒有裝 draw.io 的話，`--check` 仍然可以跑，build 不行：

```bash
brew install --cask drawio
```

## 為什麼 build 有第二段

draw.io 匯出 SVG 時，每一個標籤會存兩份：一份是 `<foreignObject>` 裡的 HTML，另一份是
同一段文字的 base64 PNG，給不支援 foreignObject 的 renderer 當 fallback。兩份會各自
漂移，而讀者看到哪一份取決於他用什麼開。JupyterLab 和 VS Code 讀 foreignObject，
GitHub 的 notebook viewer 會把 foreignObject 濾掉，落到那張圖片上。

這個 repo 就發生過：SVG 被手動改成英文之後，PNG fallback 裡還是舊的中文，帶著全形括號
與 `→`。`infra/svg_flatten.py` 把每個標籤改寫成原生的 `<text>`，只留一份，所有 renderer
讀到的都一樣，檔案也從 4.4 MB 掉到 156 KB。

## 送出去之前

用 check-drawio-layout skill 驗證來源，它檢查 10 px grid、connector 是否掛在真的 cell 上、
peer 尺寸是否一致、標籤長度與字級：

```bash
python3 $MIND_ROOT/skill/entries/diagram/check-drawio-layout/scripts/check_drawio_layout.py \
    diagram/lab02_detection_methods.drawio
```

十三個來源目前全部通過。標籤超過 90 字會被擋下來，那是刻意的：圖上的標籤負責一句主張，
論證留在顯示這張圖的 notebook 文字裡。
