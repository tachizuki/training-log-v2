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

### 文章作成（日本語技術文書）
- note記事・解説文・ブログ・技術ドキュメント・提出物など、**まとまった日本語の文章**を書く／推敲するときは `japanese-tech-writing` スキル（`.claude/skills/japanese-tech-writing/SKILL.md`）の規範に従う
- 「LLMっぽい表現の禁止」「冗長の排除」は**常に**意識する（チャット応答でも空虚な装飾・予告総括・空虚な形容を避ける）
- 「一文一行・脚注」などの整形規範は記事・原稿などの成果物に適用し、カジュアルなチャット応答には適用しない
