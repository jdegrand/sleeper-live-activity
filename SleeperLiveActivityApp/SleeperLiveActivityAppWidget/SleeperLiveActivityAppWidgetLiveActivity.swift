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
            leagueName: "Fantasy Football",
            userID: "cc12ec49965eb7856f84d71cf85306af",
            opponentUserID: "446042a71cea6b2353e5a7ad7d2a259d",
            gameStatus: "Live",
            lastUpdate: Date(),
            message: "🔥 Josh Allen +6.2 pts",
            userProjectedScore: 92.3,
            opponentProjectedScore: 88.7
        )
     }

     fileprivate static var final: SleeperLiveActivityAttributes.ContentState {
         SleeperLiveActivityAttributes.ContentState(
             totalPoints: 124.20,
             activePlayersCount: 0,
             teamName: "Team 1",
             opponentPoints: 108.60,
             opponentTeamName: "Team 2",
             leagueName: "Fantasy Football",
             userID: "cc12ec49965eb7856f84d71cf85306af",
             opponentUserID: "446042a71cea6b2353e5a7ad7d2a259d",
             gameStatus: "Final",
             lastUpdate: Date(),
             message: "⚡ Travis Kelce +8.4 pts",
             userProjectedScore: 124.2,
             opponentProjectedScore: 112.1
         )
     }
}

struct SleeperLiveActivityAppWidgetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SleeperLiveActivityAttributes.self) { context in
            SleeperWidgetView(state: context.state, leagueName: context.state.leagueName)
                .activityBackgroundTint(Color.clear)
                .activitySystemActionForegroundColor(Color.primary)

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI goes here.  Compose the expanded UI through
                // various regions, like leading/trailing/center/bottom
                DynamicIslandExpandedRegion(.leading) {
                    VStack(spacing: 6) {
                        SharedAvatarView(
                            userID: context.state.userID,
                            placeholderColor: .blue,
                            size: 60
                        )
                        Text(context.state.teamName)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                        Text("\(context.state.totalPoints, specifier: "%.2f")")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                    }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(spacing: 6) {
                        SharedAvatarView(
                            userID: context.state.opponentUserID,
                            placeholderColor: .red,
                            size: 60
                        )
                        Text(context.state.opponentTeamName)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                        Text("\(context.state.opponentPoints, specifier: "%.2f")")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.red)
                    }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 2) {
                        Text("vs")
                            .font(.title)
                            .foregroundColor(.secondary)
                        Image(systemName: "football.fill")
                            .foregroundColor(.orange)
                            .font(.title2)
                    }.frame(maxHeight: .infinity, alignment: .center)
                    if let message = context.state.message {
                        SharedMessageView(
                            message: message,
                            lastUpdate: context.state.lastUpdate,
                            width: 180,
                            alignment: .center,
                            shouldRemoveEmoji: true
                        )
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    
                }
            } compactLeading: {
                HStack {
                    SharedAvatarView(
                        userID: context.state.userID,
                        placeholderColor: .blue,
                        size: 24
                    )
                    Text("\(context.state.totalPoints, specifier: "%.2f")")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.blue)
                }
            } compactTrailing: {
                HStack {
                    Text("\(context.state.opponentPoints, specifier: "%.2f")")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.red)
                    SharedAvatarView(
                        userID: context.state.opponentUserID,
                        placeholderColor: .red,
                        size: 24
                    )
                }
            } minimal: {
                SharedAvatarView(
                    userID: context.state.userID,
                    placeholderColor: .blue,
                    size: 24
                )
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

