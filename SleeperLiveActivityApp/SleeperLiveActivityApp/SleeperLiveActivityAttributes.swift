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
        var opponentTeamName: String
        var userAvatarURL: String
        var opponentAvatarURL: String
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

// MARK: - Shared Widget View Component
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

