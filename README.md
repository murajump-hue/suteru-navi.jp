# 捨てるナビ（suteru-navi.jp）

住んでいる地域と捨てたい粗大ごみから、自治体に出すか業者に頼むか、どの捨て方がいいかを比較する静的サイトです。
自治体の公式情報から品目別の手数料を取り込み、「まとめて計算」ツール付きの市区町村ページを生成します。
構成は車検最安ナビ（shaken-navi）と同じで、GitHub に push すると Cloudflare が自動で再公開します。

## 仕組み

```
data/fees/<自治体コード>.json  ── 品目別手数料・申込方法・受付時間など（自治体ごと）
        │
scripts/build_site.py ── dist/ に静的サイトを生成（Cloudflare のビルドで実行）
        │
Cloudflare（Workers の静的アセット）── push を検知して再公開

毎月3日 GitHub Actions ── scripts/check_updates.py で料金ページの変更を確認
                          変更があれば失敗して通知メール → 内容を確認して data/fees を直す
```

## フォルダ構成

| パス | 内容 |
| --- | --- |
| `data/municipalities.csv` | 全国1,741市区町村のマスタ（団体コード・名称・読み・公式サイト） |
| `data/research_sodai_pages.csv` | 全国の粗大ごみページの探索結果（ページURL・公開形式・受付システム） |
| `data/fees/*.json` | 自治体ごとの料金データ。このファイルがある自治体だけページを作る |
| `data/page_hashes.json` | 料金ページの変更確認用 |
| `scripts/extract_fees.py` | 公式ページの表・受付システムの品目一覧から手数料を取り込む |
| `scripts/build_site.py` | `data/` から `dist/` にサイトを生成 |
| `scripts/check_updates.py` | 料金ページの変更確認 |
| `scripts/common.py` | 都道府県、よく捨てるもののボタンなどの共通定義 |
| `templates/` | トップ・市区町村・このサイトについて・404 |
| `static/` | デザイン（CSS）とアイコン |
| `config.json` | サイト名、URL、GA4 ID、アフィリエイトリンク |

## 初回のセットアップ

### 1. GitHub にリポジトリを作る

1. GitHub で新しいリポジトリ `suteru-navi` を作る（非公開で可）。
2. このフォルダを push する。
   ```
   cd suteru-navi
   git init && git add . && git commit -m "初回"
   git branch -M main
   git remote add origin https://github.com/murajump-hue/suteru-navi.git
   git push -u origin main
   ```

### 2. Cloudflare につなぐ（車検最安ナビと同じ）

1. Cloudflare のダッシュボードで Workers & Pages → 作成 →「Gitに接続」→ `suteru-navi` を選ぶ。
2. ビルドの設定
   - ビルドコマンド：`pip install -r requirements.txt && python scripts/build_site.py`
   - デプロイコマンド：`npx wrangler deploy`（`wrangler.jsonc` が `dist/` を公開する）
   - 環境変数：`PYTHON_VERSION` = `3.12`
3. デプロイ後、`suteru-navi-jp.<アカウント>.workers.dev` で表示を確認する。

### 3. 独自ドメイン suteru-navi.jp をつなぐ

Cloudflare に追加済みの `suteru-navi.jp` を、プロジェクトの「設定 → ドメインとルート」でカスタムドメインとして追加する（`www.suteru-navi.jp` も）。

## 自治体を追加する

```
# 公式ページの表から（品目・手数料の列がある表）
python scripts/extract_fees.py html <自治体コード> <料金ページのURL> [--table-filter 表見出しの文字]
# sodai-xxx.jp/eco 系の受付システムから（Playwright が必要）
python scripts/extract_fees.py eco <自治体コード> <品目一覧のURL>
```
取り込んだら `data/fees/<コード>.json` に、申込方法（web, tel, tel_hours）、処理券の金額（tickets）、
1回の点数（limit）、収集までの目安（wait）などを公式ページを見て書き足す。
最後に `python scripts/check_updates.py --save` で確認用のハッシュを更新する。

## あとで設定するもの

- **GA4**：`config.json` の `ga4_id`。業者リンクのクリックが `partner_click` イベントで送られる。
- **アフィリエイト**：`config.json` の `affiliate`。アールクリーニング・ECOクリーンはサービス内容と対応エリアを確認してから `enabled` を true にする。
- **お問い合わせ**：Google フォームを作ったら `contact_form` にURLを入れる。

## 手元で動かす

```
pip install -r requirements.txt
python scripts/build_site.py
cd dist && python -m http.server 8000
```
