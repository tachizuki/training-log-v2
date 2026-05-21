# リリース署名・ビルド手順書

PhysiqueLog のリリース版 (aab) を作って Play Console にアップロードするまでの完全手順。

---

## 0. 前提

- Android Studio / コマンドラインの `keytool` が使える
- リポジトリ直下で作業
- **keystore は紛失すると二度とアプリ更新できなくなる**。複数箇所バックアップ必須

---

## 1. キーストアの作成（初回のみ）

リポジトリ直下で実行:

```bash
keytool -genkey -v -keystore release.keystore -keyalg RSA -keysize 2048 -validity 10000 -alias physiquelog
```

質問されたら入力:

- パスワード（キーストア用）: 強いものを設定。必ず別管理で保存
- 氏名・組織・市・州・国コードなど: 任意。後から変更可能
- キーパスワード: キーストアと同じで OK（Enter で同一にできる）

生成された `release.keystore` は `.gitignore` で除外済み。**コミットしない**。

### 1-1. バックアップ（最重要）

- パスワード管理アプリ (1Password, Bitwarden 等) に keystore ファイルと両パスワードを保存
- 別の物理場所 (USBメモリ、別PC) にもコピー
- クラウドにも暗号化して保管

---

## 2. keystore.properties を作成

リポジトリ直下に `keystore.properties` ファイルを作成（このファイルは `.gitignore` 対象）:

```properties
RELEASE_STORE_FILE=../release.keystore
RELEASE_STORE_PASSWORD=設定したパスワード
RELEASE_KEY_ALIAS=physiquelog
RELEASE_KEY_PASSWORD=設定したパスワード
```

`keystore.properties.example` をコピーして編集すると速い:

```bash
cp keystore.properties.example keystore.properties
```

> `RELEASE_STORE_FILE` のパスは `app/build.gradle` から見た相対パスなので、`release.keystore` をリポジトリ直下に置くなら `../release.keystore`。

### 環境変数で渡したい場合（CI 用）

`keystore.properties` がなくても以下の環境変数があれば自動で使われる:

- `KEYSTORE_PATH`
- `KEYSTORE_PASS`
- `KEY_ALIAS`
- `KEY_PASS`

---

## 3. リリース前にコードでやること

### 3-1. プレミアム強制解放フラグを OFF

`app/src/main/assets/index.html` の冒頭付近:

```js
const DEV_UNLOCK_PREMIUM = false;  // ← true から false に
```

### 3-2. ルートの index.html と同期

Cloudflare Pages はリポジトリ直下の `index.html` を見ているので必ず同期:

```bash
cp app/src/main/assets/index.html index.html
```

### 3-3. バージョン更新

`app/build.gradle` の `versionCode` / `versionName` を必要に応じて更新。

---

## 4. リリースビルド

```bash
./gradlew bundleRelease
```

成功すると `app/build/outputs/bundle/release/app-release.aab` が生成される。

### 4-1. 確認コマンド

```bash
# aab が署名されているか確認
keytool -printcert -jarfile app/build/outputs/bundle/release/app-release.aab
```

---

## 5. Play Console にアップロード

1. Play Console → アプリ選択 → リリース → テスト → 内部テスト
2. 「新しいリリースを作成」
3. `app-release.aab` をアップロード
4. リリースノート記入 → 確認 → 公開

`docs/BILLING_RELEASE_CHECKLIST.md` の Play Console 準備が済んでいる前提。

---

## 6. 動作確認

詳細は `docs/BILLING_RELEASE_CHECKLIST.md` セクション4。要点だけ:

1. ライセンステスター登録済みの Gmail で端末ログイン
2. 内部テストのリンクからアプリ取得
3. アップグレード → 14日無料体験テスト購入
4. 完全終了 → 再起動でプレミアム維持確認
5. Play ストアでキャンセル → アプリ再起動で無料に戻ること確認

---

## 7. トラブルシューティング

### `Keystore was tampered with, or password was incorrect`

→ `keystore.properties` のパスワードが間違っている、または keystore ファイルが破損。

### `Failed to read key xxx from store`

→ alias 名が間違い。`keytool -list -keystore release.keystore` で確認できる。

### 署名なしで aab ができる

→ `keystore.properties` が存在しないし環境変数もない。本書の手順2を実行。

### R8 で起動しなくなる

→ `app/proguard-rules.pro` のkeepルールを見直し。WebView の `@JavascriptInterface` メソッドが保持されているか確認。
