package com.traininglog.app

import android.annotation.SuppressLint
import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.android.gms.common.api.ApiException
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.GoogleAuthProvider
import com.google.firebase.firestore.FirebaseFirestore
import com.google.android.play.core.review.ReviewManagerFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    // release=本番index.html / debug=再設計版index-v3.html（build.gradleのbuildConfigFieldで切替）
    private val REMOTE_URL = BuildConfig.WEBVIEW_URL
    private val LOCAL_URL = "file:///android_asset/index.html"
    // ナビゲーション許可ドメイン（ブリッジ付きWebViewに外部サイトを読み込ませない）
    private val TRUSTED_HOST: String = runCatching { Uri.parse(BuildConfig.WEBVIEW_URL).host ?: "" }.getOrDefault("")

    private val chunks = mutableMapOf<Int, String>()
    private var totalChunks = 0
    private var saveFilename = ""
    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    // 通知タップ時に復帰すべき画面（onPageFinishedで一度だけ使用）
    private var pendingScreen: String? = null
    private var authStateListener: FirebaseAuth.AuthStateListener? = null

    private lateinit var auth: FirebaseAuth
    private lateinit var db: FirebaseFirestore
    private lateinit var billing: BillingManager

    // タイマー完了をWebViewに通知するブロードキャストレシーバー
    private val timerDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == TimerService.BROADCAST_DONE) {
                webView.post {
                    webView.evaluateJavascript(
                        "if(typeof onTimerDone==='function')onTimerDone()", null
                    )
                }
            }
        }
    }

    private val googleSignInLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
            try {
                val account = task.getResult(ApiException::class.java)
                val credential = GoogleAuthProvider.getCredential(account.idToken, null)
                auth.signInWithCredential(credential).addOnCompleteListener(this) { authTask ->
                    if (authTask.isSuccessful) {
                        val user = auth.currentUser
                        val displayName = user?.displayName ?: ""
                        val email = user?.email ?: ""
                        val uid = user?.uid ?: ""
                        webView.evaluateJavascript(
                            "onFirebaseSignIn('$uid','$displayName','$email')", null
                        )
                    } else {
                        Toast.makeText(this, "認証失敗: ${authTask.exception?.message}", Toast.LENGTH_LONG).show()
                    }
                }
            } catch (e: ApiException) {
                Toast.makeText(this, "Googleサインインエラー: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private val filePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data?.data != null) {
            val uri = result.data!!.data!!
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val json = contentResolver.openInputStream(uri)?.bufferedReader()?.readText() ?: ""
                    withContext(Dispatchers.Main) {
                        val escaped = json
                            .replace("\\", "\\\\")
                            .replace("\"", "\\\"")
                            .replace("\n", "\\n")
                            .replace("\r", "")
                        webView.evaluateJavascript("receiveImportData(\"$escaped\")", null)
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@MainActivity, "読み込みエラー: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
        filePathCallback?.onReceiveValue(null)
        filePathCallback = null
    }

    inner class AndroidBridge {

        // レストタイマー完了時に音を鳴らさずバイブのみにするか（JS設定から受け取る）
        @Volatile private var timerVibeOnly = false

        // 完了アラームをバイブのみにする設定を更新（startTimerの引数は互換のため変えず別メソッドで受ける）
        @JavascriptInterface
        fun setTimerVibeOnly(on: Boolean) { timerVibeOnly = on }

        @JavascriptInterface
        fun signInWithGoogle() {
            runOnUiThread {
                val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
                    .requestIdToken("211414940177-a7bok6n7uki5kmkppo2t3jp0g4umfokj.apps.googleusercontent.com")
                    .requestEmail()
                    .build()
                val client = GoogleSignIn.getClient(this@MainActivity, gso)
                // revokeAccess() でアプリのGoogle認可を完全リセットする
                // signOut()だけではキャッシュが残り自動選択されてしまうため、
                // revokeAccess()で毎回ユーザーが明示的に同意操作を行う体験を保証する
                client.revokeAccess().addOnCompleteListener {
                    googleSignInLauncher.launch(client.signInIntent)
                }
            }
        }

        @JavascriptInterface
        fun signOut() {
            auth.signOut()
            val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN).build()
            GoogleSignIn.getClient(this@MainActivity, gso).signOut()
            webView.post {
                webView.evaluateJavascript("onFirebaseSignOut()", null)
            }
        }

        /**
         * アカウントとクラウド上の全データを削除する。
         * 1. Firestore users/{uid} ドキュメントを削除
         * 2. Firebase Auth アカウントを削除（要: 直近ログイン。失敗時は再ログイン要求）
         * 3. Google Sign-In セッションも切る
         * 4. JS 側にコールバック (onAccountDeleted) → localStorage クリア + リロード
         */
        @JavascriptInterface
        fun deleteAccountAndData() {
            val user = auth.currentUser
            if (user == null) {
                webView.post {
                    webView.evaluateJavascript("onAccountDeleted(false, 'ログインしていません')", null)
                }
                return
            }
            val uid = user.uid
            db.collection("users").document(uid).delete()
                .addOnCompleteListener {
                    // Firestore 削除の成否に関わらず、Auth アカウント削除を試みる
                    user.delete()
                        .addOnSuccessListener {
                            val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN).build()
                            GoogleSignIn.getClient(this@MainActivity, gso).signOut()
                            webView.post {
                                webView.evaluateJavascript("onAccountDeleted(true, '')", null)
                            }
                        }
                        .addOnFailureListener { e ->
                            // 直近ログインが古い場合 FirebaseAuthRecentLoginRequiredException
                            val msg = (e.message ?: "アカウント削除エラー").replace("'", " ")
                            webView.post {
                                webView.evaluateJavascript("onAccountDeleted(false, '$msg')", null)
                            }
                        }
                }
        }

        @JavascriptInterface
        fun saveToFirestore(uid: String, jsonData: String) {
            val data = hashMapOf(
                "data" to jsonData,
                "updatedAt" to System.currentTimeMillis()
            )
            db.collection("users").document(uid)
                .set(data)
                .addOnSuccessListener {
                    webView.post {
                        webView.evaluateJavascript("showToast('クラウドに保存しました ✓', false)", null)
                    }
                }
                .addOnFailureListener { e ->
                    webView.post {
                        webView.evaluateJavascript("showToast('保存エラー: ${e.message}')", null)
                    }
                }
        }

        @JavascriptInterface
        fun loadFromFirestore(uid: String) {
            db.collection("users").document(uid)
                .get()
                .addOnSuccessListener { doc ->
                    if (doc.exists()) {
                        val jsonData = doc.getString("data") ?: "{}"
                        val escaped = jsonData
                            .replace("\\", "\\\\")
                            .replace("\"", "\\\"")
                            .replace("\n", "\\n")
                            .replace("\r", "")
                        webView.post {
                            webView.evaluateJavascript("receiveFirestoreData(\"$escaped\")", null)
                        }
                    }
                }
                .addOnFailureListener { e ->
                    webView.post {
                        webView.evaluateJavascript("showToast('読み込みエラー: ${e.message}')", null)
                    }
                }
        }

        @JavascriptInterface
        fun setNotification(enabled: Boolean, hour: Int, minute: Int) {
            val prefs = getSharedPreferences("notif_prefs", MODE_PRIVATE)
            prefs.edit()
                .putBoolean("enabled", enabled)
                .putInt("hour", hour)
                .putInt("minute", minute)
                .apply()
            if (enabled) {
                NotificationReceiver.scheduleNotification(this@MainActivity, hour, minute)
                webView.post {
                    webView.evaluateJavascript(
                        "showToast('通知を設定しました（毎日 ${hour}:${minute.toString().padStart(2,'0')}）✓', false)", null
                    )
                }
            } else {
                NotificationReceiver.cancelNotification(this@MainActivity)
                webView.post {
                    webView.evaluateJavascript("showToast('通知をオフにしました', false)", null)
                }
            }
        }

        @JavascriptInterface
        fun getNotificationSettings(): String {
            val prefs = getSharedPreferences("notif_prefs", MODE_PRIVATE)
            val enabled = prefs.getBoolean("enabled", false)
            val hour = prefs.getInt("hour", 20)
            val minute = prefs.getInt("minute", 0)
            return """{"enabled":$enabled,"hour":$hour,"minute":$minute}"""
        }

        // ──────────────────────────────────────────────
        // タイマー（バックグラウンド動作・バイブレーション）
        // ──────────────────────────────────────────────

        @JavascriptInterface
        fun startTimer(seconds: Int) {
            runOnUiThread {
                try {
                    val intent = Intent(this@MainActivity, TimerService::class.java).apply {
                        action = TimerService.ACTION_START
                        putExtra(TimerService.EXTRA_SECONDS, seconds)
                        putExtra(TimerService.EXTRA_VIBE_ONLY, timerVibeOnly)
                    }
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(intent)
                    } else {
                        startService(intent)
                    }
                } catch (e: Exception) {
                    // startForegroundService 失敗時はJS側のタイマーのみで動作
                }
            }
        }

        @JavascriptInterface
        fun stopTimer() {
            runOnUiThread {
                try {
                    val intent = Intent(this@MainActivity, TimerService::class.java).apply {
                        action = TimerService.ACTION_STOP
                    }
                    startService(intent)
                } catch (e: Exception) {}
            }
        }

        @JavascriptInterface
        fun isPremium(): Boolean {
            // BillingManager がストアから取得した最新状態を SharedPreferences "premium_prefs" にキャッシュしている
            return if (::billing.isInitialized) billing.isPremium()
            else getSharedPreferences("premium_prefs", MODE_PRIVATE).getBoolean("is_premium", false)
        }

        @JavascriptInterface
        fun purchasePremium() {
            runOnUiThread {
                if (!::billing.isInitialized) {
                    webView.evaluateJavascript("showToast('課金機能の初期化中です。少し待って再度お試しください')", null)
                    return@runOnUiThread
                }
                val launched = billing.launchPurchaseFlow(this@MainActivity)
                if (!launched) {
                    // 商品詳細未取得などで起動できなかった場合
                    webView.evaluateJavascript("showToast('購入フローを起動できませんでした。ネットワークを確認してください')", null)
                }
            }
        }

        @JavascriptInterface
        fun restorePremium() {
            // ユーザー操作で明示的に復元したい場合用 (今は未使用だがUI側から呼び出せる)
            if (::billing.isInitialized) billing.restorePurchases()
        }

        @JavascriptInterface
        fun getPremiumPrice(): String =
            // ペイウォール表示用: ストアのローカライズ済み価格（例 "¥480" / "US$4.99"）。未取得時は空
            if (::billing.isInitialized) billing.premiumFormattedPrice() else ""

        /**
         * Google Play In-App Review を起動する（レビュー促進）。
         * Web側が「良い瞬間（記録が一定数貯まった等）」に1回だけ呼ぶ想定。
         * 注意: 表示するか否かは Google 側のクォータが制御するため必ず出るとは限らず、
         * 結果（出た／出ない・評価したか）はアプリには返らない仕様。これが公式の正しい使い方。
         * ユーザーに明示的にストアへ飛ばしたい場合は openPlayStore() を使う。
         */
        @JavascriptInterface
        fun requestReview() {
            runOnUiThread {
                try {
                    val manager = ReviewManagerFactory.create(this@MainActivity)
                    manager.requestReviewFlow().addOnCompleteListener { task ->
                        if (task.isSuccessful) {
                            manager.launchReviewFlow(this@MainActivity, task.result)
                        }
                        // 失敗時は何もしない（押し付けない）
                    }
                } catch (e: Exception) {
                    // In-App Review が使えない環境では静かに無視
                }
            }
        }

        /**
         * Play ストアのアプリ詳細ページを開く（設定画面の「アプリを評価する」用）。
         * In-App Review と違い、ユーザー操作で確実にストアへ遷移させる。
         */
        @JavascriptInterface
        fun openPlayStore() {
            runOnUiThread {
                val market = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$packageName")).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NO_HISTORY or Intent.FLAG_ACTIVITY_MULTIPLE_TASK)
                }
                try {
                    startActivity(market)
                } catch (e: android.content.ActivityNotFoundException) {
                    // Play ストアアプリが無い端末はブラウザで開く
                    startActivity(Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=$packageName")))
                }
            }
        }

        @JavascriptInterface
        fun sendContactForm(jsonStr: String) {
            val uid = auth.currentUser?.uid ?: "anonymous"
            val data = hashMapOf(
                "payload" to jsonStr,
                "uid" to uid,
                "createdAt" to System.currentTimeMillis()
            )
            db.collection("contacts").add(data)
                .addOnSuccessListener {
                    webView.post {
                        webView.evaluateJavascript("onContactSent(true)", null)
                    }
                }
                .addOnFailureListener { e ->
                    val msg = (e.message ?: "送信エラー").replace("'", "")
                    webView.post {
                        webView.evaluateJavascript("onContactSent(false,'$msg')", null)
                    }
                }
        }

        /**
         * GAS Web App へデータを送信する。
         *
         * POST は Google のルーティングリダイレクト（認証前 302）で
         * ボディが届かない問題があるため、GET + URL パラメータ方式を使用する。
         * GET のリダイレクトは GET→GET で一貫するため確実に動作する。
         */
        @JavascriptInterface
        fun httpPost(url: String, body: String) {
            // 送信先を Google Apps Script ホストに限定（万一のXSS時に任意ホストへ情報送信されるのを防ぐ）
            val host = runCatching { java.net.URL(url).host?.lowercase() }.getOrNull()
            val allowed = host != null && (host == "script.google.com" || host.endsWith(".googleusercontent.com"))
            if (!allowed) {
                webView.post { webView.evaluateJavascript("if(typeof onContactSent==='function')onContactSent(false,'blocked')", null) }
                return
            }
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val encoded = java.net.URLEncoder.encode(body, "UTF-8")
                    val fullUrl = "$url?payload=$encoded"
                    val conn = java.net.URL(fullUrl).openConnection() as java.net.HttpURLConnection
                    conn.instanceFollowRedirects = true   // GET リダイレクトは問題なく追える
                    conn.requestMethod = "GET"
                    conn.connectTimeout = 15_000
                    conn.readTimeout = 15_000
                    val code = conn.responseCode
                    val responseJson = if (code in 200..299)
                        runCatching { conn.inputStream.bufferedReader().readText() }.getOrDefault("")
                    else ""
                    conn.disconnect()

                    withContext(Dispatchers.Main) {
                        val gasOk = when {
                            responseJson.contains("\"ok\":true")  -> true
                            responseJson.contains("\"ok\":false") -> false
                            else -> code in 200..299
                        }
                        val errMsg = if (!gasOk) {
                            val s = responseJson.indexOf("\"error\":\"")
                            if (s >= 0) {
                                val e2 = responseJson.indexOf("\"", s + 9)
                                if (e2 > s + 9) responseJson.substring(s + 9, e2) else "GASエラー (code=$code)"
                            } else "送信に失敗しました (code=$code)"
                        } else ""
                        val safeErr = errMsg.replace("'", "").take(100)
                        webView.evaluateJavascript("onContactSent($gasOk,'$safeErr')", null)
                    }
                } catch (e: Exception) {
                    val msg = (e.message ?: "通信エラー").replace("'", "").take(80)
                    withContext(Dispatchers.Main) {
                        webView.evaluateJavascript("onContactSent(false,'$msg')", null)
                    }
                }
            }
        }

        @JavascriptInterface
        fun openFilePicker() {
            val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                type = "*/*"
                addCategory(Intent.CATEGORY_OPENABLE)
            }
            filePickerLauncher.launch(intent)
        }

        @JavascriptInterface
        fun saveJson(filename: String, json: String) {
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val file = File(cacheDir, filename)
                    file.writeText(json)
                    val uri = FileProvider.getUriForFile(
                        this@MainActivity, "${packageName}.provider", file
                    )
                    withContext(Dispatchers.Main) {
                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                            type = "application/json"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            putExtra(Intent.EXTRA_SUBJECT, filename)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        startActivity(Intent.createChooser(shareIntent, "バックアップを保存"))
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@MainActivity, "エクスポートエラー: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }

        @JavascriptInterface
        fun saveStart(filename: String, total: Int) {
            chunks.clear()
            totalChunks = total
            saveFilename = filename
        }

        @JavascriptInterface
        fun saveChunk(index: Int, data: String) {
            chunks[index] = data
        }

        @JavascriptInterface
        fun saveDone() {
            val base64 = (0 until totalChunks).joinToString("") { chunks[it] ?: "" }
            val filename = saveFilename
            chunks.clear()
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val bytes = Base64.decode(base64, Base64.DEFAULT)
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    val cacheFile = File(cacheDir, filename)
                    FileOutputStream(cacheFile).use { out ->
                        bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)
                    }
                    val uri = FileProvider.getUriForFile(
                        this@MainActivity, "${packageName}.provider", cacheFile
                    )
                    withContext(Dispatchers.Main) {
                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                            type = "image/jpeg"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        startActivity(Intent.createChooser(shareIntent, "シェア"))
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@MainActivity, "エラー: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val screen = intent.getStringExtra("target_screen") ?: return
        // 英数字とハイフンのみ許可（JS注入防止）
        if (!screen.matches(Regex("[a-z0-9-]+"))) return
        webView.post {
            webView.evaluateJavascript(
                "if(typeof showScreen==='function')showScreen('$screen')", null
            )
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_main)
        // 通知タップからの起動時は対象画面を記憶（ページロード後にonPageFinishedで遷移）
        val rawScreen = intent?.getStringExtra("target_screen")
        pendingScreen = if (rawScreen != null && rawScreen.matches(Regex("[a-z0-9-]+"))) rawScreen else null

        auth = FirebaseAuth.getInstance()
        db = FirebaseFirestore.getInstance()

        // Google Play Billing 初期化（プレミアム状態変化時はWebViewへ通知）
        billing = BillingManager(applicationContext) { active, isNewPurchase ->
            runOnUiThread {
                if (::webView.isInitialized) {
                    when {
                        // 新規購入時のみ歓迎メッセージを表示
                        active && isNewPurchase ->
                            webView.evaluateJavascript("if(typeof onPremiumPurchased==='function')onPremiumPurchased();", null)
                        // 起動時の自動復元（歓迎メッセージなしでUIだけ解放）
                        active ->
                            webView.evaluateJavascript("if(typeof onPremiumRestored==='function')onPremiumRestored(true);", null)
                        // 失効・解約
                        else ->
                            webView.evaluateJavascript("if(typeof onPremiumRestored==='function')onPremiumRestored(false);", null)
                    }
                }
            }
        }
        // 商品詳細取得時にローカライズ価格をペイウォールへ反映
        billing.onPriceReady = { price ->
            runOnUiThread {
                if (::webView.isInitialized) {
                    val safe = price.replace("\\", "\\\\").replace("'", "\\'")
                    webView.evaluateJavascript("if(typeof onPremiumPriceLoaded==='function')onPremiumPriceLoaded('$safe')", null)
                }
            }
        }
        billing.startConnection()

        // 通知チャンネル作成 & Android 13+ の通知権限リクエスト
        NotificationReceiver.createChannel(this)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(
                    this, arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 100
                )
            }
        }

        webView = findViewById(R.id.webView)
        webView.clearCache(true)
        // リモートデバッグはデバッグビルドのみ（リリースで遠隔Inspectを防ぐ）
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = false                       // 旧WebSQLは不要
            allowFileAccess = true                         // オフライン用 file:///android_asset フォールバックに必要
            allowContentAccess = false                     // content:// へのアクセスを禁止
            allowFileAccessFromFileURLs = false            // file:// から別ファイルの読み出し禁止
            allowUniversalAccessFromFileURLs = false       // file:// からの全オリジンアクセス禁止
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW  // https内のhttp読込を禁止（MITM対策）
            cacheMode = WebSettings.LOAD_NO_CACHE
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
            displayZoomControls = false
            builtInZoomControls = false
        }

        webView.addJavascriptInterface(AndroidBridge(), "AndroidBridge")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: FileChooserParams
            ): Boolean {
                this@MainActivity.filePathCallback = filePathCallback
                val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    type = "*/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }
                filePickerLauncher.launch(intent)
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            // 信頼ドメイン(pages.dev)と同梱asset以外への遷移はWebView内で読み込ませず外部アプリで開く。
            // → 万一のリダイレクト/外部リンクでブリッジ付きWebViewが攻撃者ページを読むのを防ぐ。
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val u = request.url
                val scheme = u.scheme?.lowercase()
                val host = u.host?.lowercase()
                // 同梱asset(オフラインフォールバック)のみ file:// を許可
                if (scheme == "file") return !u.toString().startsWith("file:///android_asset/")
                if (scheme == "https" && host != null && (host == TRUSTED_HOST || host.endsWith(".$TRUSTED_HOST"))) return false
                // それ以外（別ドメイン/http/mailto/tel/market/intent 等）は外部で処理
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, u).apply { addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) })
                } catch (e: Exception) { /* 対応アプリ無し時は何もしない */ }
                return true
            }

            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
                // システムバーの実際の高さをCSS変数として注入（env(safe-area-inset-top)がWebViewで0を返す場合の対策）
                ViewCompat.getRootWindowInsets(window.decorView)?.let { insets ->
                    val sat = insets.getInsets(WindowInsetsCompat.Type.statusBars()).top
                    val sab = insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom
                    view.evaluateJavascript("""
                        document.documentElement.style.setProperty('--sat','${sat}px');
                        document.documentElement.style.setProperty('--sab','${sab}px');
                    """.trimIndent(), null)
                }
                // ページ読み込み完了後にFirebase認証状態を復元
                val user = auth.currentUser
                if (user != null) {
                    notifySignIn(user.uid, user.displayName ?: "", user.email ?: "")
                }
                // 通知タップで再起動した場合、対象画面へ遷移（認証後データロードより後に実行）
                pendingScreen?.let { screen ->
                    pendingScreen = null
                    view.postDelayed({
                        view.evaluateJavascript(
                            "if(typeof showScreen==='function')showScreen('$screen')", null
                        )
                    }, 500L)
                }
            }

            override fun onReceivedError(view: WebView, errorCode: Int, description: String?, failingUrl: String?) {
                view.loadUrl(LOCAL_URL)
            }
        }

        val url = "$REMOTE_URL?v=${System.currentTimeMillis()}"
        webView.loadUrl(url)

        // タイマー完了ブロードキャストを受信（バックグラウンド完了時もJSコールバックを届ける）
        ContextCompat.registerReceiver(
            this, timerDoneReceiver,
            IntentFilter(TimerService.BROADCAST_DONE),
            ContextCompat.RECEIVER_NOT_EXPORTED
        )

        // 認証状態の監視（新規ログイン・ログアウト時にJSに通知）
        // ※ページロード完了前に発火した場合はonPageFinishedで改めて復元される
        authStateListener = FirebaseAuth.AuthStateListener { firebaseAuth ->
            val user = firebaseAuth.currentUser
            if (user != null) {
                notifySignIn(user.uid, user.displayName ?: "", user.email ?: "")
            }
        }
        auth.addAuthStateListener(authStateListener!!)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                webView.evaluateJavascript(
                    "(function(){try{if(typeof handleAndroidBack==='function')return handleAndroidBack();return false;}catch(e){return false;}})()"
                ) { result ->
                    if (result != "true") finish()
                }
            }
        })
    }

    private fun notifySignIn(uid: String, name: String, email: String) {
        val safeName = name.replace("\\", "\\\\").replace("'", "\\'")
        val safeEmail = email.replace("\\", "\\\\").replace("'", "\\'")
        webView.post {
            webView.evaluateJavascript(
                "if(typeof onFirebaseSignIn==='function')onFirebaseSignIn('$uid','$safeName','$safeEmail')", null
            )
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }

    override fun onRestoreInstanceState(savedInstanceState: Bundle) {
        super.onRestoreInstanceState(savedInstanceState)
        webView.restoreState(savedInstanceState)
    }

    override fun onResume() {
        super.onResume()
        // ストアでの購入・キャンセル等の変更をアプリ復帰時に取り込む
        if (::billing.isInitialized) billing.restorePurchases()
    }

    override fun onDestroy() {
        try { unregisterReceiver(timerDoneReceiver) } catch (_: Exception) {}
        authStateListener?.let { auth.removeAuthStateListener(it) }
        if (::billing.isInitialized) billing.endConnection()
        super.onDestroy()
    }
}
