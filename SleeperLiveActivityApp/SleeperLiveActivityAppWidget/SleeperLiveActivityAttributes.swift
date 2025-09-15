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
        public var leagueName: String
        public var userAvatarURL: String
        public var opponentAvatarURL: String
        public var userAvatarLocalURL: String?
        public var opponentAvatarLocalURL: String?
        public var gameStatus: String
        public var lastUpdate: Date

        public init(totalPoints: Double, activePlayersCount: Int, teamName: String, opponentPoints: Double, opponentTeamName: String, leagueName: String = "Fantasy Football", userAvatarURL: String, opponentAvatarURL: String, userAvatarLocalURL: String? = nil, opponentAvatarLocalURL: String? = nil, gameStatus: String, lastUpdate: Date) {
            self.totalPoints = totalPoints
            self.activePlayersCount = activePlayersCount
            self.teamName = teamName
            self.opponentPoints = opponentPoints
            self.opponentTeamName = opponentTeamName
            self.leagueName = leagueName
            self.userAvatarURL = userAvatarURL
            self.opponentAvatarURL = opponentAvatarURL
            self.userAvatarLocalURL = userAvatarLocalURL
            self.opponentAvatarLocalURL = opponentAvatarLocalURL
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

