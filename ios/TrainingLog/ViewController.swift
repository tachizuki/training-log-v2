import UIKit
import WebKit
import FirebaseAuth
import FirebaseFirestore

class ViewController: UIViewController {

    // MARK: - Properties

    private(set) var webView: WKWebView!

    private let remoteURL = "https://training-log-v2-5vc.pages.dev/index-v3.html"
    private var localURL: URL {
        Bundle.main.url(forResource: "index", withExtension: "html")!
    }

    // チャンク分割画像転送用
    var chunks: [Int: String] = [:]
    var totalChunks = 0
    var saveFilename = ""

    let auth = Auth.auth()
    let db = Firestore.firestore()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupWebView()
        loadRemoteURL()
        setupAuthListener()
        setupBilling()
        NotificationManager.shared.requestPermission()
        TimerManager.shared.configure(viewController: self)
    }

    // MARK: - WebView Setup

    private func setupWebView() {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true

        let contentController = WKUserContentController()

        // AndroidBridge shimをページJS実行前に注入 — HTMLの変更は不要
        let shim = WKUserScript(
            source: bridgeShimJS(),
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        contentController.addUserScript(shim)

        let handlerNames = [
            "signInWithGoogle", "signOut", "deleteAccountAndData",
            "saveToFirestore", "loadFromFirestore",
            "setNotification",
            "startTimer", "stopTimer",
            "isPremium", "purchasePremium", "restorePremium",
            "sendContactForm", "httpPost",
            "openFilePicker", "saveJson",
            "saveStart", "saveChunk", "saveDone"
        ]
        // WKUserContentController の循環参照を避けるため WeakScriptMessageHandler でラップ
        for name in handlerNames {
            contentController.add(WeakScriptMessageHandler(self), name: name)
        }

        config.userContentController = contentController

        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        // iOSには物理戻るが無いため、エッジスワイプで前画面へ戻れるようにする（BK-007）
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.scrollView.bounces = false
        webView.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
    }

    private func loadRemoteURL() {
        var comps = URLComponents(string: remoteURL)!
        comps.queryItems = [URLQueryItem(name: "v", value: "\(Int(Date().timeIntervalSince1970))")]
        webView.load(URLRequest(url: comps.url!))
    }

    // MARK: - Auth

    private func setupAuthListener() {
        auth.addStateDidChangeListener { [weak self] _, user in
            guard let self, let user else { return }
            self.notifySignIn(uid: user.uid, name: user.displayName ?? "", email: user.email ?? "")
        }
    }

    func notifySignIn(uid: String, name: String, email: String) {
        let js = "if(typeof onFirebaseSignIn==='function')onFirebaseSignIn('\(uid.jsEscaped)','\(name.jsEscaped)','\(email.jsEscaped)')"
        evaluateJS(js)
    }

    // MARK: - Billing

    private func setupBilling() {
        BillingManager.shared.configure { [weak self] isActive in
            guard let self else { return }
            let js = isActive
                ? "if(typeof onPremiumPurchased==='function')onPremiumPurchased();"
                : "if(typeof onPremiumRestored==='function')onPremiumRestored(false);"
            self.evaluateJS(js)
            self.evaluateJS("window.__setIsPremium(\(isActive));")
        }
    }

    // MARK: - JS Bridge

    func evaluateJS(_ js: String) {
        DispatchQueue.main.async { [weak self] in
            self?.webView.evaluateJavaScript(js, completionHandler: nil)
        }
    }

    // MARK: - Bridge Shim JS
    // iOS側で window.AndroidBridge を定義することで HTML/JS を一切変更せずに動作する

    private func bridgeShimJS() -> String {
        """
        (function() {
          var _isPremium = false;
          var _notifSettings = {"enabled":false,"hour":20,"minute":0};

          window.__setIsPremium    = function(v) { _isPremium = v; };
          window.__setNotifSettings = function(s) {
            _notifSettings = typeof s === 'string' ? JSON.parse(s) : s;
          };
          window.__platform = 'ios';

          function post(name, body) {
            window.webkit.messageHandlers[name].postMessage(body !== undefined ? body : null);
          }

          window.AndroidBridge = {
            signInWithGoogle:        function()           { post('signInWithGoogle'); },
            signOut:                 function()           { post('signOut'); },
            deleteAccountAndData:    function()           { post('deleteAccountAndData'); },
            saveToFirestore:         function(uid, data)  { post('saveToFirestore', {uid: uid, data: data}); },
            loadFromFirestore:       function(uid)        { post('loadFromFirestore', {uid: uid}); },
            setNotification:         function(en, h, m)  { post('setNotification', {enabled: en, hour: h, minute: m}); },
            getNotificationSettings: function()           { return JSON.stringify(_notifSettings); },
            startTimer:              function(s)          { post('startTimer', {seconds: s}); },
            stopTimer:               function()           { post('stopTimer'); },
            isPremium:               function()           { return _isPremium; },
            purchasePremium:         function()           { post('purchasePremium'); },
            restorePremium:          function()           { post('restorePremium'); },
            sendContactForm:         function(json)       { post('sendContactForm', {json: json}); },
            httpPost:                function(url, body)  { post('httpPost', {url: url, body: body}); },
            openFilePicker:          function()           { post('openFilePicker'); },
            saveJson:                function(name, json) { post('saveJson', {filename: name, json: json}); },
            saveStart:               function(name, tot)  { post('saveStart', {filename: name, total: tot}); },
            saveChunk:               function(idx, data)  { post('saveChunk', {index: idx, data: data}); },
            saveDone:                function()           { post('saveDone'); }
          };
        })();
        """
    }
}

// MARK: - WKNavigationDelegate

extension ViewController: WKNavigationDelegate {

    func webView(_ webView: WKWebView, didFailProvisionalNavigation _: WKNavigation!, withError _: Error) {
        webView.loadFileURL(localURL, allowingReadAccessTo: localURL.deletingLastPathComponent())
    }

    func webView(_ webView: WKWebView, didFail _: WKNavigation!, withError _: Error) {
        webView.loadFileURL(localURL, allowingReadAccessTo: localURL.deletingLastPathComponent())
    }

    func webView(_ webView: WKWebView, didFinish _: WKNavigation!) {
        // ページ読み込み完了後にFirebase認証状態を復元
        if let user = auth.currentUser {
            notifySignIn(uid: user.uid, name: user.displayName ?? "", email: user.email ?? "")
        }

        // 通知設定をJSに同期
        NotificationManager.shared.getSettings { [weak self] enabled, hour, minute in
            let json = "{\"enabled\":\(enabled),\"hour\":\(hour),\"minute\":\(minute)}"
            self?.evaluateJS("window.__setNotifSettings('\(json)');")
        }

        // プレミアム状態をJSに同期
        let premium = BillingManager.shared.isPremium()
        evaluateJS("window.__setIsPremium(\(premium));")
    }
}

// MARK: - WeakScriptMessageHandler (循環参照防止)

final class WeakScriptMessageHandler: NSObject, WKScriptMessageHandler {
    weak var delegate: WKScriptMessageHandler?
    init(_ delegate: WKScriptMessageHandler) { self.delegate = delegate }

    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        delegate?.userContentController(ucc, didReceive: message)
    }
}

// MARK: - String Extensions

extension String {
    var jsEscaped: String {
        self
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "'",  with: "\\'")
            .replacingOccurrences(of: "\n", with: "\\n")
            .replacingOccurrences(of: "\r", with: "")
    }
}
