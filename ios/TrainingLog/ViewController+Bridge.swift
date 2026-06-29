import UIKit
import WebKit
import FirebaseAuth
import FirebaseFirestore
import GoogleSignIn
import UniformTypeIdentifiers

// MARK: - WKScriptMessageHandler (AndroidBridge全メソッドの実装)

extension ViewController: WKScriptMessageHandler {

    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        let body = message.body as? [String: Any]
        switch message.name {
        case "signInWithGoogle":     handleSignInWithGoogle()
        case "signOut":              handleSignOut()
        case "deleteAccountAndData": handleDeleteAccount()
        case "saveToFirestore":      handleSaveFirestore(body)
        case "loadFromFirestore":    handleLoadFirestore(body)
        case "setNotification":      handleSetNotification(body)
        case "startTimer":           handleStartTimer(body)
        case "stopTimer":            TimerManager.shared.stop()
        case "isPremium":            break // JS shim 側で同期的に処理
        case "purchasePremium":      handlePurchasePremium()
        case "restorePremium":       handleRestorePremium()
        case "sendContactForm":      handleSendContactForm(body)
        case "httpPost":             handleHttpPost(body)
        case "openFilePicker":       handleOpenFilePicker()
        case "saveJson":             handleSaveJson(body)
        case "saveStart":            handleSaveStart(body)
        case "saveChunk":            handleSaveChunk(body)
        case "saveDone":             handleSaveDone()
        default:                     break
        }
    }

    // MARK: - Auth

    private func handleSignInWithGoogle() {
        GIDSignIn.sharedInstance.signIn(withPresenting: self) { [weak self] result, error in
            guard let self,
                  error == nil,
                  let user = result?.user,
                  let idToken = user.idToken?.tokenString else { return }

            let credential = GoogleAuthProvider.credential(
                withIDToken: idToken,
                accessToken: user.accessToken.tokenString
            )
            self.auth.signIn(with: credential) { authResult, _ in
                guard let u = authResult?.user else { return }
                self.notifySignIn(uid: u.uid, name: u.displayName ?? "", email: u.email ?? "")
            }
        }
    }

    private func handleSignOut() {
        try? auth.signOut()
        GIDSignIn.sharedInstance.signOut()
        evaluateJS("onFirebaseSignOut()")
    }

    private func handleDeleteAccount() {
        guard let user = auth.currentUser else {
            evaluateJS("onAccountDeleted(false, 'ログインしていません')")
            return
        }
        let uid = user.uid
        db.collection("users").document(uid).delete { [weak self] _ in
            guard let self else { return }
            user.delete { error in
                if let error {
                    let msg = String(error.localizedDescription.jsEscaped.prefix(100))
                    self.evaluateJS("onAccountDeleted(false, '\(msg)')")
                } else {
                    GIDSignIn.sharedInstance.signOut()
                    self.evaluateJS("onAccountDeleted(true, '')")
                }
            }
        }
    }

    // MARK: - Firestore

    private func handleSaveFirestore(_ body: [String: Any]?) {
        guard let uid  = body?["uid"]  as? String,
              let data = body?["data"] as? String else { return }

        let doc: [String: Any] = ["data": data, "updatedAt": FieldValue.serverTimestamp()]
        db.collection("users").document(uid).setData(doc) { [weak self] error in
            guard let self else { return }
            if error == nil {
                self.evaluateJS("showToast('クラウドに保存しました ✓', false)")
            } else {
                let msg = String((error?.localizedDescription ?? "保存エラー").jsEscaped.prefix(60))
                self.evaluateJS("showToast('保存エラー: \(msg)')")
            }
        }
    }

    private func handleLoadFirestore(_ body: [String: Any]?) {
        guard let uid = body?["uid"] as? String else { return }
        db.collection("users").document(uid).getDocument { [weak self] snapshot, error in
            guard let self else { return }
            if let json = snapshot?.data()?["data"] as? String {
                let escaped = json.jsEscaped
                self.evaluateJS("receiveFirestoreData(\"\(escaped)\")")
            } else if error != nil {
                self.evaluateJS("showToast('読み込みエラー')")
            }
        }
    }

    // MARK: - Notifications

    private func handleSetNotification(_ body: [String: Any]?) {
        guard let enabled = body?["enabled"] as? Bool,
              let hour    = body?["hour"]    as? Int,
              let minute  = body?["minute"]  as? Int else { return }

        UserDefaults.standard.set(enabled, forKey: "notif_enabled")
        UserDefaults.standard.set(hour,    forKey: "notif_hour")
        UserDefaults.standard.set(minute,  forKey: "notif_minute")

        if enabled {
            NotificationManager.shared.requestPermission { [weak self] granted in
                guard let self else { return }
                if granted {
                    NotificationManager.shared.schedule(hour: hour, minute: minute)
                    let msg = "通知を設定しました（毎日 \(hour):\(String(format: "%02d", minute))）✓"
                    self.evaluateJS("showToast('\(msg)', false)")
                } else {
                    self.evaluateJS("showToast('通知の権限が必要です。設定アプリから許可してください')")
                }
            }
        } else {
            NotificationManager.shared.cancel()
            evaluateJS("showToast('通知をオフにしました', false)")
        }
    }

    // MARK: - Timer

    private func handleStartTimer(_ body: [String: Any]?) {
        guard let seconds = body?["seconds"] as? Int else { return }
        TimerManager.shared.start(seconds: seconds)
    }

    // MARK: - Billing

    private func handlePurchasePremium() {
        Task { @MainActor in
            let success = await BillingManager.shared.purchase()
            if success {
                evaluateJS("window.__setIsPremium(true);")
            } else {
                evaluateJS("showToast('購入をキャンセルしました')")
            }
        }
    }

    private func handleRestorePremium() {
        Task { @MainActor in
            await BillingManager.shared.restorePurchases()
        }
    }

    // MARK: - HTTP (GAS Web App)
    // AndroidのhttpPostと同様、GET + URL パラメータ方式

    private func handleHttpPost(_ body: [String: Any]?) {
        guard let urlStr   = body?["url"]  as? String,
              let postBody = body?["body"] as? String else { return }

        Task {
            do {
                let encoded = postBody.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                let url = URL(string: "\(urlStr)?payload=\(encoded)")!
                var request = URLRequest(url: url, timeoutInterval: 15)
                request.httpMethod = "GET"

                let (data, response) = try await URLSession.shared.data(for: request)
                let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                let text = String(data: data, encoding: .utf8) ?? ""

                let gasOk: Bool
                if      text.contains("\"ok\":true")  { gasOk = true }
                else if text.contains("\"ok\":false") { gasOk = false }
                else                                  { gasOk = (200..<300).contains(code) }

                await MainActor.run {
                    self.evaluateJS("onContactSent(\(gasOk),'')")
                }
            } catch {
                let msg = String(error.localizedDescription.jsEscaped.prefix(80))
                await MainActor.run {
                    self.evaluateJS("onContactSent(false,'\(msg)')")
                }
            }
        }
    }

    private func handleSendContactForm(_ body: [String: Any]?) {
        guard let json = body?["json"] as? String else { return }
        let uid = auth.currentUser?.uid ?? "anonymous"
        let data: [String: Any] = [
            "payload": json,
            "uid": uid,
            "createdAt": FieldValue.serverTimestamp()
        ]
        db.collection("contacts").addDocument(data: data) { [weak self] error in
            guard let self else { return }
            if error == nil {
                self.evaluateJS("onContactSent(true)")
            } else {
                let msg = String((error?.localizedDescription ?? "送信エラー").jsEscaped.prefix(60))
                self.evaluateJS("onContactSent(false,'\(msg)')")
            }
        }
    }

    // MARK: - File Operations

    private func handleOpenFilePicker() {
        let types: [UTType] = [.json, .data, .item]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: true)
        picker.delegate = self
        picker.allowsMultipleSelection = false
        present(picker, animated: true)
    }

    private func handleSaveJson(_ body: [String: Any]?) {
        guard let filename = body?["filename"] as? String,
              let json     = body?["json"]     as? String else { return }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(filename)
        try? json.write(to: url, atomically: true, encoding: .utf8)
        share(url: url)
    }

    // MARK: - Chunked Image Save (Android saveDone と同じ仕組み)

    private func handleSaveStart(_ body: [String: Any]?) {
        chunks.removeAll()
        totalChunks  = body?["total"]    as? Int    ?? 0
        saveFilename = body?["filename"] as? String ?? "image.jpg"
    }

    private func handleSaveChunk(_ body: [String: Any]?) {
        guard let index = body?["index"] as? Int,
              let data  = body?["data"]  as? String else { return }
        chunks[index] = data
    }

    private func handleSaveDone() {
        let base64 = (0..<totalChunks).compactMap { chunks[$0] }.joined()
        chunks.removeAll()
        guard let imageData = Data(base64Encoded: base64),
              let image = UIImage(data: imageData) else { return }

        let url = FileManager.default.temporaryDirectory.appendingPathComponent(saveFilename)
        if let jpeg = image.jpegData(compressionQuality: 0.9) {
            try? jpeg.write(to: url)
            share(url: url)
        }
    }

    // MARK: - Share Sheet

    func share(url: URL) {
        let av = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        if let pop = av.popoverPresentationController {
            pop.sourceView = view
            pop.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 0, height: 0)
        }
        present(av, animated: true)
    }
}

// MARK: - UIDocumentPickerDelegate

extension ViewController: UIDocumentPickerDelegate {
    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let url = urls.first else { return }
        Task.detached(priority: .userInitiated) {
            guard let json = try? String(contentsOf: url, encoding: .utf8) else { return }
            let escaped = json.jsEscaped
            await MainActor.run {
                self.evaluateJS("receiveImportData(\"\(escaped)\")")
            }
        }
    }
}
