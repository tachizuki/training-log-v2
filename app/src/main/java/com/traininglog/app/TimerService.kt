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
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
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
    private var mediaPlayer: MediaPlayer? = null
    private var audioFocusReq: AudioFocusRequest? = null

    companion object {
        const val CHANNEL_ID      = "timer_channel"
        const val DONE_CHANNEL_ID = "timer_done_channel_v6" // v6: 同梱キッチンタイマー音3回版に更新（チャンネル再作成で確実に反映）
        const val DONE_SILENT_CHANNEL_ID = "timer_done_silent_v1" // イヤホン時: 音はMediaPlayerで再生する無音チャンネル
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
        // OSによるサービス再起動時に古いタイマーが全長で再開しないよう NOT_STICKY
        return START_NOT_STICKY
    }

    // Android 14 (API 34) SHORT_SERVICE のタイムアウト時に呼ばれる。
    // 3分超タイマーがOS強制終了される場合でも完了として処理する。
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onTimeout(startId: Int) {
        countDownTimer?.cancel()
        // onTimeout は3分超(SHORT_SERVICE上限)のみ＝レストタイマー(≤180s)では発生しない稀ケース。
        notificationManager.notify(DONE_NOTIF_ID, buildDoneNotification(DONE_SILENT_CHANNEL_ID))
        sendBroadcast(Intent(BROADCAST_DONE))
        fireAlarm()
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
        prepareAlarm()   // 完了音を事前prepare。完了時のズレ（バイブ→音の遅延）をなくす
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
                // 事前prepare済みの音を即start＋バイブを同時発火＝ズレなし。通知非依存で常に鳴る。
                notificationManager.notify(DONE_NOTIF_ID, buildDoneNotification(DONE_SILENT_CHANNEL_ID))
                sendBroadcast(Intent(BROADCAST_DONE))
                fireAlarm()
            }
        }.start()
    }

    private fun stopTimer() {
        countDownTimer?.cancel()
        releaseAlarmPlayer()
        abandonFocus()
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

    // イヤホン（有線/USB/Bluetooth）が出力に接続されているか
    private fun earphonesConnected(): Boolean {
        return try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).any { d ->
                    d.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
                    d.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                    d.type == AudioDeviceInfo.TYPE_USB_HEADSET ||
                    d.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                    d.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                    (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && d.type == AudioDeviceInfo.TYPE_BLE_HEADSET)
                }
            } else {
                @Suppress("DEPRECATION")
                (am.isWiredHeadsetOn || am.isBluetoothA2dpOn)
            }
        } catch (_: Exception) { false }
    }

    // タイマー開始時に音源を事前ロード(prepare)。完了時のprepare遅延を消し、バイブと同時に鳴らす
    private fun prepareAlarm() {
        try {
            releaseAlarmPlayer()
            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            val uri = Uri.parse("android.resource://" + packageName + "/raw/timer_done")
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(attrs)
                setDataSource(this@TimerService, uri)
                setOnCompletionListener {
                    releaseAlarmPlayer(); abandonFocus(); finishService()
                }
                prepare()
            }
        } catch (_: Exception) { mediaPlayer = null }
    }

    private fun releaseAlarmPlayer() {
        try { mediaPlayer?.release() } catch (_: Exception) {}
        mediaPlayer = null
    }

    private fun requestFocus() {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                    .setAudioAttributes(attrs).build()
                audioFocusReq = req
                am.requestAudioFocus(req)
            } else {
                @Suppress("DEPRECATION")
                am.requestAudioFocus(null, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            }
        } catch (_: Exception) {}
    }

    // 完了時：事前prepare済みなら即start＋バイブを同時発火（ズレなし）。準備失敗時のみフォールバック。
    private fun fireAlarm() {
        val mp = mediaPlayer
        if (mp != null) {
            requestFocus()
            try { mp.start() } catch (_: Exception) {}
            try { vibrate() } catch (_: Exception) {}
        } else {
            try { vibrate() } catch (_: Exception) {}
            playAlarmSound()
        }
    }

    // 完了音を自前で再生（フォールバック：事前prepareに失敗した場合のみ）。再生完了で finishService。
    private fun playAlarmSound() {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                    .setAudioAttributes(attrs).build()
                audioFocusReq = req
                am.requestAudioFocus(req)
            } else {
                @Suppress("DEPRECATION")
                am.requestAudioFocus(null, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            }
            val soundUri = Uri.parse("android.resource://" + packageName + "/raw/timer_done")
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(attrs)
                setDataSource(this@TimerService, soundUri)
                setOnCompletionListener {
                    try { it.release() } catch (_: Exception) {}
                    mediaPlayer = null
                    abandonFocus()
                    finishService()
                }
                prepare()
                start()
            }
        } catch (_: Exception) {
            abandonFocus()
            finishService()
        }
    }

    // フォアグラウンド解除 → WakeLock 解放 → サービス停止（完了処理の共通化）
    private fun finishService() {
        stopForeground(STOP_FOREGROUND_REMOVE)
        releaseWakeLock()
        stopSelf()
    }

    private fun abandonFocus() {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                audioFocusReq?.let { am.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION") am.abandonAudioFocus(null)
            }
        } catch (_: Exception) {}
        audioFocusReq = null
    }

    private fun buildDoneNotification(channelId: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("target_screen", "gym-screen")
        }
        val launchPi = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, channelId)
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
            // タイマー完了通知（USAGE_NOTIFICATION: 通常の「音を出すモード」=着信/通知音量で鳴る。
            // 以前は USAGE_ALARM でアラーム音量基準だったため、アラーム音量0だと音モードでも無音だった）
            val vibPattern = longArrayOf(0, 400, 150, 400, 150, 400, 150, 400)
            val audioAttrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            // 同梱のキッチンタイマー音（res/raw/timer_done.mp3 = OtoLogic「キッチンタイマー03」）
            val soundUri = Uri.parse("android.resource://" + packageName + "/raw/timer_done")
            val doneChannel = NotificationChannel(
                DONE_CHANNEL_ID, "タイマー完了",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "インターバル終了通知"
                enableVibration(true)
                vibrationPattern = vibPattern
                setSound(soundUri, audioAttrs)
            }
            // タイマー完了（イヤホン時）: 無音。音は MediaPlayer 側で再生する
            val doneSilentChannel = NotificationChannel(
                DONE_SILENT_CHANNEL_ID, "タイマー完了（イヤホン）",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "イヤホン接続時のインターバル終了（音はアプリ側で再生）"
                enableVibration(true)
                vibrationPattern = vibPattern
                setSound(null, null)
            }
            notificationManager.createNotificationChannel(timerChannel)
            notificationManager.createNotificationChannel(doneChannel)
            notificationManager.createNotificationChannel(doneSilentChannel)
        }
    }

    override fun onDestroy() {
        countDownTimer?.cancel()
        try { mediaPlayer?.release() } catch (_: Exception) {}
        mediaPlayer = null
        abandonFocus()
        releaseWakeLock()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
