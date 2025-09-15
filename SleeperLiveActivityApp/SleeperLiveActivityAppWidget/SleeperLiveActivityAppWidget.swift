//
//  SleeperLiveActivityAppWidget.swift
//  SleeperLiveActivityAppWidget
//
//  Created by Joey DeGrand on 9/14/25.
//

import WidgetKit
import SwiftUI
import ActivityKit

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> SimpleEntry {
        SimpleEntry(
            date: Date(),
            state: SleeperLiveActivityAttributes.ContentState(
                totalPoints: 0,
                activePlayersCount: 0,
                teamName: "My Team",
                opponentPoints: 0,
                opponentTeamName: "Opponent",
                userAvatarURL: "",
                opponentAvatarURL: "",
                gameStatus: "Pregame",
                lastUpdate: Date()
            )
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (SimpleEntry) -> ()) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        let entry = placeholder(in: context)
        let timeline = Timeline(entries: [entry], policy: .atEnd)
        completion(timeline)
    }
}

struct SimpleEntry: TimelineEntry {
    let date: Date
    let state: SleeperLiveActivityAttributes.ContentState
}

struct SleeperLiveActivityAppWidgetEntryView: View {
    var entry: Provider.Entry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Team vs Opponent Header
            HStack {
                VStack(alignment: .leading) {
                    Text(entry.state.teamName)
                        .font(.headline)
                    Text(String(format: "%.1f", entry.state.totalPoints))
                        .font(.title)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text(entry.state.opponentTeamName)
                        .font(.headline)
                    Text(String(format: "%.1f", entry.state.opponentPoints))
                        .font(.title)
                        .fontWeight(.bold)
                }
            }
            
            // Game status and last update
            VStack(alignment: .leading, spacing: 4) {
                Text(entry.state.gameStatus)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text("Last update: \(entry.state.lastUpdate, style: .time)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
    }
}

struct SleeperLiveActivityAppWidget: Widget {
    let kind: String = "SleeperLiveActivityAppWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            if #available(iOS 17.0, *) {
                SleeperLiveActivityAppWidgetEntryView(entry: entry)
                    .containerBackground(.fill.tertiary, for: .widget)
            } else {
                SleeperLiveActivityAppWidgetEntryView(entry: entry)
                    .padding()
                    .background()
            }
        }
        .configurationDisplayName("Sleeper Live Activity")
        .description("Track your fantasy football team's live scores.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

#Preview(as: .systemSmall) {
    SleeperLiveActivityAppWidget()
} timeline: {
    SimpleEntry(
        date: .now,
        state: SleeperLiveActivityAttributes.ContentState(
            totalPoints: 87.5,
            activePlayersCount: 3,
            teamName: "Team Swift",
            opponentPoints: 92.3,
            opponentTeamName: "Team Kotlin",
            userAvatarURL: "",
            opponentAvatarURL: "",
            gameStatus: "Q3 8:24",
            lastUpdate: Date()
        )
    )
}
