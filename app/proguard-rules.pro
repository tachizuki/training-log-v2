# ===============================
# PhysiqueLog ProGuard / R8 ルール
# ===============================
# 方針:
#   - サイズ縮小・難読化は基本的に R8 のデフォルトに任せる
#   - WebView ↔ JavaScript の橋渡し部分とライブラリ依存箇所だけを明示的にkeep
#   - クラッシュ解析のためソースファイル/行番号は保持

# WebView の JavascriptInterface でJSから呼ぶメソッドは絶対に削除/リネームしない
# AndroidBridge の @JavascriptInterface 付きメソッドが全てこの対象
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# BroadcastReceiver は AndroidManifest で参照されるため通常残るが、明示的に保護
-keep public class * extends android.content.BroadcastReceiver

# Kotlin Coroutines (一部の内部クラス保持。普通は consumer rules でカバーされるが、念のため)
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# Firebase Auth + Firestore（ライブラリの consumer rules で大部分カバーされる想定だが安全側）
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# Google Play Services (Sign-In)
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# Google Play Billing
-keep class com.android.billingclient.** { *; }
-dontwarn com.android.billingclient.**

# AndroidX Browser (CustomTabs)
-dontwarn androidx.browser.**

# クラッシュレポートに有用な行番号情報を保持しつつ、難読化はする
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# JavaScript からアクセスされる可能性のあるアノテーションを保持
-keepattributes *Annotation*

# enum の values()/valueOf() は反射で使われるので保持
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# Parcelable
-keepclassmembers class * implements android.os.Parcelable {
    public static final ** CREATOR;
}
