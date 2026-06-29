# iOS セットアップ手順

## 必要なもの
- Mac + Xcode 15 以上
- CocoaPods (`sudo gem install cocoapods`)
- Firebase コンソールへのアクセス権

---

## 1. Xcode プロジェクト作成

1. Xcode → **File > New > Project** → **iOS App**
2. 設定値:
   | 項目 | 値 |
   |---|---|
   | Product Name | `TrainingLog` |
   | Bundle Identifier | `com.traininglog.app` |
   | Interface | **Storyboard** |
   | Language | **Swift** |
3. 保存先を `ios/` フォルダにする

---

## 2. Swift ファイルを追加

以下のファイルをプロジェクトに追加（**Add Files to "TrainingLog"**）:

```
TrainingLog/AppDelegate.swift          ← 自動生成のものと置換
TrainingLog/SceneDelegate.swift        ← 自動生成のものと置換
TrainingLog/ViewController.swift       ← 追加
TrainingLog/ViewController+Bridge.swift← 追加
TrainingLog/Services/TimerManager.swift        ← 追加
TrainingLog/Services/NotificationManager.swift ← 追加
TrainingLog/Services/BillingManager.swift      ← 追加
```

- Xcode が自動生成した `ViewController.swift` は削除して置き換える
- `Main.storyboard` は削除（コードで画面を構築するため）
- Info.plist の `Main storyboard file base name` キーを削除

---

## 3. index.html をバンドルに追加

ローカルフォールバック用に HTML を追加する。

1. **File > Add Files to "TrainingLog"**
2. プロジェクトルートの `index.html` を選択
3. **"Copy items if needed"** にチェック、ターゲット `TrainingLog` にチェック

---

## 4. CocoaPods でライブラリをインストール

```bash
cd ios
pod install
```

以降は **TrainingLog.xcworkspace** を開く（.xcodeproj ではない）。

---

## 5. Firebase iOS アプリを追加【要設定】

1. [Firebase Console](https://console.firebase.google.com) → プロジェクト → **アプリを追加 > iOS**
2. Bundle ID: `com.traininglog.app`
3. **GoogleService-Info.plist** をダウンロード
4. Xcode プロジェクトのルートに追加（Copy items if needed ✓）

---

## 6. Google Sign-In URL スキームを設定【要設定】

1. `GoogleService-Info.plist` を開き `REVERSED_CLIENT_ID` の値をコピー
   - 例: `com.googleusercontent.apps.211414940177-xxxxxxxx`
2. `TrainingLog/Resources/Info.plist` の `REPLACE_WITH_REVERSED_CLIENT_ID` をその値に置換
3. （または Xcode の Info タブ → URL Types から設定）

---

## 7. App Store Connect で In-App Purchase を設定【要設定】

1. [App Store Connect](https://appstoreconnect.apple.com) → マイApp → 新規作成 (`com.traininglog.app`)
2. **機能 > App 内課金** → 非消耗型アイテムを追加
3. プロダクトID: `com.traininglog.app.premium`（変える場合は `BillingManager.swift` の `productId` も更新）

---

## 8. Xcode ケイパビリティを設定

プロジェクト設定 → **Signing & Capabilities** で以下を追加:
- **In-App Purchase**
- **Push Notifications**（通知を使う場合）

---

## 完了後の確認

- [ ] GoogleService-Info.plist が追加されている
- [ ] REVERSED_CLIENT_ID が Info.plist に設定されている
- [ ] `pod install` 済みで `.xcworkspace` を使っている
- [ ] index.html がバンドルに含まれている
- [ ] Signing Team が設定されている

---

## Android との対応関係

| Android | iOS |
|---|---|
| `AndroidBridge` (JavascriptInterface) | `window.AndroidBridge` shim → WKScriptMessageHandler |
| `TimerService` (ForegroundService) | `TimerManager` + UNLocalNotification |
| `NotificationReceiver` (AlarmManager) | `NotificationManager` (UNCalendarNotificationTrigger) |
| `BillingManager` (Google Play Billing) | `BillingManager` (StoreKit 2) |
| `Intent.ACTION_SEND` + FileProvider | UIActivityViewController |
| `Intent.ACTION_GET_CONTENT` | UIDocumentPickerViewController |
| `SharedPreferences` | UserDefaults |
| `google-services.json` | `GoogleService-Info.plist` |
