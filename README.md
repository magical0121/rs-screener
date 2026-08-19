# 株式スクリーナー（個人用）

RS × Weinstein Stage × Minervini Trend Template × HQM の日本語スクリーナーです。

## 画面

- 左: **テーマ強度**カード
- 右: 銘柄表（RS / ステージ / 業種 / テーマ / TT / HQM）
- Stage2フィルター、ソート対応

## 確定ロジック

### Stage（Weinstein・米国株仕様）
- 150日SMA近似、SPYベンチマーク
- Stage2 を必須フィルター想定

### TT（Minervini / RyanJHamby）
1. 価格 > 150SMA かつ > 200SMA  
2. 150SMA > 200SMA  
3. 200SMA が約1ヶ月以上上昇  
4. 50SMA > 150SMA > 200SMA  
5. 価格 > 50SMA  
6. 価格 ≥ 52週安値 × 1.30  
7. 価格 ≥ 52週高値 × 0.75  
8. RS slope ≥ +0.15  

表示: 7〜8=強い / 5〜6=普通 / 4以下=弱い

### HQM
- 1M / 3M / 6M / 1Y リターンのパーセンタイル平均
- いずれかが下位25%なら品質ペナルティ
- 表示例: `92（Top）` / `81（Strong）` / `74（Good）`

## ローカルで見る

```bash
cd rs-screener
# 単純に index.html をブラウザで開くだけでもサンプル表示可
python -m http.server 8080
# http://localhost:8080
```

## データを更新する

```bash
pip install -r requirements.txt
python scripts/update_screener.py
```

`data/screener.json` が更新されます。

## GitHub で自動更新する（推奨）

1. このフォルダを GitHub リポジトリに push
2. Settings → Pages → Deploy from branch `main` / `/ (root)`
3. Actions が有効なら、平日の米株引け後に自動で `screener.json` を更新して commit

手動実行: Actions → **Daily Screener Update** → Run workflow

## テーマ定義

`data/themes.json` を編集してテーマ構成銘柄を変更できます。

## 注意

- 投資助言ではありません
- 日次バッチ前提（リアルタイムではない）
- ユニバースは `scripts/update_screener.py` の `DEFAULT_TICKERS` で拡張
