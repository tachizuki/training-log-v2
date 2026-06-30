package com.traininglog.app

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import java.util.Calendar

class NotificationReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED -> {
                // 再起動後にアラームを再設定
                val prefs = context.getSharedPreferences("notif_prefs", Context.MODE_PRIVATE)
                val enabled = prefs.getBoolean("enabled", false)
                val hour = prefs.getInt("hour", 20)
                val minute = prefs.getInt("minute", 0)
                if (enabled) { scheduleNotification(context, hour, minute); scheduleWeeklySummary(context) }
            }
            ACTION_DAILY -> {
                showNotification(context)
            }
            ACTION_WEEKLY -> {
                showWeeklyNotification(context)
            }
        }
    }

    companion object {
        const val CHANNEL_ID = "daily_record"
        const val NOTIF_ID = 1001
        const val ACTION_DAILY = "com.traininglog.app.DAILY_NOTIFICATION"
        // 週間まとめ通知（毎週月曜9時。既存の通知トグルに連動）
        const val CHANNEL_WEEKLY = "weekly_summary"
        const val NOTIF_ID_WEEKLY = 1002
        const val ACTION_WEEKLY = "com.traininglog.app.WEEKLY_SUMMARY"

        fun createChannel(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val channel = NotificationChannel(
                    CHANNEL_ID,
                    "デイリー記録リマインダー",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "毎日の記録リマインダー通知"
                }
                val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.createNotificationChannel(channel)
                val weekly = NotificationChannel(
                    CHANNEL_WEEKLY,
                    "週間まとめ",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "毎週のまとめ通知"
                }
                nm.createNotificationChannel(weekly)
            }
        }

        fun scheduleNotification(context: Context, hour: Int, minute: Int) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val pi = buildPendingIntent(context)
            val cal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, hour)
                set(Calendar.MINUTE, minute)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
                // 指定時刻を過ぎていたら翌日にセット
                if (timeInMillis <= System.currentTimeMillis()) add(Calendar.DAY_OF_MONTH, 1)
            }
            // setRepeating で毎日繰り返し
            am.setRepeating(AlarmManager.RTC_WAKEUP, cal.timeInMillis, AlarmManager.INTERVAL_DAY, pi)
        }

        fun cancelNotification(context: Context) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.cancel(buildPendingIntent(context))
        }

        private fun buildPendingIntent(context: Context): PendingIntent {
            val intent = Intent(context, NotificationReceiver::class.java).apply {
                action = ACTION_DAILY
            }
            return PendingIntent.getBroadcast(
                context, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }

        // 週間まとめ通知を毎週月曜9時に設定
        fun scheduleWeeklySummary(context: Context) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val pi = buildWeeklyPendingIntent(context)
            val cal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 9)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
                set(Calendar.DAY_OF_WEEK, Calendar.MONDAY)
                // 今週の月曜9時を過ぎていたら翌週へ
                if (timeInMillis <= System.currentTimeMillis()) add(Calendar.WEEK_OF_YEAR, 1)
            }
            am.setRepeating(AlarmManager.RTC_WAKEUP, cal.timeInMillis, AlarmManager.INTERVAL_DAY * 7, pi)
        }

        fun cancelWeeklySummary(context: Context) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.cancel(buildWeeklyPendingIntent(context))
        }

        private fun buildWeeklyPendingIntent(context: Context): PendingIntent {
            val intent = Intent(context, NotificationReceiver::class.java).apply {
                action = ACTION_WEEKLY
            }
            return PendingIntent.getBroadcast(
                context, 1, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }

        fun showNotification(context: Context) {
            val launchIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                context, 0, launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle("今日の記録はしましたか？ 💪")
                .setContentText("体重・食事・トレーニングを記録しましょう")
                .setStyle(NotificationCompat.BigTextStyle()
                    .bigText("体重・食事・水分・トレーニングをTrainingLogで記録して\n大会までの進捗を管理しましょう！"))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .build()
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIF_ID, notif)
        }

        fun showWeeklyNotification(context: Context) {
            val launchIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                context, 1, launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(context, CHANNEL_WEEKLY)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle("今週のまとめができました 📊")
                .setContentText("先週のがんばりを振り返ろう")
                .setStyle(NotificationCompat.BigTextStyle()
                    .bigText("体重の変化・トレーニング・栄養のまとめをチェックして、今週のモチベーションにしましょう！"))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .build()
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIF_ID_WEEKLY, notif)
        }
    }
}
