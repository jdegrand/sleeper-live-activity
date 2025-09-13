//
//  SleeperLiveActivityAttributes.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import ActivityKit
import SwiftUI
import WidgetKit

struct SleeperLiveActivityAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var totalPoints: Double
        var activePlayersCount: Int
        var teamName: String
        var opponentPoints: Double
        var gameStatus: String
        var lastUpdate: Date
    }
    
    var userID: String
    var leagueID: String
}


private let timeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter
}()

