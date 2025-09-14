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
        var opponentTeamName: String
        var userAvatarURL: String
        var opponentAvatarURL: String
        var gameStatus: String
        var lastUpdate: Date
    }

    var userID: String
    var leagueID: String
}


// MARK: - Shared Widget View Component (identical to main app)
struct SleeperWidgetView: View {
    let state: SleeperLiveActivityAttributes.ContentState

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "football.fill")
                    .foregroundColor(.orange)
                    .font(.title3)

                Text("Fantasy Football")
                    .font(.headline)
                    .fontWeight(.semibold)

                Spacer()

                Text(state.gameStatus)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.orange)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Color.orange.opacity(0.15))
                    .cornerRadius(8)
            }

            HStack(spacing: 20) {
                // User team (left side)
                HStack(spacing: 8) {
                    AsyncImage(url: URL(string: state.userAvatarURL)) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Circle()
                            .fill(Color.blue.opacity(0.3))
                            .overlay(
                                Image(systemName: "person.fill")
                                    .foregroundColor(.blue)
                                    .font(.caption)
                            )
                    }
                    .frame(width: 32, height: 32)
                    .clipShape(Circle())

                    VStack(alignment: .leading, spacing: 4) {
                        Text(state.teamName)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                        Text("\(state.totalPoints, specifier: "%.2f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                    }
                }

                Spacer()

                // Opponent team (right side)
                HStack(spacing: 8) {
                    VStack(alignment: .trailing, spacing: 4) {
                        Text(state.opponentTeamName)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                        Text("\(state.opponentPoints, specifier: "%.2f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }

                    AsyncImage(url: URL(string: state.opponentAvatarURL)) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Circle()
                            .fill(Color.red.opacity(0.3))
                            .overlay(
                                Image(systemName: "person.fill")
                                    .foregroundColor(.red)
                                    .font(.caption)
                            )
                    }
                    .frame(width: 32, height: 32)
                    .clipShape(Circle())
                }
            }

            HStack {
                Image(systemName: "clock")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text("Updated \(state.lastUpdate, formatter: timeFormatter)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Spacer()
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(.systemBackground))
                .shadow(color: .black.opacity(0.1), radius: 2, x: 0, y: 1)
        )
    }
}

private let timeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter
}()

struct SleeperLiveActivityAppWidgetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SleeperLiveActivityAttributes.self) { context in
            SleeperWidgetView(state: context.state)
                .activityBackgroundTint(Color.clear)
                .activitySystemActionForegroundColor(Color.primary)

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI goes here.  Compose the expanded UI through
                // various regions, like leading/trailing/center/bottom
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 6) {
                        AsyncImage(url: URL(string: context.state.userAvatarURL)) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Circle()
                                .fill(Color.blue.opacity(0.3))
                                .overlay(
                                    Image(systemName: "person.fill")
                                        .foregroundColor(.blue)
                                        .font(.caption2)
                                )
                        }
                        .frame(width: 24, height: 24)
                        .clipShape(Circle())

                        VStack(alignment: .leading) {
                            Text(context.state.teamName)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                            Text("\(context.state.totalPoints, specifier: "%.2f")")
                                .font(.title3)
                                .fontWeight(.bold)
                                .foregroundColor(.blue)
                        }
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    HStack(spacing: 6) {
                        VStack(alignment: .trailing) {
                            Text(context.state.opponentTeamName)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                            Text("\(context.state.opponentPoints, specifier: "%.2f")")
                                .font(.title3)
                                .fontWeight(.bold)
                                .foregroundColor(.red)
                        }

                        AsyncImage(url: URL(string: context.state.opponentAvatarURL)) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Circle()
                                .fill(Color.red.opacity(0.3))
                                .overlay(
                                    Image(systemName: "person.fill")
                                        .foregroundColor(.red)
                                        .font(.caption2)
                                )
                        }
                        .frame(width: 24, height: 24)
                        .clipShape(Circle())
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack {
                        Text("vs")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Image(systemName: "football.fill")
                            .foregroundColor(.orange)
                            .font(.title2)
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
                    Text("\(context.state.totalPoints, specifier: "%.2f")")
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

extension SleeperLiveActivityAttributes {
    fileprivate static var preview: SleeperLiveActivityAttributes {
        SleeperLiveActivityAttributes(userID: "12345", leagueID: "67890")
    }
}

extension SleeperLiveActivityAttributes.ContentState {
    fileprivate static var active: SleeperLiveActivityAttributes.ContentState {
        SleeperLiveActivityAttributes.ContentState(
            totalPoints: 87.50,
            activePlayersCount: 3,
            teamName: "Team 1",
            opponentPoints: 72.80,
            opponentTeamName: "Team 2",
            userAvatarURL: "https://sleepercdn.com/avatars/thumbs/cc12ec49965eb7856f84d71cf85306af",
            opponentAvatarURL: "https://sleepercdn.com/avatars/thumbs/446042a71cea6b2353e5a7ad7d2a259d",
            gameStatus: "Live",
            lastUpdate: Date()
        )
     }

     fileprivate static var final: SleeperLiveActivityAttributes.ContentState {
         SleeperLiveActivityAttributes.ContentState(
             totalPoints: 124.20,
             activePlayersCount: 0,
             teamName: "Team 1",
             opponentPoints: 108.60,
             opponentTeamName: "Team 2",
             userAvatarURL: "https://sleepercdn.com/avatars/thumbs/cc12ec49965eb7856f84d71cf85306af",
             opponentAvatarURL: "https://sleepercdn.com/avatars/thumbs/446042a71cea6b2353e5a7ad7d2a259d",
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
