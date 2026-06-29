import UserNotifications

// Android の NotificationReceiver に相当。
// UNCalendarNotificationTrigger で毎日指定時刻にローカル通知を発火する。

final class NotificationManager {
    static let shared = NotificationManager()
    private let notifId = "daily_reminder"

    func requestPermission(completion: ((Bool) -> Void)? = nil) {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { granted, _ in
            DispatchQueue.main.async { completion?(granted) }
        }
    }

    func schedule(hour: Int, minute: Int) {
        cancel()

        var components = DateComponents()
        components.hour   = hour
        components.minute = minute

        let content = UNMutableNotificationContent()
        content.title = "トレーニングログ"
        content.body  = "今日のトレーニングを記録しましょう！"
        content.sound = .default

        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: true)
        let request = UNNotificationRequest(identifier: notifId, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }

    func cancel() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [notifId])
    }

    // JS側の getNotificationSettings() 向けに現在設定を返す
    func getSettings(completion: @escaping (_ enabled: Bool, _ hour: Int, _ minute: Int) -> Void) {
        UNUserNotificationCenter.current().getPendingNotificationRequests { [self] requests in
            if let req = requests.first(where: { $0.identifier == self.notifId }),
               let trigger = req.trigger as? UNCalendarNotificationTrigger,
               let h = trigger.dateComponents.hour,
               let m = trigger.dateComponents.minute {
                DispatchQueue.main.async { completion(true, h, m) }
            } else {
                let h = UserDefaults.standard.integer(forKey: "notif_hour")
                let m = UserDefaults.standard.integer(forKey: "notif_minute")
                DispatchQueue.main.async { completion(false, h == 0 ? 20 : h, m) }
            }
        }
    }
}
