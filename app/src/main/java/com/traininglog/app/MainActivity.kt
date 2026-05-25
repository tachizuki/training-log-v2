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
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val REMOTE_URL = "https://training-log-v2-5vc.pages.dev/index.html"
    private val LOCAL_URL = "file:///android_asset/index.html"

    private val chunks = mutableMapOf<Int, String>()
    private var totalChunks = 0
    private var saveFilename = ""
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

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
            val intent = Intent(this@MainActivity, TimerService::class.java).apply {
                action = TimerService.ACTION_START
                putExtra(TimerService.EXTRA_SECONDS, seconds)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        }

        @JavascriptInterface
        fun stopTimer() {
            val intent = Intent(this@MainActivity, TimerService::class.java).apply {
                action = TimerService.ACTION_STOP
            }
            startService(intent)
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

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContentView(R.layout.activity_main)

        auth = FirebaseAuth.getInstance()
        db = FirebaseFirestore.getInstance()

        // Google Play Billing 初期化（プレミアム状態変化時はWebViewへ通知）
        billing = BillingManager(applicationContext) { active ->
            runOnUiThread {
                if (::webView.isInitialized) {
                    if (active) {
                        webView.evaluateJavascript("if(typeof onPremiumPurchased==='function')onPremiumPurchased();", null)
                    } else {
                        webView.evaluateJavascript("if(typeof onPremiumRestored==='function')onPremiumRestored(false);", null)
                    }
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

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
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
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = false

            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
                // ページ読み込み完了後にFirebase認証状態を復元
                // （addAuthStateListenerはページロード前に発火するためここで再通知が必要）
                val user = auth.currentUser
                if (user != null) {
                    notifySignIn(user.uid, user.displayName ?: "", user.email ?: "")
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
        auth.addAuthStateListener { firebaseAuth ->
            val user = firebaseAuth.currentUser
            if (user != null) {
                notifySignIn(user.uid, user.displayName ?: "", user.email ?: "")
            }
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                webView.evaluateJavascript(
                    "typeof handleAndroidBack === 'function' ? handleAndroidBack() : false"
                ) { result ->
                    if (result != "true") {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            }
        })
    }

    private fun notifySignIn(uid: String, name: String, email: String) {
        webView.post {
            webView.evaluateJavascript(
                "if(typeof onFirebaseSignIn==='function')onFirebaseSignIn('$uid','$name','$email')", null
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
        if (::billing.isInitialized) billing.endConnection()
        super.onDestroy()
    }
}
