# CLAUDE.md — プロジェクトルール

## 必須ルール

### バージョン管理
- Kotlinコード（`app/src/main/java/`）を変更したら**必ず同じコミットでversionCodeを+1、versionNameも上げる**
- 聞かれる前に自分でやること

### ファイル更新
- HTMLを変更する際は**必ず両方更新する**
  - `/index.html`（Cloudflare Pages = 実際にアプリが読み込むファイル）
  - `/app/src/main/assets/index.html`（ローカルフォールバック）

### git push後
- Kotlinコード／Manifest／build.gradleを変更したpushの後は、以下をセットで伝える
  1. 「**ローカルで`git pull origin main`してからリビルドしてください**」
  2. そのビルドのリリースノート（変更内容を箇条書きで）

### 実装前確認
- 頼まれていない機能を勝手に実装しない
- 実装前にテストすること
