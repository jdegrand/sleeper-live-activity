//
//  SharedWidgetView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/14/25.
//  Shared between main app and widget extension

import SwiftUI
import ActivityKit

// MARK: - Shared Widget View Component (Used by both app and Live Activity)
public struct SleeperWidgetView: View {
    let state: SleeperLiveActivityAttributes.ContentState
    let leagueName: String

    public init(state: SleeperLiveActivityAttributes.ContentState, leagueName: String = "Fantasy Football") {
        self.state = state
        self.leagueName = leagueName
    }

    public var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "football.fill")
                    .foregroundColor(.orange)
                    .font(.title3)

                Text(leagueName)
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
                    SharedAvatarView(
                        userID: state.userID,
                        placeholderColor: .blue,
                        size: 32
                    )

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

                    SharedAvatarView(
                        userID: state.opponentUserID,
                        placeholderColor: .red,
                        size: 32
                    )
                }
            }

            HStack {
                Image(systemName: "clock")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text("Updated \(formatTime(state.lastUpdate))")
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

// MARK: - Helper Functions
public func checkFileExists(_ path: String?, _ label: String) -> Bool {
    guard let path = path, !path.isEmpty else {
        print("🛑 \(label) path is nil or empty")
        return false
    }
    
    let fileManager = FileManager.default
    let fileExists = fileManager.fileExists(atPath: path)
    print("\(label) file exists: \(fileExists) at path: \(path)")
    return fileExists
}

public func formatTime(_ date: Date) -> String {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter.string(from: date)
}