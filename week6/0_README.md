# Week 6 預警與根因分析

這個資料夾就是 Week 6 實作課要用的全部東西。**不需要再去別的地方下載任何檔案。**

把它放在桌面 (Desktop) ,然後照檔名前面的數字 0、1、2、3、4 依序走。

## 上課流程

| 順序 | 檔案 | 什麼時候 | 這一步在做什麼 |
| :--- | :--- | :--- | :--- |
| 0 | `0_README.md` | 拿到這一包就先讀 | 你正在看的這一份。裝環境、開 JupyterLab、出問題怎麼查 |
| 1 | `1_pkg_checker.ipynb` | **上課一開始,大家一起跑** | 檢查這台機器裝好了沒。缺什麼、怎麼補,它會直接寫出來。前一天先跑過更好,當場就只是確認 |
| 2 | `2_lab06_forecasting.ipynb` | 上課第一段 | Lab 06 預警: 從「已經出事」推進到「快要出事」 |
| 3 | `3_lab07_root_cause_analysis.ipynb` | 上課第二段 | Lab 07 根因分析: 五個 port 一起亮的時候,誰才是根因 |
| 4 | `4_grafana.py` | 第二段的最後 | 把兩本 lab 的 case 都推上 Grafana,看它們在值班畫面長什麼樣子 |

沒有編號的檔案不用自己打開,是上面這些檔案在用的 (資料、投影片圖、重播服務、錄好的模型回應) 。

### 每一段的教學目的

**Lab 06 對應理論講義單元 07。** 要回答的問題是: 同樣是晚上流量在漲,為什麼有一晚會把出口打滿、另一晚不會,而且能不能在打滿之前就分辨出來。做法分成三層: 先用 Prophet 學「這個時刻的正常值是多少」,再用一個殘差模型學「不正常正在往哪個方向走」,最後把推算值跟容量門檻比,連續幾格越線才發預警。重點不在模型準不準,在於**這條規則要用召回率、誤警率與提前量一起評估**,而且每一個都要有對照組。

**Lab 07 對應理論講義單元 08。** 要回答的問題是: 一場事故裡五個 port 同時異常,排在最前面的症狀通常不是根因。做法是把講義的五項證據各算成一個分數再融合排名 (幅度 A、時序 T、拓樸 G、統計與因果 C、知識 K) ,接著用 BM25 從一份可以抽換的知識包撈出相關的維運手冊,連同證據一起交給語言模型寫診斷,最後用 Hit@1 與 MRR 評估,並把值班人員的核可寫回知識包。**課堂上不需要 API 金鑰**,錄好的模型回應就在 `llm_diagnoses.json` 裡。

**`4_grafana.py` 是收尾,而且是課程的一部分,不是加分題。** 前面兩本算出來的東西如果只留在 notebook 裡,值班的人看不到,那這一整週就沒有落地。這一步用 Docker 起一組 Prometheus 加 Grafana,**把兩本 lab 的 case 各自重播成一張儀表板**:

- **Lab 06 預警**: 2/25 與 2/26 那兩晚,看實際流量、預測區間、往前推算值撞上容量線,以及預警旗標在越線之前就亮起來
- **Lab 07 根因**: 事故 L,看五個 port 的症狀、Score(c) 排名,以及「分數最高的那個 port 不是 z 最大的那個」

同時也說明教學版 (notebook 算完寫 CSV,再重播) 跟正式環境 (模型跑在長駐服務裡) 差在哪裡: 從 Prometheus 往後看,兩者完全一樣。

## 課前準備

### 第一步: 建立 Python 環境

只要做一次。開一個終端機視窗:

- macOS: 打開「終端機」 (Terminal)
- Windows: 打開「Anaconda Prompt」 (從開始功能表找,不是一般的命令提示字元)

先切換到這個資料夾。指令是 `cd` 加上資料夾路徑:

```
cd ~/Desktop/week6                  # macOS
cd %USERPROFILE%\Desktop\week6      # Windows
```

**前幾週已經建過課程環境的人** (環境名字是 `aiops-anomaly-zero-to-hero`) ,只要補上 Week 6 多用到的幾個套件:

```
conda env update -f environments/environment.macos.yml      # macOS
conda env update -f environments\environment.windows.yml    # Windows
conda activate aiops-anomaly-zero-to-hero
```

不要加 `--prune`,那會把別的 lab 需要的套件刪掉。

**完全還沒有環境的人**,從頭建一個:

```
conda env create -f environments/environment.macos.yml      # macOS
conda env create -f environments\environment.windows.yml    # Windows
conda activate aiops-anomaly-zero-to-hero
```

這一份環境檔只列 Week 6 真的會 import 的套件,從頭建大約下載 700 MB 到 1 GB,依網路速度需要 5 到 20 分鐘。**請在上課前做完。**

### 另外要先裝 Docker Desktop

最後一段的 Grafana 是課程內容,不是加分題,而它需要 Docker。**請在上課前裝好並開起來一次**,確認工作列的鯨魚圖示顯示執行中。

- macOS 與 Windows: 到 <https://www.docker.com/products/docker-desktop/> 下載 Docker Desktop,照安裝精靈裝完後打開它
- Linux: 裝 Docker Engine 即可

裝完之後 `1_pkg_checker.ipynb` 會告訴你它有沒有看到 Docker。當天真的來不及裝也不會卡住前面兩本 notebook,那一段改看講師的畫面,`screenshots/` 裡也有接好之後的樣子。

### 第二步: 打開 JupyterLab

**要在這個資料夾裡面打開,這件事很重要。** 承接上一步的終端機視窗 (已經 `cd` 進來,也已經 `conda activate` 過) ,直接執行:

```
jupyter lab
```

瀏覽器會自己打開。左邊的檔案列表應該看得到 `2_lab06_forecasting.ipynb` 與 `data` 這個資料夾。**看不到就代表開錯位置了**,關掉重來一次,先 `cd` 到 week6 再執行 `jupyter lab`。

### 第三步: 跑 1_pkg_checker.ipynb

打開 `1_pkg_checker.ipynb`,選單列按 **Run > Run All Cells**,等它跑完。它會真的配一個很小的 Prophet 模型,所以不是瞬間結束: 在一台 Apple Silicon 的 Mac 上實測 11 秒。**第一次在一台新機器上跑會明顯久很多** (幾分鐘) ,因為 Prophet 背後的 cmdstanpy 要先編譯一次模型,之後每次都用編譯好的。畫面沒有反應不代表當掉。

最後一格會印出一張總表。**全部顯示通過就可以開始上課。** 有任何一列顯示失敗,那一列會直接寫出該怎麼修;修不掉就把最後那段可以複製的文字傳給講師。

上課一開始會請大家再跑一次這一本,當場一起把沒裝好的補起來,所以前一天先跑過的人當天只是確認。

## 資料夾裡有什麼

依序要開的五個,前面帶編號:

| 檔案 | 用途 |
| :--- | :--- |
| `0_README.md` | 這一份 |
| `1_pkg_checker.ipynb` | 環境檢查。上課前先跑這一本 |
| `2_lab06_forecasting.ipynb` | Lab 06 從流量預測到預警規則 |
| `3_lab07_root_cause_analysis.ipynb` | Lab 07 根因分析 |
| `4_grafana.py` | 一行指令把 Grafana 環境帶起來,兩個 case 各一張儀表板 |

其餘的不用自己開,是上面那些檔案在用的:

| 檔案 | 用途 |
| :--- | :--- |
| `data/synthetic/` | 課程資料。三個 CSV 加上產生它們的模擬器程式 |
| `outputs/workshop/` | 兩本 notebook 算完的結果會寫在這裡 (含 Grafana 要重播的兩份 case CSV) 。一開始是空的 |
| `slides/` | 講義單元 07 與 08 的投影片圖,notebook 裡面會引用 |
| `screenshots/` | Grafana 接好之後長什麼樣子的截圖 |
| `environments/` | conda 環境定義檔,三個作業系統各一份。只列 Week 6 會用到的套件 |
| `infra/stack/` | Grafana 環境的設定 (Docker Compose、Prometheus 設定、兩張儀表板) |
| `results_exporter.py` | 把 notebook 算完的 CSV 重播給 Prometheus 抓的服務 |
| `llm_diagnoses.json` | 錄好的模型回應。沒有 API 金鑰也能跑完 Lab 07 |

## 兩本 notebook 的執行順序

先 `2_lab06_forecasting.ipynb`,再 `3_lab07_root_cause_analysis.ipynb`。

兩本都是從第一格開始,按 **Run > Run All Cells** 一路跑到底。在一台 Apple Silicon 的 Mac 上跑兩次實測: Lab 06 是 104 秒與 145 秒 (它要配好幾個 Prophet 模型與殘差模型,同一台機器上下浮動是正常的) ,Lab 07 兩次都是 8 秒以內。你的機器慢一些是正常的,但如果 Lab 06 超過十分鐘還沒跑完,那多半是 Prophet 第一次編譯還沒結束。

兩本各自獨立讀 `data/synthetic/` 的原始資料,所以 Lab 07 不會因為 Lab 06 沒跑完而失敗。唯一的例外是最後的 Grafana 那一段,它要用兩本各自寫出來的 `outputs/workshop/forecast_case_K.csv` 與 `rca_case_L.csv`,所以那一段之前兩本都要先跑完。

## 上 Grafana: 兩個 case 各一張儀表板

這一段要 Docker。先確認 Docker Desktop 已經打開 (圖示顯示執行中) ,而且**兩本 notebook 都已經跑完**,因為要重播的兩份 CSV 是它們寫出來的。然後在 week6 資料夾裡:

```
python 4_grafana.py
```

它會依序檢查 Docker、檢查兩份 CSV 在不在、檢查四個 port 有沒有被佔用,然後啟動四個服務 (兩支重播程式、Prometheus、Grafana) ,最後打開兩張儀表板:

- **Lab 06 預警課堂案例 (兩晚對照)**
- **Lab 07 RCA 課堂案例 (事故 L)**

重播是循環的,一輪大約八分鐘,走完會從頭再來。看完之後關掉:

```
python 4_grafana.py down
```

只想檢查、不想啟動: `python 4_grafana.py health`。看服務說了什麼: `python 4_grafana.py logs`。

**port 被佔住是最常見的問題。** 用到的是 3000 (Grafana)、9090 (Prometheus)、8010 與 8011 (兩支重播程式) ,其中一個被佔住的時候程式會直接告訴你是哪一個。最常見的原因是前幾週課自己用 brew 或 systemd 裝的 Grafana 或 Prometheus 還在跑。兩個做法二選一: 關掉那個服務,或在 `infra/stack/.env` 裡設一個沒被佔用的 port,例如 `WEEK6_GRAFANA_PORT=3001`。

## 常見問題

**圖上的中文變成空白方框。** matplotlib 找不到中文字型。`1_pkg_checker.ipynb` 的字型那一段會告訴你這台機器找到的是哪一個,以及找不到的時候該裝什麼。

**Windows 上 `conda env create` 卡住或 Prophet 裝不起來。** 先確認是用「Anaconda Prompt」而不是一般的命令提示字元。另外,如果 Windows 使用者名稱含有中文或空白,Prophet 背後的編譯步驟可能會失敗;這種情況把 week6 資料夾改放到 `C:\week6` 再跑一次。

**notebook 第一格就報 FileNotFoundError,說找不到課程資料。** JupyterLab 不是從 week6 資料夾打開的。關掉它,先 `cd` 到 week6,再執行 `jupyter lab`。

**notebook 裡的流程圖顯示成一堆文字而不是圖。** 那些圖是 mermaid,需要 JupyterLab 4.1 以上。用 VS Code 打開 notebook 也會變成純文字。請用 `jupyter lab` 打開。

**Lab 07 說找不到 `llm_diagnoses.json`。** 那個檔案要跟 notebook 放在同一層。整包解壓縮的時候如果只挑了幾個檔案出來,就會少掉它。
