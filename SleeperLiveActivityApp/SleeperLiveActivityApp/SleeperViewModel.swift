//
//  SleeperViewModel.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit
import UserNotifications
import Combine

class SleeperViewModel: ObservableObject {
    @Published var userID: String = ""
    @Published var leagueID: String = ""
    @Published var isConfigured: Bool = false
    @Published var isLiveActivityActive: Bool = false
    @Published var currentPoints: Double = 0.0
    @Published var activePlayers: Int = 0
    @Published var lastUpdate: Date = Date()
    @Published var errorMessage: String?
    
    private let apiClient = SleeperAPIClient()
    private var cancellables = Set<AnyCancellable>()
    private var currentActivity: Activity<SleeperLiveActivityAttributes>?
    
    // Configuration keys
    private let userIDKey = "SleeperUserID"
    private let leagueIDKey = "SleeperLeagueID"
    private let deviceIDKey = "SleeperDeviceID"
    
    init() {
        loadConfiguration()
        requestNotificationPermissions()
        setupNotificationObservers()
    }
    
    private func setupNotificationObservers() {
        NotificationCenter.default.addObserver(
            forName: .autoStartLiveActivity,
            object: nil,
            queue: .main
        ) { _ in
            if !self.isLiveActivityActive {
                self.startLiveActivity()
            }
        }
        
        NotificationCenter.default.addObserver(
            forName: .autoEndLiveActivity,
            object: nil,
            queue: .main
        ) { _ in
            if self.isLiveActivityActive {
                self.stopLiveActivity()
            }
        }
    }
    
    func loadConfiguration() {
        userID = UserDefaults.standard.string(forKey: userIDKey) ?? ""
        leagueID = UserDefaults.standard.string(forKey: leagueIDKey) ?? ""
        isConfigured = !userID.isEmpty && !leagueID.isEmpty
        
        // Check if Live Activity is currently running
        checkLiveActivityStatus()
    }
    
    func saveConfiguration() {
        UserDefaults.standard.set(userID, forKey: userIDKey)
        UserDefaults.standard.set(leagueID, forKey: leagueIDKey)
        isConfigured = !userID.isEmpty && !leagueID.isEmpty
        
        // Register with backend if configured
        if isConfigured {
            Task {
                await registerWithBackend()
            }
        }
    }
    
    private func requestNotificationPermissions() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if let error = error {
                print("Notification permission error: \(error)")
            }
        }
    }
    
    private func checkLiveActivityStatus() {
        if ActivityAuthorizationInfo().areActivitiesEnabled {
            // Check if we have an active Live Activity
            for activity in Activity<SleeperLiveActivityAttributes>.activities {
                if activity.activityState == .active {
                    currentActivity = activity
                    isLiveActivityActive = true
                    break
                }
            }
        }
    }
    
    func startLiveActivity() {
        guard isConfigured else {
            errorMessage = "Please configure your Sleeper credentials first"
            return
        }
        
        let authInfo = ActivityAuthorizationInfo()
        print("Live Activities enabled: \(authInfo.areActivitiesEnabled)")
        print("Live Activities frequent updates enabled: \(authInfo.frequentPushesEnabled)")
        
        guard authInfo.areActivitiesEnabled else {
            errorMessage = "Live Activities are not enabled. Please enable them in Settings > Face ID & Passcode > Live Activities."
            return
        }
        
        let attributes = SleeperLiveActivityAttributes(
            userID: userID,
            leagueID: leagueID
        )
        
        let initialState = SleeperLiveActivityAttributes.ContentState(
            totalPoints: 0.0,
            activePlayersCount: 0,
            teamName: "Your Team",
            opponentPoints: 0.0,
            gameStatus: "Starting...",
            lastUpdate: Date()
        )
        
        print("Attempting to start Live Activity...")
        print("Attributes: userID=\(userID), leagueID=\(leagueID)")
        
        do {
            let activity = try Activity<SleeperLiveActivityAttributes>.request(
                attributes: attributes,
                contentState: initialState,
                pushType: .token
            )
            
            print("Live Activity started successfully with ID: \(activity.id)")
            currentActivity = activity
            isLiveActivityActive = true
            
            // Register with backend
            Task {
                await registerWithBackend()
                await notifyBackendLiveActivityStarted()
            }
            
        } catch {
            print("Live Activity error details: \(error)")
            print("Error type: \(type(of: error))")
            print("Error code: \((error as NSError).code)")
            print("Error domain: \((error as NSError).domain)")
            errorMessage = "Failed to start Live Activity: \(error.localizedDescription)"
        }
    }
    
    func stopLiveActivity() {
        Task {
            await currentActivity?.end(dismissalPolicy: .immediate)
            currentActivity = nil
            isLiveActivityActive = false
            
            // Notify backend
            await notifyBackendLiveActivityStopped()
        }
    }
    
    func refreshData() {
        Task {
            await fetchLatestData()
        }
    }
    
    @MainActor
    private func fetchLatestData() async {
        guard isConfigured else { return }
        
        do {
            // Get current NFL state
            let nflState = try await apiClient.getNFLState()
            let currentWeek = nflState["week"] as? Int ?? 1
            
            // Get matchups
            let matchups = try await apiClient.getMatchups(leagueID: leagueID, week: currentWeek)
            
            // Get rosters to find user's team
            let rosters = try await apiClient.getLeagueRosters(leagueID: leagueID)
            
            // Find user's roster and matchup data
            if let userRoster = rosters.first(where: { $0["owner_id"] as? String == userID }),
               let rosterID = userRoster["roster_id"] as? Int,
               let userMatchup = matchups.first(where: { $0["roster_id"] as? Int == rosterID }) {
                
                currentPoints = userMatchup["points"] as? Double ?? 0.0
                activePlayers = (userRoster["starters"] as? [String])?.count ?? 0
                lastUpdate = Date()
                
                // Update Live Activity if active
                if let activity = currentActivity {
                    let newState = SleeperLiveActivityAttributes.ContentState(
                        totalPoints: currentPoints,
                        activePlayersCount: activePlayers,
                        teamName: "Team \(rosterID)",
                        opponentPoints: findOpponentPoints(matchups: matchups, userMatchup: userMatchup),
                        gameStatus: "Live",
                        lastUpdate: lastUpdate
                    )
                    
                    await activity.update(using: newState)
                }
            }
            
        } catch {
            errorMessage = "Failed to fetch data: \(error.localizedDescription)"
        }
    }
    
    private func findOpponentPoints(matchups: [[String: Any]], userMatchup: [String: Any]) -> Double {
        guard let matchupID = userMatchup["matchup_id"] as? Int,
              let userRosterID = userMatchup["roster_id"] as? Int else {
            return 0.0
        }
        
        for matchup in matchups {
            if let otherMatchupID = matchup["matchup_id"] as? Int,
               let otherRosterID = matchup["roster_id"] as? Int,
               otherMatchupID == matchupID && otherRosterID != userRosterID {
                return matchup["points"] as? Double ?? 0.0
            }
        }
        
        return 0.0
    }
    
    private func getDeviceID() -> String {
        if let deviceID = UserDefaults.standard.string(forKey: deviceIDKey) {
            return deviceID
        }
        
        let newDeviceID = UUID().uuidString
        UserDefaults.standard.set(newDeviceID, forKey: deviceIDKey)
        return newDeviceID
    }
    
    private func registerWithBackend() async {
        guard let pushToken = await getPushToken() else { return }
        
        let deviceID = getDeviceID()
        let config = UserConfig(
            userID: userID,
            leagueID: leagueID,
            pushToken: pushToken,
            deviceID: deviceID
        )
        
        do {
            try await apiClient.registerUser(config: config)
        } catch {
            print("Failed to register with backend: \(error)")
        }
    }
    
    private func getPushToken() async -> String? {
        // In a real implementation, you would get the actual push token
        // For now, return a placeholder
        return "placeholder_push_token_\(getDeviceID())"
    }
    
    private func notifyBackendLiveActivityStarted() async {
        let deviceID = getDeviceID()
        do {
            try await apiClient.startLiveActivity(deviceID: deviceID)
        } catch {
            print("Failed to notify backend of Live Activity start: \(error)")
        }
    }
    
    private func notifyBackendLiveActivityStopped() async {
        let deviceID = getDeviceID()
        do {
            try await apiClient.endLiveActivity(deviceID: deviceID)
        } catch {
            print("Failed to notify backend of Live Activity stop: \(error)")
        }
    }
}

// MARK: - Data Models
struct UserConfig: Codable {
    let userID: String
    let leagueID: String
    let pushToken: String
    let deviceID: String
    
    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case leagueID = "league_id"
        case pushToken = "push_token"
        case deviceID = "device_id"
    }
}
