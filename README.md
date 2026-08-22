# Stage2 Entry スクリーナー

12週高値ブレイク + 30週SMA上（Lookahead ON相当）で **Stage2背景が入った瞬間** の米国株を日次抽出します。

## 判定ロジック

- 週足終値 > 直近12週の終値高値（現在週除く）
- 週足終値 > 30週SMA
- 前週未達 & 今週達成 → **Entry**
- 今週も達成中 → **Active**

日足を週足（W-FRI）にリサンプルし、未確定の今週を含めるため Lookahead ON 相当です。

## ユニバース

- 株価 ≥ $0.75
- 20日平均出来高 ≥ 50万株
- 売買代金 ≥ $1M

## 表示

- RS（3Mリターン順位）
- 業種 / 業種スコア / 業種強度
- ブレイク% / 30週乖離
- Entry / Active 区分

TT・HQM・本/再/目前・品質フィルターは含みません。

## 更新

```bash
pip install -r requirements.txt
python scripts/update_screener.py
```

GitHub Actions: 平日の米引け後に自動実行（`workflow_dispatch` で手動可）。

## 既存 rs-screener への入れ方

1. このフォルダの内容でリポジトリを上書き（または差し替え）
2. `data/themes.json` は任意（業種スコアは業種名ベース）
3. Pages は `main` / root のまま
