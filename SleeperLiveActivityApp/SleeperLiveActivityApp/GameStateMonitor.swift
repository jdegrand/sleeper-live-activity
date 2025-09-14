//
//  GameStateMonitor.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit
import Combine
import Foundation

class GameStateMonitor: ObservableObject {
    @Published var isMonitoring = false
    @Published var activeGames: [NFLGame] = []
    @Published var userActivePlayerCount = 0
    
    private let apiClient = SleeperAPIClient()
    private var cancellables = Set<AnyCancellable>()
    private var monitoringTimer: Timer?
    private let dataCache = DataCache.shared
    
    // Configuration keys
    private let userIDKey = "SleeperUserID"
    private let leagueIDKey = "SleeperLeagueID"
    
    func startMonitoring() {
        guard !isMonitoring else { return }
        
        isMonitoring = true
        
        // Start periodic monitoring every 5 minutes
        monitoringTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { _ in
            Task {
                await self.checkGameStates()
            }
        }
        
        // Initial check
        Task {
            await checkGameStates()
        }
    }
    
    func stopMonitoring() {
        isMonitoring = false
        monitoringTimer?.invalidate()
        monitoringTimer = nil
    }
    
    @MainActor
    private func checkGameStates() async {
        guard let userID = UserDefaults.standard.string(forKey: userIDKey),
              let leagueID = UserDefaults.standard.string(forKey: leagueIDKey),
              !userID.isEmpty, !leagueID.isEmpty else {
            return
        }
        
        do {
            // Get NFL state
            let nflState = try await apiClient.getNFLState()
            let currentWeek = nflState["week"] as? Int ?? 1
            
            // Get user's roster
            let rosters = try await apiClient.getLeagueRosters(leagueID: leagueID)
            guard let userRoster = rosters.first(where: { $0["owner_id"] as? String == userID }),
                  let starters = userRoster["starters"] as? [String] else {
                return
            }
            
            // Get NFL players to map player IDs to teams
            let players = try await apiClient.getNFLPlayers()
            
            // Check which of user's starters have active games
            var activePlayerCount = 0
            var currentActiveGames: [NFLGame] = []
            
            for playerID in starters {
                if let playerData = players[playerID] as? [String: Any],
                   let team = playerData["team"] as? String {
                    
                    // Check if this team has an active game
                    if let gameInfo = await getGameInfoForTeam(team: team, nflState: nflState) {
                        if gameInfo.status == "in_progress" {
                            activePlayerCount += 1
                            if !currentActiveGames.contains(where: { $0.id == gameInfo.id }) {
                                currentActiveGames.append(gameInfo)
                            }
                        }
                    }
                }
            }
            
            userActivePlayerCount = activePlayerCount
            activeGames = currentActiveGames
            
            // Auto-start Live Activity if players are active and it's not already running
            if activePlayerCount > 0 && !isLiveActivityCurrentlyActive() {
                await autoStartLiveActivity()
            }
            
            // Auto-end Live Activity if no players are active for 30+ minutes
            if activePlayerCount == 0 && isLiveActivityCurrentlyActive() {
                await checkForLiveActivityTimeout()
            }
            
        } catch {
            print("Error checking game states: \(error)")
        }
    }
    
    private func getGameInfoForTeam(team: String, nflState: [String: Any]) async -> NFLGame? {
        // This would parse the NFL state to find games for the specific team
        // For now, return a mock game if team matches common NFL teams
        let nflTeams = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS"]
        
        if nflTeams.contains(team) {
            return NFLGame(
                id: "\(team)_game",
                homeTeam: team,
                awayTeam: "OPP",
                status: "in_progress",
                quarter: "2nd",
                timeRemaining: "8:45"
            )
        }
        
        return nil
    }
    
    private func isLiveActivityCurrentlyActive() -> Bool {
        return Activity<SleeperLiveActivityAttributes>.activities.contains { $0.activityState == .active }
    }
    
    private func autoStartLiveActivity() async {
        // This would trigger the same logic as manual start in SleeperViewModel
        NotificationCenter.default.post(name: .autoStartLiveActivity, object: nil)
    }
    
    private func checkForLiveActivityTimeout() async {
        // Check if it's been 30+ minutes since last active player
        let lastActiveTime = dataCache.getLastActivePlayerTime()
        if let lastTime = lastActiveTime,
           Date().timeIntervalSince(lastTime) > 1800 { // 30 minutes
            NotificationCenter.default.post(name: .autoEndLiveActivity, object: nil)
        } else if lastActiveTime == nil {
            // First time seeing no active players, record the time
            dataCache.setLastActivePlayerTime(Date())
        }
    }
}

// MARK: - Data Models
struct NFLGame: Identifiable, Equatable {
    let id: String
    let homeTeam: String
    let awayTeam: String
    let status: String
    let quarter: String
    let timeRemaining: String
}

// MARK: - Notification Names (defined in SleeperViewModel.swift)

// MARK: - Data Cache
class DataCache {
    static let shared = DataCache()
    private init() {}
    
    private let lastActivePlayerTimeKey = "lastActivePlayerTime"
    
    func setLastActivePlayerTime(_ date: Date) {
        UserDefaults.standard.set(date, forKey: lastActivePlayerTimeKey)
    }
    
    func getLastActivePlayerTime() -> Date? {
        return UserDefaults.standard.object(forKey: lastActivePlayerTimeKey) as? Date
    }
    
    func clearLastActivePlayerTime() {
        UserDefaults.standard.removeObject(forKey: lastActivePlayerTimeKey)
    }
}
