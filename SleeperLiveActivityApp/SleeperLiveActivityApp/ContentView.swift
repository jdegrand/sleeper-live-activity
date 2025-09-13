//
//  ContentView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit

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
                    
                    Text("Fantasy Football Live Scores")
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
                            HStack {
                                Image(systemName: "person.circle.fill")
                                    .foregroundColor(.green)
                                Text("User ID: \(viewModel.userID)")
                                    .fontWeight(.medium)
                            }
                            
                            HStack {
                                Image(systemName: "trophy.circle.fill")
                                    .foregroundColor(.orange)
                                Text("League ID: \(viewModel.leagueID)")
                                    .fontWeight(.medium)
                            }
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                        
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
                                if viewModel.isLiveActivityActive {
                                    viewModel.stopLiveActivity()
                                } else {
                                    viewModel.startLiveActivity()
                                }
                            }) {
                                HStack {
                                    Image(systemName: viewModel.isLiveActivityActive ? "stop.circle.fill" : "play.circle.fill")
                                    Text(viewModel.isLiveActivityActive ? "Stop Live Activity" : "Start Live Activity")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(viewModel.isLiveActivityActive ? .red : .blue)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }
                            
                            Button("Refresh Data") {
                                viewModel.refreshData()
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color(.systemGray5))
                            .cornerRadius(12)
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
                            
                            Text("Configure your Sleeper User ID and League ID to get started")
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
            viewModel.loadConfiguration()
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
