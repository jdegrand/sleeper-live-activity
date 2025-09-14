//
//  SettingsView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI

struct SettingsView: View {
    @ObservedObject var viewModel: SleeperViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var tempUsername: String = ""
    @State private var tempLeagueID: String = ""
    @State private var isValidating = false
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Sleeper Configuration")) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Username")
                            .font(.headline)
                        TextField("Enter your Sleeper username", text: $tempUsername)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .autocapitalization(.none)
                            .autocorrectionDisabled()
                        Text("This is your @username displayed in Sleeper")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("League ID")
                            .font(.headline)
                        TextField("Enter your League ID", text: $tempLeagueID)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                        Text("Found in your league's URL or settings")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)
                }
                
                Section(header: Text("How to Find Your Information")) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "1.circle.fill")
                                .foregroundColor(.blue)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Username")
                                    .fontWeight(.semibold)
                                Text("This is your @username shown in your Sleeper profile and when other users mention you")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "2.circle.fill")
                                .foregroundColor(.blue)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("League ID")
                                    .fontWeight(.semibold)
                                Text("In your league, go to League Settings. The League ID is shown at the bottom or in the URL")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
                
                Section(header: Text("Live Activity Settings")) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Image(systemName: "bell.fill")
                                .foregroundColor(.orange)
                            Text("Push Notifications")
                                .fontWeight(.medium)
                        }
                        Text("Live Activities require push notifications to be enabled for real-time updates")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Image(systemName: "lock.shield.fill")
                                .foregroundColor(.green)
                            Text("Privacy")
                                .fontWeight(.medium)
                        }
                        Text("Your data is only used to fetch fantasy scores and is not stored permanently")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        saveSettings()
                    }
                    .disabled(tempUsername.isEmpty || tempLeagueID.isEmpty || isValidating)
                }
            }
        }
        .onAppear {
            tempUsername = viewModel.username
            tempLeagueID = viewModel.leagueID
        }
        .overlay {
            if isValidating {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                
                VStack(spacing: 16) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Validating username...")
                        .font(.headline)
                }
                .padding(24)
                .background(Color(.systemBackground))
                .cornerRadius(12)
                .shadow(radius: 8)
            }
        }
    }
    
    private func saveSettings() {
        isValidating = true

        Task {
            do {
                // Validate username exists by trying to fetch user info
                _ = try await SleeperAPIClient().getUserByUsername(username: tempUsername)

                await MainActor.run {
                    viewModel.username = tempUsername
                    viewModel.leagueID = tempLeagueID
                    viewModel.saveConfiguration()
                    isValidating = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    viewModel.errorMessage = "Failed to validate username. Please check your username and try again."
                    isValidating = false
                }
            }
        }
    }
}

#Preview {
    SettingsView(viewModel: SleeperViewModel())
}
