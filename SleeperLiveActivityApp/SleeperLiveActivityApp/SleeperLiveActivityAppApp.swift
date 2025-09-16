//
//  SleeperLiveActivityAppApp.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit
import WidgetKit
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Set notification delegate
        UNUserNotificationCenter.current().delegate = self

        // Register for remote notifications
        UIApplication.shared.registerForRemoteNotifications()

        print("🚀 App launched, registered for remote notifications")
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("📱 Device registered for remote notifications with token: \(tokenString)")

        // Store the token for use by Live Activities
        UserDefaults.standard.set(deviceToken, forKey: "apns_device_token")
        UserDefaults.standard.synchronize()
        print("💾 Stored APNS device token in UserDefaults")
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("❌ Failed to register for remote notifications: \(error)")
    }

    // Handle push notifications when app is in foreground
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        print("📨 Received push notification in foreground:")
        print("   Title: \(notification.request.content.title)")
        print("   Body: \(notification.request.content.body)")
        print("   UserInfo: \(notification.request.content.userInfo)")

        // Check if this is a Live Activity update
        if let apsData = notification.request.content.userInfo["aps"] as? [String: Any] {
            print("🎯 APS data: \(apsData)")

            if let event = apsData["event"] as? String {
                print("📡 Live Activity event: \(event)")
            }

            if let contentState = apsData["content-state"] as? [String: Any] {
                print("📊 Content state update: \(contentState)")
            }
        }

        completionHandler([.alert, .badge, .sound])
    }

    // Handle push notification tap
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        print("👆 User tapped push notification:")
        print("   UserInfo: \(response.notification.request.content.userInfo)")
        completionHandler()
    }
}

@main
struct SleeperLiveActivityAppApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var gameMonitor = GameStateMonitor()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(gameMonitor)
                .onAppear {
                    gameMonitor.startMonitoring()
                }
        }
    }
}

