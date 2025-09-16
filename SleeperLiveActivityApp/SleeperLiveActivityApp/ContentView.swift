//
//  ContentView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit
import WidgetKit

struct ContentView: View {
    @StateObject private var viewModel = SleeperViewModel()
    @State private var showingSettings = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Header
                VStack {
                    Image(systemName: "sportscourt.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)
                    
                    Text("Sleeper Live Activity")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("\(viewModel.leagueName) Live Scores")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top)
                
                Spacer()
                
                // Status Section
                VStack(spacing: 16) {
                    if viewModel.isConfigured {
                        // User Info
                        VStack(alignment: .leading, spacing: 8) {
                            // Widget Preview - using the same component as Live Activity
                            VStack(spacing: 12) {
                                Text("Live Activity Preview")
                                    .font(.headline)

                                SleeperWidgetView(
                                    state: SleeperLiveActivityAttributes.ContentState(
                                        totalPoints: viewModel.currentPoints,
                                        activePlayersCount: viewModel.activePlayers,
                                        teamName: viewModel.teamName,
                                        opponentPoints: viewModel.opponentPoints,
                                        opponentTeamName: viewModel.opponentTeamName,
                                        leagueName: viewModel.leagueName,
                                        userAvatarURL: viewModel.userAvatarURL,
                                        opponentAvatarURL: viewModel.opponentAvatarURL,
                                        gameStatus: viewModel.gameStatus,
                                        lastUpdate: viewModel.lastUpdate
                                    ),
                                    leagueName: viewModel.leagueName
                                )
                            }
                            
                            // Live Activity Status
                            VStack(spacing: 12) {
                                HStack {
                                    Circle()
                                        .fill(viewModel.isLiveActivityActive ? .green : .red)
                                        .frame(width: 12, height: 12)
                                    
                                    Text(viewModel.isLiveActivityActive ? "Live Activity Active" : "Live Activity Inactive")
                                        .fontWeight(.medium)
                                    
                                    Spacer()
                                }
                                
                                if viewModel.isLiveActivityActive {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("Points: \(viewModel.currentPoints, specifier: "%.1f")")
                                        Text("Active Players: \(viewModel.activePlayers)")
                                        Text("Last Update: \(viewModel.lastUpdate, formatter: timeFormatter)")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(12)
                            
                            // Action Buttons
                            VStack(spacing: 12) {
                                Button(action: {
                                    Task {
                                        if viewModel.isLiveActivityActive {
                                            await viewModel.stopLiveActivity()
                                        } else {
                                            await viewModel.startLiveActivity()
                                        }
                                    }
                                }) {
                                    HStack {
                                        Image(systemName: viewModel.isLiveActivityActive ? "stop.circle.fill" : "play.circle.fill")
                                        Text(viewModel.isLiveActivityActive ? "Stop Live Activity" : "Start Live Activity")
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(viewModel.isLiveActivityActive ? Color.red : Color.blue)
                                    .foregroundColor(.white)
                                    .cornerRadius(10)
                                }
                                .padding(.horizontal)
                                .disabled(!viewModel.isConfigured)
                                
                                Button("Refresh Data") {
                                    viewModel.refreshData()
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color(.systemGray5))
                                .cornerRadius(12)
                            }
                        }
                    } else {
                        // Setup Required
                        VStack(spacing: 16) {
                            Image(systemName: "gear")
                                .font(.system(size: 40))
                                .foregroundColor(.orange)
                            
                            Text("Setup Required")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text("Configure your Sleeper Username and League ID to get started")
                                .multilineTextAlignment(.center)
                                .foregroundColor(.secondary)
                            
                            Button("Configure Settings") {
                                showingSettings = true
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(.blue)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                        }
                    }
                }
                .padding(.horizontal)
                
                Spacer()
                
                // Footer
                Text("Live Activity will automatically start when your players are active in games")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .padding(.bottom)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Settings") {
                        showingSettings = true
                    }
                }
            }
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView(viewModel: viewModel)
        }
        .onAppear {
            // Configuration already loaded in ViewModel init
        }
        .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("OK") {
                viewModel.errorMessage = nil
            }
        } message: {
            if let errorMessage = viewModel.errorMessage {
                Text(errorMessage)
            }
        }
    }
}

private let timeFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.timeStyle = .short
    return formatter
}()

#Preview {
    ContentView()
}
