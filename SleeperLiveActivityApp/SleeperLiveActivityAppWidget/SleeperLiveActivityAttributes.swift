//
//  SleeperLiveActivityAttributes.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import ActivityKit
import SwiftUI
import WidgetKit

public struct SleeperLiveActivityAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        public var totalPoints: Double
        public var activePlayersCount: Int
        public var teamName: String
        public var opponentPoints: Double
        public var opponentTeamName: String
        public var userAvatarURL: String
        public var opponentAvatarURL: String
        public var userAvatarData: Data?
        public var opponentAvatarData: Data?
        public var gameStatus: String
        public var lastUpdate: Date

        public init(totalPoints: Double, activePlayersCount: Int, teamName: String, opponentPoints: Double, opponentTeamName: String, userAvatarURL: String, opponentAvatarURL: String, userAvatarData: Data? = nil, opponentAvatarData: Data? = nil, gameStatus: String, lastUpdate: Date) {
            self.totalPoints = totalPoints
            self.activePlayersCount = activePlayersCount
            self.teamName = teamName
            self.opponentPoints = opponentPoints
            self.opponentTeamName = opponentTeamName
            self.userAvatarURL = userAvatarURL
            self.opponentAvatarURL = opponentAvatarURL
            self.userAvatarData = userAvatarData
            self.opponentAvatarData = opponentAvatarData
            self.gameStatus = gameStatus
            self.lastUpdate = lastUpdate
        }
    }

    public var userID: String
    public var leagueID: String

    public init(userID: String, leagueID: String) {
        self.userID = userID
        self.leagueID = leagueID
    }
}


// Widget view is now defined in the widget extension
// Import SleeperLiveActivityAppWidgetExtension to use the shared component

