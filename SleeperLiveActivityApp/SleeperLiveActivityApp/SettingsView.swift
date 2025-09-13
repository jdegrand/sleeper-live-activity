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
    @State private var tempUserID: String = ""
    @State private var tempLeagueID: String = ""
    @State private var isValidating = false
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Sleeper Configuration")) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("User ID")
                            .font(.headline)
                        TextField("Enter your Sleeper User ID", text: $tempUserID)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                        Text("You can find this in your Sleeper profile URL or by searching your username")
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
                
                Section(header: Text("How to Find Your IDs")) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "1.circle.fill")
                                .foregroundColor(.blue)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("User ID")
                                    .fontWeight(.semibold)
                                Text("Go to your Sleeper profile and look at the URL. Your User ID is the number after '/user/'")
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
                    .disabled(tempUserID.isEmpty || tempLeagueID.isEmpty || isValidating)
                }
            }
        }
        .onAppear {
            tempUserID = viewModel.userID
            tempLeagueID = viewModel.leagueID
        }
        .overlay {
            if isValidating {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                
                VStack(spacing: 16) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Validating credentials...")
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
                // Validate user exists by trying to fetch user info
                _ = try await SleeperAPIClient().getUserInfo(username: tempUserID)
                
                await MainActor.run {
                    viewModel.userID = tempUserID
                    viewModel.leagueID = tempLeagueID
                    viewModel.saveConfiguration()
                    isValidating = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    viewModel.errorMessage = "Failed to validate credentials. Please check your User ID and try again."
                    isValidating = false
                }
            }
        }
    }
}

#Preview {
    SettingsView(viewModel: SleeperViewModel())
}
