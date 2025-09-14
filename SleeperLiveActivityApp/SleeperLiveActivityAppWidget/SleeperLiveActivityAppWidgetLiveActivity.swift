//
//  SleeperLiveActivityAppWidgetLiveActivity.swift
//  SleeperLiveActivityAppWidget
//
//  Created by Joey DeGrand on 9/14/25.
//

import ActivityKit
import WidgetKit
import SwiftUI

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

struct SleeperLiveActivityAppWidgetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SleeperLiveActivityAttributes.self) { context in
            // Lock screen/banner UI goes here
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "sportscourt.fill")
                        .foregroundColor(.blue)
                        .font(.title3)

                    Text("Fantasy Football")
                        .font(.headline)
                        .fontWeight(.semibold)

                    Spacer()

                    Text(context.state.gameStatus)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.orange)
                }

                HStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Your Score")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text("\(context.state.totalPoints, specifier: "%.1f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                    }

                    Spacer()

                    VStack(alignment: .center, spacing: 4) {
                        Text("Active Players")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text("\(context.state.activePlayersCount)")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.green)
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: 4) {
                        Text("Opponent")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text("\(context.state.opponentPoints, specifier: "%.1f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }
                }

                HStack {
                    Image(systemName: "clock")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("Updated \(context.state.lastUpdate, formatter: timeFormatter)")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }
            }
            .padding()
            .activityBackgroundTint(Color.black.opacity(0.1))
            .activitySystemActionForegroundColor(Color.white)

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI goes here.  Compose the expanded UI through
                // various regions, like leading/trailing/center/bottom
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading) {
                        Text("Your Score")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(context.state.totalPoints, specifier: "%.1f")")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing) {
                        Text("Opponent")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(context.state.opponentPoints, specifier: "%.1f")")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack {
                        Text("Active Players")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(context.state.activePlayersCount)")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.green)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        Image(systemName: "sportscourt.fill")
                            .foregroundColor(.blue)
                        Text("Fantasy Football - \(context.state.gameStatus)")
                            .font(.caption)
                        Spacer()
                        Text("Updated \(context.state.lastUpdate, formatter: timeFormatter)")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            } compactLeading: {
                Image(systemName: "sportscourt.fill")
                    .foregroundColor(.blue)
            } compactTrailing: {
                VStack {
                    Text("\(context.state.totalPoints, specifier: "%.0f")")
                        .font(.caption)
                        .fontWeight(.semibold)
                    Text("pts")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            } minimal: {
                Image(systemName: "sportscourt.fill")
                    .foregroundColor(.blue)
            }
            .widgetURL(URL(string: "sleeperapp://"))
            .keylineTint(Color.blue)
        }
    }
}

private let timeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter
}()

extension SleeperLiveActivityAttributes {
    fileprivate static var preview: SleeperLiveActivityAttributes {
        SleeperLiveActivityAttributes(userID: "12345", leagueID: "67890")
    }
}

extension SleeperLiveActivityAttributes.ContentState {
    fileprivate static var active: SleeperLiveActivityAttributes.ContentState {
        SleeperLiveActivityAttributes.ContentState(
            totalPoints: 87.5,
            activePlayersCount: 3,
            teamName: "Your Team",
            opponentPoints: 72.8,
            gameStatus: "Live",
            lastUpdate: Date()
        )
     }

     fileprivate static var final: SleeperLiveActivityAttributes.ContentState {
         SleeperLiveActivityAttributes.ContentState(
             totalPoints: 124.2,
             activePlayersCount: 0,
             teamName: "Your Team",
             opponentPoints: 108.6,
             gameStatus: "Final",
             lastUpdate: Date()
         )
     }
}

#Preview("Notification", as: .content, using: SleeperLiveActivityAttributes.preview) {
   SleeperLiveActivityAppWidgetLiveActivity()
} contentStates: {
    SleeperLiveActivityAttributes.ContentState.active
    SleeperLiveActivityAttributes.ContentState.final
}
