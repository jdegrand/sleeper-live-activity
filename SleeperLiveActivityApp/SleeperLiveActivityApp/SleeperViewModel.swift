//
//  SleeperViewModel.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import Foundation
import Combine
import ActivityKit
import WidgetKit
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
    @Published private(set) var activity: Activity<SleeperLiveActivityAttributes>?
    
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
                Task {
                    await self.startLiveActivity()
                }
            }
        }

        NotificationCenter.default.addObserver(
            forName: .autoEndLiveActivity,
            object: nil,
            queue: .main
        ) { _ in
            if self.isLiveActivityActive {
                Task {
                    await self.stopLiveActivity()
                }
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
            if let currentActivity = Activity<SleeperLiveActivityAttributes>.activities.first(where: { $0.activityState == .active }) {
                self.activity = currentActivity
                isLiveActivityActive = true
                
                // Update local state from the activity
                let state = currentActivity.content.state
                currentPoints = state.totalPoints
                activePlayers = state.activePlayersCount
                lastUpdate = state.lastUpdate
            }
        }
    }
    
    @MainActor
    func startLiveActivity() async {
        guard isConfigured else {
            errorMessage = "Please configure your Sleeper credentials first"
            return
        }
        
        // Check if we already have an active activity
        if let currentActivity = Activity<SleeperLiveActivityAttributes>.activities.first(where: { $0.activityState == .active }) {
            self.activity = currentActivity
            isLiveActivityActive = true
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
            totalPoints: currentPoints,
            activePlayersCount: activePlayers,
            teamName: "Your Team",
            opponentPoints: 0.0, // Will be updated in the first fetch
            gameStatus: "Starting...",
            lastUpdate: Date()
        )
        
        do {
            let newActivity = try Activity.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil),
                pushType: .token
            )
            
            print("Live Activity started successfully with ID: \(newActivity.id)")
            self.activity = newActivity
            isLiveActivityActive = true
            errorMessage = nil
            
            // Register with backend
            await registerWithBackend()
            await notifyBackendLiveActivityStarted()
            
            // Start monitoring for updates
            startMonitoringActivityUpdates()
            
        } catch {
            print("Failed to start Live Activity: \(error)")
            errorMessage = "Failed to start Live Activity: \(error.localizedDescription)"
        }
    }
    
    @MainActor
    func stopLiveActivity() async {
        guard let activity = activity else { return }
        
        // Create a final update before ending
        let finalState = SleeperLiveActivityAttributes.ContentState(
            totalPoints: currentPoints,
            activePlayersCount: activePlayers,
            teamName: "Your Team",
            opponentPoints: 0.0,
            gameStatus: "Final",
            lastUpdate: Date()
        )
        
        // Update with final state before ending
        await activity.update(using: finalState)
        
        // End the activity
        await activity.end(using: finalState, dismissalPolicy: .immediate)
        
        // Clean up
        self.activity = nil
        isLiveActivityActive = false
        
        // Notify backend
        await notifyBackendLiveActivityStopped()
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
                
                await updateLiveActivity(with: matchups, userMatchup: userMatchup)
            }
            
        } catch {
            errorMessage = "Failed to fetch data: \(error.localizedDescription)"
        }
    }
    
    private func updateLiveActivity(with matchups: [[String: Any]], userMatchup: [String: Any]) async {
        guard let userRoster = matchups.first(where: { $0["roster_id"] as? Int == userMatchup["roster_id"] as? Int ?? 0 }) else { return }
        
        let newPoints = userMatchup["points"] as? Double ?? 0.0
        let newActivePlayers = (userRoster["starters"] as? [String])?.count ?? 0
        let opponentPoints = findOpponentPoints(matchups: matchups, userMatchup: userMatchup)
        let now = Date()
        
        // Update local state
        currentPoints = newPoints
        activePlayers = newActivePlayers
        lastUpdate = now
        
        // Update Live Activity if active
        if let activity = activity {
            let newState = SleeperLiveActivityAttributes.ContentState(
                totalPoints: newPoints,
                activePlayersCount: newActivePlayers,
                teamName: "Your Team",
                opponentPoints: opponentPoints,
                gameStatus: "Live",
                lastUpdate: now
            )
            
            do {
                try await activity.update(using: newState)
                print("Live Activity updated successfully")
            } catch {
                print("Failed to update Live Activity: \(error)")
            }
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
        guard let activity = activity else { return }
        
        // Get the push token for this activity
        let pushToken = await getPushToken(for: activity)
        let deviceID = getDeviceID()
        
        let config = UserConfig(
            userID: userID,
            leagueID: leagueID,
            pushToken: pushToken,
            deviceID: deviceID
        )
        
        do {
            try await apiClient.registerUser(config: config)
            print("Successfully registered with backend")
        } catch {
            print("Failed to register with backend: \(error)")
        }
    }
    
    private func startMonitoringActivityUpdates() {
        Task {
            for await activity in Activity<SleeperLiveActivityAttributes>.activityUpdates {
                print("Activity update received: \(activity.id) - \(activity.activityState)")
                
                // Update local state when activity changes
                if activity.activityState == .ended || activity.activityState == .dismissed {
                    await MainActor.run {
                        self.activity = nil
                        self.isLiveActivityActive = false
                    }
                } else if activity.activityState == .active {
                    await MainActor.run {
                        self.activity = activity
                        self.isLiveActivityActive = true
                    }
                }
            }
        }
    }
    
    private func getPushToken(for activity: Activity<SleeperLiveActivityAttributes>) async -> String {
        // In a real implementation, you would get the actual push token
        // For now, return a placeholder that includes the activity ID
        return "\(activity.id).\(getDeviceID())"
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
