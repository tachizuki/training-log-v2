import StoreKit

// Android の BillingManager (Google Play Billing) に相当。
// StoreKit 2 (iOS 15+) で実装。

@MainActor
final class BillingManager {
    static let shared = BillingManager()

    // TODO: App Store Connect で登録したプロダクトIDに変更する
    private let productId = "com.traininglog.app.premium"

    private var product: Product?
    private var onStatusChange: ((Bool) -> Void)?
    private var transactionListenerTask: Task<Void, Never>?

    private(set) var isPremiumActive: Bool = false {
        didSet { UserDefaults.standard.set(isPremiumActive, forKey: "is_premium") }
    }

    func configure(onStatusChange: @escaping (Bool) -> Void) {
        self.onStatusChange = onStatusChange
        isPremiumActive = UserDefaults.standard.bool(forKey: "is_premium")
        Task {
            await loadProduct()
            await checkEntitlements()
        }
        transactionListenerTask = Task { await listenForTransactions() }
    }

    func isPremium() -> Bool { isPremiumActive }

    func purchase() async -> Bool {
        guard let product else { return false }
        do {
            let result = try await product.purchase()
            if case .success(let verification) = result,
               case .verified(let transaction) = verification {
                await transaction.finish()
                isPremiumActive = true
                onStatusChange?(true)
                return true
            }
        } catch { }
        return false
    }

    func restorePurchases() async {
        do { try await AppStore.sync() } catch { }
        await checkEntitlements()
    }

    // MARK: - Private

    private func loadProduct() async {
        guard let products = try? await Product.products(for: [productId]) else { return }
        product = products.first
    }

    private func checkEntitlements() async {
        var found = false
        for await result in Transaction.currentEntitlements {
            if case .verified(let tx) = result,
               tx.productID == productId,
               tx.revocationDate == nil {
                found = true
                break
            }
        }
        if isPremiumActive != found {
            isPremiumActive = found
            onStatusChange?(found)
        }
    }

    private func listenForTransactions() async {
        for await result in Transaction.updates {
            if case .verified(let tx) = result {
                await tx.finish()
                if tx.productID == productId {
                    let active = tx.revocationDate == nil
                    isPremiumActive = active
                    onStatusChange?(active)
                }
            }
        }
    }

    deinit { transactionListenerTask?.cancel() }
}
