//
//  SleeperLiveActivityWidget.swift
//  SleeperLiveActivityWidget
//
//  Created by Joey DeGrand on 9/13/25.
//

import ActivityKit
import WidgetKit
import SwiftUI

@available(iOS 16.1, *)
struct SleeperLiveActivityWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SleeperLiveActivityAttributes.self) { context in
            // Lock Screen/Banner UI
            LockScreenLiveActivityView(context: context)
        } dynamicIsland: { context in
            // Dynamic Island UI
            DynamicIsland {
                // Expanded UI
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Your Team")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(context.state.totalPoints, specifier: "%.1f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.primary)
                    }
                }
                
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing, spacing: 4) {
                        Text("Opponent")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(context.state.opponentPoints, specifier: "%.1f")")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.primary)
                    }
                }
                
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 4) {
                        Image(systemName: "sportscourt.fill")
                            .font(.title3)
                            .foregroundColor(.blue)
                        Text("\(context.state.activePlayersCount) Active")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        Text(context.state.gameStatus)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        Text("Updated \(context.state.lastUpdate, formatter: timeFormatter)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.horizontal)
                }
            } compactLeading: {
                // Compact leading (left side of notch)
                Image(systemName: "sportscourt.fill")
                    .font(.caption)
                    .foregroundColor(.blue)
            } compactTrailing: {
                // Compact trailing (right side of notch)
                Text("\(context.state.totalPoints, specifier: "%.0f")")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
            } minimal: {
                // Minimal (when multiple activities are running)
                Image(systemName: "sportscourt.fill")
                    .font(.caption)
                    .foregroundColor(.blue)
            }
        }
    }
}

struct LockScreenLiveActivityView: View {
    let context: ActivityViewContext<SleeperLiveActivityAttributes>
    
    var body: some View {
        VStack(spacing: 12) {
            // Header
            HStack {
                Image(systemName: "sportscourt.fill")
                    .font(.title2)
                    .foregroundColor(.blue)
                
                Text("Fantasy Football")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Text(context.state.gameStatus)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.blue.opacity(0.2))
                    .cornerRadius(8)
            }
            
            // Score Display
            HStack(spacing: 20) {
                // Your Team
                VStack(spacing: 4) {
                    Text("Your Team")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(context.state.totalPoints, specifier: "%.1f")")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                }
                .frame(maxWidth: .infinity)
                
                // VS Divider
                VStack {
                    Text("VS")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                    
                    Rectangle()
                        .fill(Color.secondary.opacity(0.3))
                        .frame(width: 1, height: 30)
                }
                
                // Opponent
                VStack(spacing: 4) {
                    Text("Opponent")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(context.state.opponentPoints, specifier: "%.1f")")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                }
                .frame(maxWidth: .infinity)
            }
            
            // Bottom Info
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "person.2.fill")
                        .font(.caption)
                        .foregroundColor(.blue)
                    Text("\(context.state.activePlayersCount) Active Players")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Text("Updated \(context.state.lastUpdate, formatter: timeFormatter)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(16)
        .background(Color(.systemBackground))
        .cornerRadius(12)
    }
}

private let timeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter
}()

@available(iOS 16.1, *)
@main
struct SleeperLiveActivityWidgetBundle: WidgetBundle {
    var body: some Widget {
        SleeperLiveActivityWidget()
    }
}
