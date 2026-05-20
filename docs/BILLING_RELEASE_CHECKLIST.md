# Google Play Billing 動作確認 & リリース直前チェックリスト

## 1. Play Console 側の準備（必須）

### 1-1. サブスクリプション商品の作成

1. **アプリの登録**（まだなら）。パッケージ名 `com.traininglog.app`
2. **アプリ内アイテム → サブスクリプション → 新規作成**
   - 商品ID: `premium_monthly` （`BillingManager.PRODUCT_PREMIUM_MONTHLY` と一致）
   - 名前: PhysiqueLog プレミアム
   - 価格設定:
     - 日本 ¥400 / 米国 $2.99 / 他国は Play Console の自動換算で OK
3. **基本プラン (Base plan) の作成**
   - 課金期間: **月次 (P1M)**
   - 自動更新: ON
   - 状態: 有効

### 1-2. 無料体験オファーの追加 ★今回の主作業

サブスクリプション商品の中の「**オファー**」タブから:

1. 「**新しいオファーを作成**」
2. オファータイプ: **無料体験 (Free trial)**
3. 期間: **14日間 (P14D)**
4. 適用条件:
   - **対象**: このサブスクリプションを購入したことがない新規ユーザーのみ
   - **資格**: デフォルトのままで OK (Play Billing が自動で「初回購入か」を判定)
5. ターゲット国: 全国対応(または日本+米国のみ)
6. 状態: **有効化**

これで初回ユーザーが購入フローを起動すると、最初に14日間無料体験のオファーが表示され、期間内のキャンセルでは課金されない動作になります。

### 1-3. テスター追加

「設定 → ライセンステスト → ライセンスをテスト」に自分のGmailを追加。これでテスト購入(課金されず購入扱い)が可能。

### 1-4. aab を内部テストトラックにアップ（最初の購入テストには必須）

## 2. リリースビルドの設定（次の作業）

```gradle
// app/build.gradle に追加
android {
  signingConfigs {
    release {
      storeFile file(System.getenv("KEYSTORE_PATH") ?: "release.keystore")
      storePassword System.getenv("KEYSTORE_PASS")
      keyAlias System.getenv("KEY_ALIAS")
      keyPassword System.getenv("KEY_PASS")
    }
  }
  buildTypes {
    release {
      minifyEnabled true
      shrinkResources true
      proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
      signingConfig signingConfigs.release
    }
  }
}
```

keystore は `keytool -genkey -v -keystore release.keystore -keyalg RSA -keysize 2048 -validity 10000 -alias physiquelog` で作成。
**絶対に紛失しないこと。紛失するとアプリのアップデート不可。** クラウド等にバックアップ推奨。

## 3. リリース直前にコードで必ずやる

1. `index.html` の `DEV_UNLOCK_PREMIUM` を **`false` に戻す**
   ```js
   const DEV_UNLOCK_PREMIUM = false;
   ```
2. `versionCode` / `versionName` を更新（必要に応じて）
3. `cp app/src/main/assets/index.html index.html` でルートも同期
4. リリースビルド: `./gradlew bundleRelease` → `app/build/outputs/bundle/release/app-release.aab`
5. Play Console の内部テストにアップロード

## 4. テスト購入の動作確認手順

1. ライセンステスター登録済みのGmailアカウントで端末にログイン
2. アプリ起動 → プロフィール → 「アップグレード」ボタンタップ
3. ペイウォール画面 → 「¥300/月で始める」をタップ
4. Google Play の購入ダイアログが開く（"テスト購入"と表示される）
5. 購入 → 数秒でアプリに戻り `onPremiumPurchased()` が走り、有料機能がアンロックされる
6. 一度アプリを完全終了 → 再起動して、プレミアムが維持されているか確認
7. **キャンセル動作確認**: Play ストア → 定期購入 → PhysiqueLog → キャンセル → アプリ再起動で `onPremiumRestored(false)` が走り無料プランに戻ることを確認

## 5. 確認ポイント

- ペイウォール内の価格表示は現状ハードコード `¥400/月` 。Play Console 側の価格と一致させること
- 国別価格を変える場合は `BillingManager` で `productDetails.subscriptionOfferDetails` から動的に表示するよう拡張する
- 起動時に `restorePurchases()` が動くので、機種変更後の自動復元も問題なし
- `acknowledge` を実装済みなので、3日以内のack漏れによる自動払い戻しは発生しない
- **14日無料体験中もアプリは Premium 扱い** (`PurchaseState.PURCHASED` が返る)。期間内キャンセルで `restorePurchases` 時に Premium が外れる

## 6. もし「課金機能の初期化中です」と出る場合

- `BillingManager.startConnection()` の接続が完了する前にユーザーが押した可能性
- もしくは商品ID不一致 / Play Console 側で商品が「有効」になっていない
- ログ確認: `adb logcat -s BillingManager`

## 7. 既知の制限と今後の拡張候補

- 現状 `premium_monthly` 1種類のみ。年額プラン追加なら同じ仕組みで `premium_yearly` を追加し、`launchPurchaseFlow` に商品選択を渡せるように拡張
- 価格表示の動的化（多言語/通貨対応）
- 購入レシートのサーバー検証（Firebase Functions + Play Developer API）。現状はクライアント側のキャッシュのみのため、改ざんを完全には防げない。本気でやるなら Server-side validation を導入
- **AI 体型・ポージング分析機能の追加課金 (将来案)**
  - コスト変動費なので 1プラン定額には組み込まずに別建てのアドオン or 都度課金で実装する想定
  - 案A: 月額アドオン `ai_image_pack ¥500/月`, `ai_video_pack ¥1200/月`
  - 案B: 消費型チケット `ai_image_ticket ¥150/回`, `ai_video_ticket ¥500/回`
  - 詳細設計は `docs/AI_BODY_ANALYSIS_DESIGN.md` を参照
