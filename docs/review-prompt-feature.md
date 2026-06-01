# レビュー促進機能（In-App Review）

## 概要
ユーザーにGoogleフォームではなくPlayストアのレビューを促す機能。アプリの価値を体感した「良い瞬間」に、Google公式の In-App Review をさりげなく1回だけ表示する。加えて、設定画面に「アプリを評価する」ボタンを常設し、ユーザー操作で確実にストアへ遷移できるようにする。

## 設計・方針
- **方式**: Google Play In-App Review API（`com.google.android.play:review-ktx:2.0.2`）をメインに採用。
- **ポリシー遵守**: In-App Review の前に「気に入った？はい/いいえ」の感情ゲートを置くのはGoogle規約違反のため行わない。良い瞬間に静かに1回呼ぶだけ。表示可否・結果はGoogle側が制御し、アプリには返らない仕様。
- **トリガー**: 累計記録（`records`）が **7件** に達し、かつ未依頼（`localStorage.review_requested !== '1'`）のときに1回だけ呼ぶ。`saveRecord()` 内をフック地点とする。
- **手動経路**: 設定 → データ・サポート に「⭐ アプリを評価する」ボタン。`openPlayStore()` で `market://details?id=...`（無ければブラウザ）を開く。

## 詳細
### ネイティブ（MainActivity.kt / AndroidBridge）
- `requestReview()`: `ReviewManagerFactory.create()` → `requestReviewFlow()` → 成功時 `launchReviewFlow()`。失敗時は無視。
- `openPlayStore()`: `market://` インテント。Playストア非搭載端末は https フォールバック。
- import 追加: `com.google.android.play.core.review.ReviewManagerFactory`

### build.gradle
- 依存追加: `implementation 'com.google.android.play:review-ktx:2.0.2'`
- versionCode 14 → 15 / versionName 1.1.3 → 1.1.4

### Web（index.html ×2: ルート と app/src/main/assets）
- `maybeRequestReview()`: 閾値判定＋1回限りガード＋1.5秒ディレイで `AndroidBridge.requestReview()`
- `rateApp()`: `AndroidBridge.openPlayStore()`、ブラウザ版は `window.open` フォールバック
- `saveRecord()` の保存後に `maybeRequestReview()` を呼ぶ
- 設定画面（`#contact-section` 直後）に「アプリを評価する」ボタンを追加

## テスト状況・残作業
- JS構文チェック: OK（node --check）
- **未実施**: Gradleビルド／実機確認（このCLI環境にGradle wrapper・Android SDKが無いため）。Android Studioでリビルドして確認が必要。
- In-App Review は実機（Playストア配信ビルド）でのみ正しく動作。デバッグビルドでは表示されないことがあるため、内部テストトラックで確認するのが確実。

## 再発防止・注意
- index.html を変更したら必ず `/index.html` と `/app/src/main/assets/index.html` の両方を更新（本実装でも両方反映済み）。
