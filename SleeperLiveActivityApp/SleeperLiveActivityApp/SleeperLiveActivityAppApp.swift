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

        // Check if app was launched from a remote notification
        if let remoteNotification = launchOptions?[UIApplication.LaunchOptionsKey.remoteNotification] as? [AnyHashable: Any] {
            print("📨 App launched from remote notification:")
            print("   UserInfo: \(remoteNotification)")

            // Handle push-to-start if this was the launch trigger
            if let apsData = remoteNotification["aps"] as? [String: Any],
               let event = apsData["event"] as? String,
               event == "start" {
                print("🚀 App launched via push-to-start notification")
                handlePushToStartNotification(apsData: apsData)
            }
        }

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

    // Handle remote notifications when app is in background or not running
    func application(_ application: UIApplication, didReceiveRemoteNotification userInfo: [AnyHashable: Any], fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
        print("📨 Received remote notification in background/not running:")
        print("   UserInfo: \(userInfo)")

        // Check if this is a Live Activity notification
        if let apsData = userInfo["aps"] as? [String: Any] {
            print("🎯 APS data: \(apsData)")

            if let event = apsData["event"] as? String {
                print("📡 Live Activity event: \(event)")

                // Handle push-to-start event
                if event == "start" {
                    print("🚀 Received push-to-start Live Activity notification in background")
                    handlePushToStartNotification(apsData: apsData)
                    completionHandler(.newData)
                    return
                }
            }
        }

        completionHandler(.noData)
    }

    // Handle push notifications when app is in foreground
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        print("📨 Received push notification in foreground:")
        print("   Title: \(notification.request.content.title)")
        print("   Body: \(notification.request.content.body)")
        print("   UserInfo: \(notification.request.content.userInfo)")

        // Check if this is a Live Activity notification
        if let apsData = notification.request.content.userInfo["aps"] as? [String: Any] {
            print("🎯 APS data: \(apsData)")

            if let event = apsData["event"] as? String {
                print("📡 Live Activity event: \(event)")

                // Handle push-to-start event
                if event == "start" {
                    print("🚀 Received push-to-start Live Activity notification")
                    handlePushToStartNotification(apsData: apsData)
                }
            }

            if let contentState = apsData["content-state"] as? [String: Any] {
                print("📊 Content state update: \(contentState)")
            }
        }

        completionHandler([.alert, .badge, .sound])
    }

    // Handle push-to-start notifications
    private func handlePushToStartNotification(apsData: [String: Any]) {
        print("🎯 Processing push-to-start notification")

        // Extract attributes and content state
        guard let attributesType = apsData["attributes-type"] as? String,
              attributesType == "SleeperLiveActivityAttributes",
              let attributes = apsData["attributes"] as? [String: Any],
              let userID = attributes["userID"] as? String,
              let leagueID = attributes["leagueID"] as? String,
              let contentState = apsData["content-state"] as? [String: Any] else {
            print("❌ Invalid push-to-start notification format")
            return
        }

        print("✅ Push-to-start notification parsed successfully")
        print("   User ID: \(userID)")
        print("   League ID: \(leagueID)")

        // Start the Live Activity
        Task {
            await startLiveActivityFromPush(
                userID: userID,
                leagueID: leagueID,
                contentState: contentState
            )
        }
    }

    @MainActor
    private func startLiveActivityFromPush(userID: String, leagueID: String, contentState: [String: Any]) async {
        print("🚀 Starting Live Activity from push notification")

        // Create attributes
        let attributes = SleeperLiveActivityAttributes(
            userID: userID,
            leagueID: leagueID
        )

        // Create initial state from content state
        let initialState = SleeperLiveActivityAttributes.ContentState(
            totalPoints: contentState["totalPoints"] as? Double ?? 0.0,
            activePlayersCount: contentState["activePlayersCount"] as? Int ?? 0,
            teamName: contentState["teamName"] as? String ?? "Your Team",
            opponentPoints: contentState["opponentPoints"] as? Double ?? 0.0,
            opponentTeamName: contentState["opponentTeamName"] as? String ?? "Opponent",
            leagueName: contentState["leagueName"] as? String ?? "League",
            userAvatarURL: contentState["userAvatarURL"] as? String ?? "",
            opponentAvatarURL: contentState["opponentAvatarURL"] as? String ?? "",
            userAvatarLocalURL: contentState["userAvatarLocalURL"] as? String,
            opponentAvatarLocalURL: contentState["opponentAvatarLocalURL"] as? String,
            gameStatus: contentState["gameStatus"] as? String ?? "Live",
            lastUpdate: Date()
        )

        do {
            print("🎯 Requesting Live Activity from push-to-start")

            let newActivity = try Activity.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil),
                pushType: .token
            )

            print("✅ Live Activity started from push notification with ID: \(newActivity.id)")

        } catch {
            print("❌ Failed to start Live Activity from push: \(error)")
        }
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

