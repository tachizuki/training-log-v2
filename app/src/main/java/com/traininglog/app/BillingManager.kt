package com.traininglog.app

import android.app.Activity
import android.content.Context
import android.util.Log
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams

/**
 * Google Play Billing ラッパー。
 *
 * 想定するサブスクリプション商品:
 *   productId = "premium_monthly"  （Play Console で月額サブスクとして作成）
 *
 * 主な責務:
 *   - BillingClient の接続・再接続
 *   - 商品詳細の取得
 *   - 購入フローの起動
 *   - 新規購入・既存購入(復元)の検出と Acknowledge
 *   - サブスク有効/無効の状態を SharedPreferences "premium_prefs" に保存
 *
 * 呼び出し側 (MainActivity) に通知するイベントは onPremiumStateChanged で受け取れる。
 */
class BillingManager(
    private val context: Context,
    // (有効か, 新規購入か) — 新規購入時のみ歓迎メッセージ等を出し分けられる
    private val onPremiumStateChanged: (Boolean, Boolean) -> Unit,
) {

    companion object {
        private const val TAG = "BillingManager"
        const val PRODUCT_PREMIUM_MONTHLY = "premium_monthly"
        private const val PREFS_NAME = "premium_prefs"
        private const val PREF_KEY = "is_premium"
    }

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private var productDetails: ProductDetails? = null
    private var pendingPurchaseCallback: (() -> Unit)? = null

    private val purchasesUpdatedListener = PurchasesUpdatedListener { result, purchases ->
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> {
                purchases?.forEach { handlePurchase(it) }
            }
            BillingClient.BillingResponseCode.USER_CANCELED -> {
                Log.d(TAG, "ユーザーが購入をキャンセル")
            }
            else -> {
                Log.w(TAG, "購入エラー code=${result.responseCode} msg=${result.debugMessage}")
            }
        }
    }

    private val billingClient: BillingClient = BillingClient.newBuilder(context)
        .setListener(purchasesUpdatedListener)
        .enablePendingPurchases()
        .build()

    /** 起動直後に呼ぶ。Billing接続後に既存の購入を確認し、サブスク有無を反映する。 */
    fun startConnection() {
        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    Log.d(TAG, "Billing接続完了")
                    queryProductDetails()
                    restorePurchases()
                } else {
                    Log.w(TAG, "Billing接続失敗: ${billingResult.debugMessage}")
                }
            }
            override fun onBillingServiceDisconnected() {
                Log.w(TAG, "Billingサービス切断 — 再接続を試みます")
                billingClient.startConnection(this)
            }
        })
    }

    /** プレミアムサブスクの商品詳細を取得しキャッシュ。 */
    private fun queryProductDetails() {
        val product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(PRODUCT_PREMIUM_MONTHLY)
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(listOf(product))
            .build()
        billingClient.queryProductDetailsAsync(params) { result, list ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK && list.isNotEmpty()) {
                productDetails = list.first()
                Log.d(TAG, "商品詳細取得: ${productDetails?.name}")
            } else {
                Log.w(TAG, "商品詳細取得失敗 code=${result.responseCode} msg=${result.debugMessage}")
            }
        }
    }

    /** 既存購入を確認しサブスク状態を反映。アプリ起動時/復元時に呼ぶ。 */
    fun restorePurchases() {
        val params = QueryPurchasesParams.newBuilder()
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        billingClient.queryPurchasesAsync(params) { result, purchases ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                val active = purchases.any {
                    it.purchaseState == Purchase.PurchaseState.PURCHASED &&
                    it.products.contains(PRODUCT_PREMIUM_MONTHLY)
                }
                setPremium(active, isNewPurchase = false)
                // 未acknowledgeの購入は ack しておかないと自動払い戻しになる
                purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED && !it.isAcknowledged }
                    .forEach { acknowledge(it) }
            }
        }
    }

    /** 購入フローを起動。activity は前面のActivity。 */
    fun launchPurchaseFlow(activity: Activity): Boolean {
        val details = productDetails
        if (details == null) {
            Log.w(TAG, "商品詳細未取得のため購入フロー起動不可")
            // 商品取得を再試行しておく
            queryProductDetails()
            return false
        }
        // 無料トライアル等の優遇オファー（価格0の料金フェーズを含む）があれば優先的に選択する。
        // firstOrNull だと基本プランが先頭の場合にトライアルが適用されない不具合になるため。
        val offers = details.subscriptionOfferDetails
        if (offers.isNullOrEmpty()) {
            Log.w(TAG, "オファー一覧が空のため購入フロー起動不可")
            return false
        }
        val freeTrialOffer = offers.firstOrNull { offer ->
            offer.pricingPhases.pricingPhaseList.any { it.priceAmountMicros == 0L }
        }
        val offerToken = (freeTrialOffer ?: offers.first()).offerToken
        val params = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(details)
                        .setOfferToken(offerToken)
                        .build()
                )
            )
            .build()
        val result = billingClient.launchBillingFlow(activity, params)
        return result.responseCode == BillingClient.BillingResponseCode.OK
    }

    private fun handlePurchase(purchase: Purchase) {
        if (purchase.purchaseState != Purchase.PurchaseState.PURCHASED) return
        if (!purchase.products.contains(PRODUCT_PREMIUM_MONTHLY)) return
        setPremium(true, isNewPurchase = true)
        if (!purchase.isAcknowledged) acknowledge(purchase)
    }

    private fun acknowledge(purchase: Purchase) {
        val params = AcknowledgePurchaseParams.newBuilder()
            .setPurchaseToken(purchase.purchaseToken)
            .build()
        billingClient.acknowledgePurchase(params) { result ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                Log.d(TAG, "acknowledge成功")
            } else {
                Log.w(TAG, "acknowledge失敗: ${result.debugMessage}")
            }
        }
    }

    fun isPremium(): Boolean = prefs.getBoolean(PREF_KEY, false)

    private fun setPremium(active: Boolean, isNewPurchase: Boolean) {
        val prev = isPremium()
        prefs.edit().putBoolean(PREF_KEY, active).apply()
        if (prev != active) onPremiumStateChanged(active, isNewPurchase)
    }

    fun endConnection() {
        try { billingClient.endConnection() } catch (_: Exception) {}
    }
}
