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
    @Published var username: String = ""
    @Published var userID: String = "" // Internal storage - resolved from username
    @Published var leagueID: String = ""
    @Published var isConfigured: Bool = false
    @Published var isLiveActivityActive: Bool = false
    @Published var currentPoints: Double = 0.0
    @Published var activePlayers: Int = 0
    @Published var opponentPoints: Double = 0.0
    @Published var teamName: String = "Your Team"
    @Published var opponentTeamName: String = "Opponent"
    @Published var leagueName: String = "Fantasy Football"
    @Published var userAvatarURL: String = ""
    @Published var opponentAvatarURL: String = ""

    // Avatar loading timestamps to prevent frequent re-downloads
    private var lastUserAvatarUpdate: Date?
    private var lastOpponentAvatarUpdate: Date?
    private let avatarUpdateInterval: TimeInterval = 3600 // 1 hour

    private let imageLoader = ImageLoader.shared
    @Published var gameStatus: String = "Starting..."
    @Published var lastUpdate: Date = Date()
    @Published var errorMessage: String?
    
    private let apiClient = SleeperAPIClient()
    private var cancellables = Set<AnyCancellable>()
    @Published private(set) var activity: Activity<SleeperLiveActivityAttributes>?
    
    // Configuration keys
    private let usernameKey = "SleeperUsername"
    private let userIDKey = "SleeperUserID" // Cached user ID from username
    private let leagueIDKey = "SleeperLeagueID"
    private let deviceIDKey = "SleeperDeviceID"
    
    init() {
        loadConfiguration()
        requestNotificationPermissions()
        if #available(iOS 17.2, *) {
            subscribeToPushToStartTokens()
        }
    }
    
    
    func loadConfiguration() {
        username = UserDefaults.standard.string(forKey: usernameKey) ?? ""
        userID = UserDefaults.standard.string(forKey: userIDKey) ?? ""
        leagueID = UserDefaults.standard.string(forKey: leagueIDKey) ?? ""
        isConfigured = !username.isEmpty && !leagueID.isEmpty

        // Check if Live Activity is currently running
        checkLiveActivityStatus()

        // Fetch data if configured
        if isConfigured {
            Task {
                // Resolve username to userID if needed
                if userID.isEmpty {
                    await resolveUsernameToUserID()
                }
                await fetchLeagueInfo()
                await fetchLatestData()
            }
        }
    }
    
    func saveConfiguration() {
        UserDefaults.standard.set(username, forKey: usernameKey)
        UserDefaults.standard.set(userID, forKey: userIDKey)
        UserDefaults.standard.set(leagueID, forKey: leagueIDKey)
        isConfigured = !username.isEmpty && !leagueID.isEmpty

        // Only resolve username and register with backend - data fetching handled elsewhere
        if isConfigured {
            Task {
                await resolveUsernameToUserID()
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

        // Fetch latest data to ensure we have current info and avatars before starting
        await fetchLatestData()

        let attributes = SleeperLiveActivityAttributes(
            userID: userID,
            leagueID: leagueID
        )

        let initialState = SleeperLiveActivityAttributes.ContentState(
            totalPoints: currentPoints,
            activePlayersCount: activePlayers,
            teamName: teamName,
            opponentPoints: opponentPoints,
            opponentTeamName: opponentTeamName,
            leagueName: leagueName,
            userAvatarURL: userAvatarURL,
            opponentAvatarURL: opponentAvatarURL,
            gameStatus: gameStatus,
            lastUpdate: Date()
        )
        
        do {
            print("🎯 Requesting Live Activity with pushType: .token")

            let newActivity = try Activity.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil),
                pushType: .token
            )

            print("Live Activity started successfully with ID: \(newActivity.id)")
            print("Activity state: \(newActivity.activityState)")
            self.activity = newActivity
            isLiveActivityActive = true
            errorMessage = nil
            print("🔍 Global token observation will handle token registration")

            // Register with backend
            await registerWithBackend()
            await notifyBackendLiveActivityStarted()

            // Start monitoring for updates
            startMonitoringActivityUpdates()

        } catch {
            print("❌ Failed to start Live Activity: \(error)")
            print("Error type: \(type(of: error))")
            print("Error description: \(error.localizedDescription)")

            if error.localizedDescription.contains("activityDisabled") {
                errorMessage = "Live Activities are disabled. Enable them in Settings > Face ID & Passcode > Live Activities."
            } else if error.localizedDescription.contains("frequentPushesDisabled") {
                errorMessage = "Frequent push updates are disabled for Live Activities."
            } else {
                errorMessage = "Failed to start Live Activity: \(error.localizedDescription)"
            }
        }
    }
    
    @MainActor
    func stopLiveActivity() async {
        guard let activity = activity else { return }
        
        // Create a final update before ending
        let finalState = SleeperLiveActivityAttributes.ContentState(
            totalPoints: currentPoints,
            activePlayersCount: activePlayers,
            teamName: teamName,
            opponentPoints: opponentPoints,
            opponentTeamName: opponentTeamName,
            leagueName: leagueName,
            userAvatarURL: userAvatarURL,
            opponentAvatarURL: opponentAvatarURL,
            gameStatus: "Final",
            lastUpdate: Date(),
            message: "Game ended"
        )
        
        // Update with final state before ending
        await activity.update(.init(state: finalState, staleDate: nil))
        
        // End the activity
        await activity.end(using: finalState, dismissalPolicy: .immediate)
        
        // Clean up
        self.activity = nil
        isLiveActivityActive = false

        // Notify backend
        await notifyBackendLiveActivityStopped()
    }
    
    func refreshData() {
        // Manual refresh - primarily for testing
        // Live Activity updates now come via push notifications from backend
        Task {
            await fetchLatestData()
        }
    }

    @MainActor
    private func fetchLeagueInfo() async {
        guard isConfigured else {
            print("❌ fetchLeagueInfo: Not configured")
            return
        }

        print("🏆 Fetching league info for leagueID: \(leagueID)")

        do {
            let leagueInfo = try await apiClient.getLeagueInfo(leagueID: leagueID)
            if let name = leagueInfo["name"] as? String {
                leagueName = name
                print("✅ League name set to: \(name)")
            } else {
                print("⚠️ No league name found in response")
            }
        } catch {
            print("❌ Failed to fetch league info: \(error)")
        }
    }

    @MainActor
    private func fetchLatestData() async {
        guard isConfigured else {
            print("❌ fetchLatestData: Not configured")
            return
        }

        print("🔄 fetchLatestData: Starting for userID: \(userID), leagueID: \(leagueID)")

        do {
            // Get current NFL state
            print("🏈 Fetching NFL state...")
            let nflState = try await apiClient.getNFLState()
            let currentWeek = nflState["week"] as? Int ?? 1
            print("📅 Current NFL week: \(currentWeek)")

            // Get matchups
            print("⚡ Fetching matchups for week \(currentWeek)...")
            let matchups = try await apiClient.getMatchups(leagueID: leagueID, week: currentWeek)
            print("🎯 Found \(matchups.count) matchups")

            // Get rosters to find user's team
            print("👥 Fetching rosters...")
            let rosters = try await apiClient.getLeagueRosters(leagueID: leagueID)
            print("🏆 Found \(rosters.count) rosters")

            // Find user's roster and matchup data
            if let userRoster = rosters.first(where: { $0["owner_id"] as? String == userID }),
               let rosterID = userRoster["roster_id"] as? Int,
               let userMatchup = matchups.first(where: { $0["roster_id"] as? Int == rosterID }) {

                print("✅ Found user roster and matchup data")
                await updateLiveActivity(with: matchups, userMatchup: userMatchup)
            } else {
                print("❌ Could not find user roster or matchup")
            }

        } catch {
            let errorMessage = "Failed to fetch data: \(error.localizedDescription)"
            print("💥 API Error: \(errorMessage)")
            self.errorMessage = errorMessage
        }
    }
    
    private func updateLiveActivity(with matchups: [[String: Any]], userMatchup: [String: Any]) async {
        let newPoints = userMatchup["points"] as? Double ?? 0.0
        let newOpponentPoints = findOpponentPoints(matchups: matchups, userMatchup: userMatchup)
        let (userTeamName, opponentName) = await getTeamNames(matchups: matchups, userMatchup: userMatchup)
        let newGameStatus = determineGameStatus()
        let now = Date()

        // Count active players (those currently in games)
        let newActivePlayers = await countActivePlayers(userMatchup: userMatchup)

        // Update local state on main thread
        await MainActor.run {
            currentPoints = newPoints
            activePlayers = newActivePlayers
            opponentPoints = newOpponentPoints
            teamName = userTeamName
            opponentTeamName = opponentName
            gameStatus = newGameStatus
            lastUpdate = now
        }

        print("📊 Updated scores - You: \(newPoints), Opponent: \(newOpponentPoints), Active: \(newActivePlayers)")

        // Update Live Activity if active
        if let activity = activity {
            print("🎯 Updating Live Activity with avatars:")
            print("   Remote URLs - User: \(userAvatarURL), Opponent: \(opponentAvatarURL)")

            let newState = SleeperLiveActivityAttributes.ContentState(
                totalPoints: newPoints,
                activePlayersCount: newActivePlayers,
                teamName: userTeamName,
                opponentPoints: newOpponentPoints,
                opponentTeamName: opponentName,
                leagueName: leagueName,
                userAvatarURL: userAvatarURL,
                opponentAvatarURL: opponentAvatarURL,
                gameStatus: newGameStatus,
                lastUpdate: now
            )

            do {
                try await activity.update(using: newState)
                print("✅ Live Activity updated successfully")
            } catch {
                print("❌ Failed to update Live Activity: \(error)")
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

    
    private func getTeamNames(matchups: [[String: Any]], userMatchup: [String: Any]) async -> (String, String) {
        // Get roster information to find team names
        do {
            let rosters = try await apiClient.getLeagueRosters(leagueID: leagueID)
            let userRosterID = userMatchup["roster_id"] as? Int ?? 0
            let opponentRosterID = findOpponentRosterID(matchups: matchups, userMatchup: userMatchup)

            // Find user roster
            if let userRoster = rosters.first(where: { $0["roster_id"] as? Int == userRosterID }),
               let userOwnerID = userRoster["owner_id"] as? String {

                // Find opponent roster
                if let opponentRoster = rosters.first(where: { $0["roster_id"] as? Int == opponentRosterID }),
                   let opponentOwnerID = opponentRoster["owner_id"] as? String {

                    // Get user info for avatars and display names
                    async let userInfo = try? apiClient.getUser(userID: userOwnerID)
                    async let opponentInfo = try? apiClient.getUser(userID: opponentOwnerID)

                    let userResult = await userInfo
                    let opponentResult = await opponentInfo

                    // Update avatar URLs
                    if let userAvatar = userResult?["avatar"] as? String {
                        let userAvatarURL = "https://sleepercdn.com/avatars/thumbs/\(userAvatar)"
                        await MainActor.run {
                            self.userAvatarURL = userAvatarURL
                        }

                        // Download to cache for main app usage
                        await ImageCacheManager.shared.downloadAndCacheImageAsLocalURL(from: userAvatarURL)
                        await MainActor.run {
                            self.lastUserAvatarUpdate = Date()
                        }
                    } else {
                        await MainActor.run {
                            self.userAvatarURL = ""
                        }
                    }

                    if let opponentAvatar = opponentResult?["avatar"] as? String {
                        let opponentAvatarURL = "https://sleepercdn.com/avatars/thumbs/\(opponentAvatar)"
                        await MainActor.run {
                            self.opponentAvatarURL = opponentAvatarURL
                        }

                        // Download to cache for main app usage
                        await ImageCacheManager.shared.downloadAndCacheImageAsLocalURL(from: opponentAvatarURL)
                        await MainActor.run {
                            self.lastOpponentAvatarUpdate = Date()
                        }
                    } else {
                        await MainActor.run {
                            self.opponentAvatarURL = ""
                        }
                    }

                    // Get display names or use usernames
                    let userName = userResult?["display_name"] as? String ?? userResult?["username"] as? String ?? "Team \(userRosterID)"
                    let opponentName = opponentResult?["display_name"] as? String ?? opponentResult?["username"] as? String ?? "Team \(opponentRosterID)"

                    return (userName, opponentName)
                }
            }
        } catch {
            print("Failed to get team info: \(error)")
        }

        // Fallback to roster IDs
        let userRosterID = userMatchup["roster_id"] as? Int ?? 0
        let opponentRosterID = findOpponentRosterID(matchups: matchups, userMatchup: userMatchup)
        let userTeam = "Team \(userRosterID)"
        let opponentTeam = opponentRosterID > 0 ? "Team \(opponentRosterID)" : "Opponent"

        return (userTeam, opponentTeam)
    }

    private func findOpponentRosterID(matchups: [[String: Any]], userMatchup: [String: Any]) -> Int {
        guard let matchupID = userMatchup["matchup_id"] as? Int,
              let userRosterID = userMatchup["roster_id"] as? Int else {
            return 0
        }

        for matchup in matchups {
            if let otherMatchupID = matchup["matchup_id"] as? Int,
               let otherRosterID = matchup["roster_id"] as? Int,
               otherMatchupID == matchupID && otherRosterID != userRosterID {
                return otherRosterID
            }
        }

        return 0
    }

    private func determineGameStatus() -> String {
        // For now, determine status based on whether we have active players
        if activePlayers > 0 {
            return "Live"
        } else if currentPoints > 0 {
            return "Final"
        } else {
            return "Pre-Game"
        }
    }

    private func countActivePlayers(userMatchup: [String: Any]) async -> Int {
        // For now, return the count of starters
        // In a real implementation, you'd check which players are currently in active games
        // by cross-referencing with NFL game state

        // Get rosters to find starters
        do {
            let rosters = try await apiClient.getLeagueRosters(leagueID: leagueID)
            if let userRoster = rosters.first(where: { $0["owner_id"] as? String == userID }),
               let starters = userRoster["starters"] as? [String] {
                // For now, assume all starters are active if it's during game time
                // In reality, you'd check NFL state to see which games are active
                return starters.count
            }
        } catch {
            print("Failed to get rosters for active player count: \(error)")
        }

        return 0
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
        guard let activity = activity else {
            print("❌ No activity available for registration")
            return
        }

        print("🚀 Starting backend registration...")

        // Get the Live Activity specific push token
        let pushToken = await getPushToken(for: activity)
        let deviceID = getDeviceID()

        print("📱 Device ID: \(deviceID)")
        print("👤 User ID: \(userID)")
        print("🏆 League ID: \(leagueID)")
        print("🔑 Push Token: \(pushToken)")

        let config = UserConfig(
            userID: userID,
            leagueID: leagueID,
            pushToken: pushToken,
            deviceID: deviceID,
            pushToStartToken: nil
        )

        do {
            try await apiClient.registerUser(config: config)
            print("✅ Successfully registered with backend")
        } catch {
            print("❌ Failed to register with backend: \(error)")
            errorMessage = "Backend registration failed: \(error.localizedDescription)"
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
        print("🔗 Getting push token for activity: \(activity.id)")

        for await pushToken in activity.pushTokenUpdates {
            let tokenString = pushToken.map { String(format: "%02x", $0) }.joined()
            print("✅ Received push token: \(tokenString)")
            return tokenString
        }

        print("❌ Failed to get push token, using fallback")
        return "\(activity.id).\(getDeviceID())"
    }

    // MARK: - Push Notification Support
    // Live Activity updates now come via push notifications from the backend
    // The backend monitors Sleeper API and sends updates when scores change

    // MARK: - Username Resolution
    @MainActor
    private func resolveUsernameToUserID() async {
        guard !username.isEmpty else { return }

        do {
            print("🔍 Resolving username '\(username)' to user ID...")
            let userData = try await apiClient.getUserByUsername(username: username)

            if let resolvedUserID = userData["user_id"] as? String {
                userID = resolvedUserID
                // Cache the resolved user ID
                UserDefaults.standard.set(userID, forKey: userIDKey)
                print("✅ Username '\(username)' resolved to user ID: \(userID)")
            } else {
                print("❌ Could not resolve username '\(username)' to user ID")
                errorMessage = "Username '\(username)' not found"
            }
        } catch {
            print("❌ Failed to resolve username: \(error)")
            errorMessage = "Failed to resolve username: \(error.localizedDescription)"
        }
    }

    private func getPushToken() async -> String? {
        // Get the actual APNS device token
        return await withCheckedContinuation { continuation in
            DispatchQueue.main.async {
                // Check if we have a stored token from the AppDelegate
                if let tokenData = UserDefaults.standard.data(forKey: "apns_device_token") {
                    let tokenString = tokenData.map { String(format: "%02x", $0) }.joined()
                    print("📱 Retrieved stored APNS token: \(tokenString)")
                    continuation.resume(returning: tokenString)
                } else {
                    print("❌ No APNS device token found")
                    continuation.resume(returning: nil)
                }
            }
        }
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

    @available(iOS 17.2, *)
    private func subscribeToPushToStartTokens() {
        Task {
            for await token in Activity<SleeperLiveActivityAttributes>.pushToStartTokenUpdates {
                print("📱 Received push-to-start token: \(token)")
                await sendTokenToServer(token)
            }
        }
    }

    private func sendTokenToServer(_ token: Data) async {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        let deviceID = getDeviceID()

        print("🚀 Sending push-to-start token to server: \(tokenString)")
        print("📋 COPY THIS TOKEN FOR YOUR TEST SCRIPT:")
        print("📋 ACTIVITY_PUSH_TOKEN=\"\(tokenString)\"")
        print("📋 ===================================")

        guard isConfigured else {
            print("❌ Not configured, skipping token send")
            return
        }

        do {
            // Get the Live Activity push token (if available)
            let pushToken = await getPushToken() ?? ""

            let config = UserConfig(
                userID: userID,
                leagueID: leagueID,
                pushToken: pushToken,
                deviceID: deviceID,
                pushToStartToken: tokenString
            )

            try await apiClient.registerUser(config: config)
            print("✅ Successfully sent push-to-start token to server")
        } catch {
            print("❌ Failed to send push-to-start token: \(error)")
        }
    }
}

// MARK: - Notification Extensions
extension Notification.Name {
    static let autoStartLiveActivity = Notification.Name("autoStartLiveActivity")
    static let autoEndLiveActivity = Notification.Name("autoEndLiveActivity")
}

// MARK: - Data Models
struct UserConfig: Codable {
    let userID: String
    let leagueID: String
    let pushToken: String
    let deviceID: String
    let pushToStartToken: String?

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case leagueID = "league_id"
        case pushToken = "push_token"
        case deviceID = "device_id"
        case pushToStartToken = "push_to_start_token"
    }
}
