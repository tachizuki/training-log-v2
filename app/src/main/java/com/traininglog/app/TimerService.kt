package com.traininglog.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.CountDownTimer
import android.os.IBinder
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat

class TimerService : Service() {

    private var countDownTimer: CountDownTimer? = null
    private var totalSeconds: Int = 90
    private lateinit var notificationManager: NotificationManager
    private var wakeLock: PowerManager.WakeLock? = null

    companion object {
        const val CHANNEL_ID      = "timer_channel"
        const val DONE_CHANNEL_ID = "timer_done_channel"
        const val NOTIF_ID        = 2001
        const val DONE_NOTIF_ID   = 2002
        const val ACTION_START    = "com.traininglog.app.TIMER_START"
        const val ACTION_STOP     = "com.traininglog.app.TIMER_STOP"
        const val EXTRA_SECONDS   = "seconds"
        const val BROADCAST_DONE  = "com.traininglog.app.TIMER_DONE"
    }

    override fun onCreate() {
        super.onCreate()
        notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        createChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> stopTimer()
            else -> {
                totalSeconds = intent?.getIntExtra(EXTRA_SECONDS, 90) ?: 90
                startTimer(totalSeconds)
            }
        }
        return START_REDELIVER_INTENT
    }

    // Android 14 (API 34) SHORT_SERVICE のタイムアウト時に呼ばれる。
    // 3分超タイマーがOS強制終了される場合でも完了として処理する。
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onTimeout(startId: Int) {
        countDownTimer?.cancel()
        try { vibrate() } catch (_: Exception) {}
        notificationManager.notify(DONE_NOTIF_ID, buildDoneNotification())
        stopForeground(STOP_FOREGROUND_REMOVE)
        sendBroadcast(Intent(BROADCAST_DONE))
        releaseWakeLock()
        stopSelf()
        // super を呼ばない — デフォルト実装はクラッシュする
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TrainingLog::TimerWakeLock")
        wakeLock?.acquire(10 * 60 * 1000L) // 最大10分
    }

    private fun releaseWakeLock() {
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
    }

    private fun startTimer(seconds: Int) {
        countDownTimer?.cancel()
        releaseWakeLock()
        acquireWakeLock()
        val notif = buildNotification(seconds, seconds)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_SHORT_SERVICE)
        } else {
            startForeground(NOTIF_ID, notif)
        }

        countDownTimer = object : CountDownTimer(seconds * 1000L, 1000) {
            override fun onTick(millisUntilFinished: Long) {
                val remaining = ((millisUntilFinished + 500) / 1000).toInt()
                notificationManager.notify(NOTIF_ID, buildNotification(remaining, totalSeconds))
            }
            override fun onFinish() {
                // ① 直接バイブ（フォアグラウンド時の即時フィードバック）
                try { vibrate() } catch (_: Exception) {}
                // ② 完了通知を発行 — OS が音＋バイブを担当（バックグラウンド・画面オフでも確実）
                notificationManager.notify(DONE_NOTIF_ID, buildDoneNotification())
                // ③ フォアグラウンドサービスを解除してブロードキャスト
                stopForeground(STOP_FOREGROUND_REMOVE)
                sendBroadcast(Intent(BROADCAST_DONE))
                // ④ WakeLock 解放 → 即座に停止（Handler.postDelayed は使わない）
                releaseWakeLock()
                stopSelf()
            }
        }.start()
    }

    private fun stopTimer() {
        countDownTimer?.cancel()
        releaseWakeLock()
        // 完了通知は残しておく（ユーザーが閉じるまで）
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun vibrate() {
        val pattern = longArrayOf(0, 400, 150, 400, 150, 400, 150, 400)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vm.defaultVibrator.vibrate(VibrationEffect.createWaveform(pattern, -1))
        } else {
            @Suppress("DEPRECATION")
            val v = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createWaveform(pattern, -1))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(pattern, -1)
            }
        }
    }

    private fun buildDoneNotification(): Notification {
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("target_screen", "gym-screen")
        }
        val launchPi = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, DONE_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("⏱ インターバル終了！")
            .setContentText("次のセットを始めよう")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(launchPi)
            .build()
    }

    private fun buildNotification(remaining: Int, total: Int): Notification {
        val m = remaining / 60
        val s = remaining % 60
        val timeStr = String.format("%02d:%02d", m, s)

        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("target_screen", "gym-screen")
        }
        val launchPi = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stopIntent = Intent(this, TimerService::class.java).apply { action = ACTION_STOP }
        val stopPi = PendingIntent.getService(
            this, 1, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("⏱ REST TIMER")
            .setContentText("残り $timeStr")
            .setProgress(total, total - remaining, false)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(launchPi)
            .addAction(0, "停止", stopPi)
            .build()
    }

    private fun createChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            // 進行中タイマー通知（サイレント）
            val timerChannel = NotificationChannel(
                CHANNEL_ID, "レストタイマー",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "筋トレ休憩タイマー"
                setSound(null, null)
                enableVibration(false)
            }
            // タイマー完了通知（音＋バイブ付き）
            val vibPattern = longArrayOf(0, 400, 150, 400, 150, 400, 150, 400)
            val audioAttrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            val doneChannel = NotificationChannel(
                DONE_CHANNEL_ID, "タイマー完了",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "インターバル終了通知"
                enableVibration(true)
                vibrationPattern = vibPattern
                setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION), audioAttrs)
            }
            notificationManager.createNotificationChannel(timerChannel)
            notificationManager.createNotificationChannel(doneChannel)
        }
    }

    override fun onDestroy() {
        countDownTimer?.cancel()
        releaseWakeLock()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
