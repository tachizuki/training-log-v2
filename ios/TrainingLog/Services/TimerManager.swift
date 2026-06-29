import Foundation
import UserNotifications
import AudioToolbox

// Android の TimerService に相当。
// フォアグラウンド: Timer でカウントダウン + バイブレーション
// バックグラウンド: UNLocalNotification で時刻に通知
// （iOSはForegroundServiceが存在しないため、Notification + checkIfExpired() で代替する）

final class TimerManager: NSObject {
    static let shared = TimerManager()

    private let notifId = "timer_done"
    private var timerEndDate: Date?
    private var foregroundTimer: Timer?
    private weak var viewController: ViewController?

    func configure(viewController: ViewController) {
        self.viewController = viewController
        UNUserNotificationCenter.current().delegate = self
    }

    func start(seconds: Int) {
        stop()
        timerEndDate = Date().addingTimeInterval(TimeInterval(seconds))
        scheduleNotification(seconds: seconds)
        foregroundTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(seconds), repeats: false) { [weak self] _ in
            self?.onComplete(fromBackground: false)
        }
    }

    func stop() {
        foregroundTimer?.invalidate()
        foregroundTimer = nil
        timerEndDate = nil
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [notifId])
    }

    // SceneDelegate.sceneDidBecomeActive から呼ぶ
    // バックグラウンド中に終了していた場合に JS へ通知する
    func checkIfExpired() {
        guard let endDate = timerEndDate, Date() >= endDate else { return }
        stop()
        vibrate()
        viewController?.evaluateJS("if(typeof onTimerDone==='function')onTimerDone()")
    }

    // MARK: - Private

    private func onComplete(fromBackground: Bool) {
        // フォアグラウンドで完了した場合は pending notification を削除（二重通知を防ぐ）
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [notifId])
        timerEndDate = nil
        vibrate()
        viewController?.evaluateJS("if(typeof onTimerDone==='function')onTimerDone()")
    }

    private func scheduleNotification(seconds: Int) {
        let content = UNMutableNotificationContent()
        content.title = "⏱ REST TIMER"
        content.body  = "休憩終了！トレーニングを再開しましょう"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: TimeInterval(seconds), repeats: false)
        let request = UNNotificationRequest(identifier: notifId, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }

    // Android の vibrate(pattern) に相当する連続バイブレーション
    private func vibrate() {
        let delays: [Double] = [0.00, 0.55, 0.70, 0.85, 1.00]
        for delay in delays {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                AudioServicesPlaySystemSound(kSystemSoundID_Vibrate)
            }
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension TimerManager: UNUserNotificationCenterDelegate {

    // フォアグラウンド中にタイマー通知が来た場合はバナーを出さない（foregroundTimer が処理済み）
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        if notification.request.identifier == notifId {
            completionHandler([])
        } else {
            completionHandler([.banner, .sound])
        }
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        completionHandler()
    }
}
