//
//  SleeperLiveActivityAppWidgetLiveActivity.swift
//  SleeperLiveActivityAppWidget
//
//  Created by Joey DeGrand on 9/14/25.
//

import ActivityKit
import WidgetKit
import SwiftUI

// SleeperLiveActivityAttributes and SleeperWidgetView are now defined in shared files

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
                        Text("Updated \(formatTime(context.state.lastUpdate))")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            } compactLeading: {
                HStack {
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
                    Text("\(context.state.totalPoints, specifier: "%.2f")")
                        .font(.caption)
                        .fontWeight(.semibold)
                }
            } compactTrailing: {
                HStack {
                    Text("\(context.state.opponentPoints, specifier: "%.2f")")
                        .font(.caption)
                        .fontWeight(.semibold)
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
            } minimal: {
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
            }
            .widgetURL(URL(string: "sleeperapp://"))
            .keylineTint(Color.blue)
        }
    }
}

#Preview("Notification", as: .content, using: SleeperLiveActivityAttributes.preview) {
   SleeperLiveActivityAppWidgetLiveActivity()
} contentStates: {
    SleeperLiveActivityAttributes.ContentState.active
    SleeperLiveActivityAttributes.ContentState.final
}

