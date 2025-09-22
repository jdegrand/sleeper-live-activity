//
//  OnboardingView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/16/25.
//

import SwiftUI
import UserNotifications
import ActivityKit
import Foundation

enum PermissionState {
    case unset
    case granted
    case denied
}

struct OnboardingView: View {
    @Binding var isCompleted: Bool
    @State private var currentStep = 0
    @State private var notificationPermissionGranted = false
    @State private var notificationPermissionDenied = false
    @State private var liveActivityPermissionGranted = false
    @State private var liveActivityPermissionDenied = false
    @State private var networkPermissionState: PermissionState = .unset
    @State private var networkTestAttempts = 0
    @State private var isCheckingPermissions = false

    private var totalSteps: Int {
        #if DEBUG
        return 4 // Debug: Welcome, Notifications, Network, Live Activities
        #else
        return 3 // Release: Welcome, Notifications, Live Activities (skip network step)
        #endif
    }

    var body: some View {
        NavigationView {
            VStack(spacing: 24) {
                // Progress indicator
                HStack {
                    ForEach(0..<totalSteps, id: \.self) { step in
                        Circle()
                            .fill(step <= currentStep ? .blue : .gray.opacity(0.3))
                            .frame(width: 12, height: 12)

                        if step < totalSteps - 1 {
                            Rectangle()
                                .fill(step < currentStep ? .blue : .gray.opacity(0.3))
                                .frame(height: 2)
                        }
                    }
                }
                .padding(.horizontal)

                Spacer()

                // Content based on current step
                Group {
                    switch currentStep {
                    case 0:
                        welcomeStep
                    case 1:
                        notificationPermissionStep
                    case 2:
                        #if DEBUG
                        networkPermissionStep
                        #else
                        liveActivityPermissionStep
                        #endif
                    case 3:
                        #if DEBUG
                        liveActivityPermissionStep
                        #else
                        EmptyView()
                        #endif
                    default:
                        EmptyView()
                    }
                }

                Spacer()

                // Navigation buttons
                HStack(spacing: 16) {
                    if currentStep > 0 {
                        Button("Back") {
                            withAnimation {
                                currentStep -= 1
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 50)
                        .background(Color(.systemGray5))
                        .foregroundColor(.primary)
                        .cornerRadius(12)
                    }

                    Button(action: nextAction) {
                        Text(nextButtonTitle)
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: 50)
                    }
                    .background(canProceed ? .blue : .gray)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                    .disabled(!canProceed)
                }
                .padding(.horizontal)
            }
            .padding()
            .navigationTitle("Setup")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear {
            checkInitialPermissions()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            // Refresh permissions when app becomes active (e.g., returning from Settings)
            checkInitialPermissions()

            // Also verify network permission if it was previously denied
            if networkPermissionState == .denied {
                verifyNetworkPermissionAfterSettings()
            }
        }
    }

    private var welcomeStep: some View {
        VStack(spacing: 24) {
            Image(systemName: "sportscourt.fill")
                .font(.system(size: 80))
                .foregroundColor(.blue)

            VStack(spacing: 16) {
                Text("Welcome to Sleeper Live Activity")
                    .font(.title)
                    .fontWeight(.bold)
                    .multilineTextAlignment(.center)

                Text("Get real-time fantasy football updates right on your lock screen and Dynamic Island")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            VStack(alignment: .leading, spacing: 12) {
                PermissionFeatureRow(
                    icon: "bell.fill",
                    title: "Push Notifications",
                    description: "Receive updates when your players score"
                )

                PermissionFeatureRow(
                    icon: "rectangle.stack.badge.play",
                    title: "Live Activities",
                    description: "See live scores on your lock screen"
                )

                PermissionFeatureRow(
                    icon: "network",
                    title: "Local Network",
                    description: "Connect to Sleeper's servers for updates"
                )
            }
        }
    }

    private var notificationPermissionStep: some View {
        VStack(spacing: 24) {
            Image(systemName: "bell.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.blue)

            VStack(spacing: 16) {
                Text("Enable Notifications")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("We need permission to send you push notifications when your fantasy players score points or when games start.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            if notificationPermissionGranted {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Notifications Enabled")
                        .fontWeight(.medium)
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)
            } else if isCheckingPermissions {
                HStack {
                    ProgressView()
                        .scaleEffect(0.8)
                    Text("Requesting permission...")
                        .fontWeight(.medium)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            } else if notificationPermissionDenied {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                        .font(.title3)

                    Text("Notifications were denied")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .multilineTextAlignment(.center)

                    Text("To enable notifications, please go to Settings > Notifications > Sleeper Live Activity and turn on Allow Notifications")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            } else {
                VStack(spacing: 8) {
                    Text("Tap the button below to enable notifications")
                        .font(.subheadline)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)

                    Text("A system dialog will appear asking for permission")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)
            }
        }
    }

    private var networkPermissionStep: some View {
        VStack(spacing: 24) {
            Image(systemName: "network")
                .font(.system(size: 80))
                .foregroundColor(.blue)

            VStack(spacing: 16) {
                Text("Enable Network Access")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("We need to connect to your local Sleeper API server to fetch real-time fantasy data and sync your Live Activities.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            switch networkPermissionState {
            case .granted:
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Network Access Enabled")
                        .fontWeight(.medium)
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)

            case .denied:
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                        .font(.title3)

                    Text("Local Network Access was denied")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .multilineTextAlignment(.center)

                    Text("To enable network access, please go to Settings > Privacy & Security > Local Network and turn on Sleeper Live Activity")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)

            case .unset:
                if isCheckingPermissions {
                    HStack {
                        ProgressView()
                            .scaleEffect(0.8)
                        Text("Testing network connection...")
                            .fontWeight(.medium)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                } else {
                    VStack(spacing: 8) {
                        Text("Tap the button below to test network connection")
                            .font(.subheadline)
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)

                        Text("A system dialog may appear asking for local network access")
                            .font(.caption)
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
            }
        }
    }

    private var liveActivityPermissionStep: some View {
        VStack(spacing: 24) {
            Image(systemName: "rectangle.stack.badge.play")
                .font(.system(size: 80))
                .foregroundColor(.blue)

            VStack(spacing: 16) {
                Text("Enable Live Activities")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("Live Activities show your fantasy scores right on your lock screen and in the Dynamic Island. This is where the magic happens!")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            if liveActivityPermissionGranted {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Live Activities Enabled")
                        .fontWeight(.medium)
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .cornerRadius(8)
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                        .font(.title3)

                    Text("Live Activities are not enabled")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .multilineTextAlignment(.center)

                    Text("To enable Live Activities, please go to Settings > Face ID & Passcode > Live Activities and turn it on")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.orange.opacity(0.1))
                .cornerRadius(8)
            }
        }
    }

    private var canProceed: Bool {
        let result: Bool
        switch currentStep {
        case 0:
            result = true
        case 1:
            // Always allow proceeding on step 1 so user can request permissions
            result = true
        case 2:
            #if DEBUG
            // Debug: Always allow proceeding on step 2 (network test)
            result = true
            #else
            // Release: Step 2 is Live Activities, always allow proceeding
            result = true
            #endif
        case 3:
            #if DEBUG
            // Debug: Step 3 is Live Activities, always allow proceeding
            result = true
            #else
            // Release: No step 3
            result = false
            #endif
        default:
            result = false
        }
        print("🔍 canProceed for step \(currentStep): \(result) (notifications: \(notificationPermissionGranted), network: \(networkPermissionState), liveActivity: \(liveActivityPermissionGranted))")
        return result
    }

    private var nextButtonTitle: String {
        switch currentStep {
        case 0:
            return "Get Started"
        case 1:
            if notificationPermissionGranted {
                return "Next"
            } else if notificationPermissionDenied {
                return "Open Settings"
            } else {
                return isCheckingPermissions ? "Requesting..." : "Enable Notifications"
            }
        case 2:
            #if DEBUG
            switch networkPermissionState {
            case .granted:
                return "Next"
            case .denied:
                return "Open Settings"
            case .unset:
                return isCheckingPermissions ? "Testing..." : "Test Network"
            }
            #else
            // Release: Step 2 is Live Activities
            if liveActivityPermissionGranted {
                return "Complete Setup"
            } else {
                return "Open Settings"
            }
            #endif
        case 3:
            #if DEBUG
            // Debug: Step 3 is Live Activities
            if liveActivityPermissionGranted {
                return "Complete Setup"
            } else {
                return "Open Settings"
            }
            #else
            // Release: No step 3
            return "Next"
            #endif
        default:
            return "Next"
        }
    }

    private func nextAction() {
        switch currentStep {
        case 0:
            withAnimation {
                currentStep += 1
            }
        case 1:
            if notificationPermissionGranted {
                withAnimation {
                    currentStep += 1
                }
            } else {
                requestNotificationPermission()
            }
        case 2:
            #if DEBUG
            switch networkPermissionState {
            case .granted:
                withAnimation {
                    currentStep += 1
                }
            case .denied:
                openSettings()
            case .unset:
                testNetworkPermission()
            }
            #else
            // Release: Step 2 is Live Activities
            if liveActivityPermissionGranted {
                completeOnboarding()
            } else {
                openSettings()
            }
            #endif
        case 3:
            #if DEBUG
            // Debug: Step 3 is Live Activities
            if liveActivityPermissionGranted {
                completeOnboarding()
            } else {
                openSettings()
            }
            #else
            // Release: No step 3
            break
            #endif
        default:
            break
        }
    }

    private func requestNotificationPermission() {
        // Check current status first
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                if settings.authorizationStatus == .denied {
                    // Permission was previously denied, can't request again
                    print("🔔 Notification permission previously denied, directing to Settings")
                    self.notificationPermissionDenied = true
                    self.openSettings()
                    return
                }

                // Permission not yet requested or is undetermined, proceed with request
                self.isCheckingPermissions = true
                print("🔔 Requesting notification permission...")

                // Add a timeout in case the permission dialog doesn't appear
                DispatchQueue.main.asyncAfter(deadline: .now() + 10) {
                    if self.isCheckingPermissions {
                        print("⏰ Permission request timed out")
                        self.isCheckingPermissions = false
                    }
                }

                UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
                    print("🔔 Notification permission result: granted=\(granted), error=\(String(describing: error))")

                    DispatchQueue.main.async {
                        self.isCheckingPermissions = false
                        self.notificationPermissionGranted = granted
                        self.notificationPermissionDenied = !granted

                        if let error = error {
                            print("❌ Notification permission error: \(error)")
                        }

                        if granted {
                            print("✅ Notification permission granted, moving to next step")
                            // Automatically move to next step after a brief delay
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                                if self.currentStep == 1 { // Only advance if still on the same step
                                    withAnimation {
                                        self.currentStep += 1
                                    }
                                }
                            }
                        } else {
                            print("❌ Notification permission denied")
                        }
                    }
                }
            }
        }
    }

    private func testNetworkPermission() {
        isCheckingPermissions = true
        networkTestAttempts += 1

        print("🌐 Testing network permission with health check (attempt \(networkTestAttempts))...")

        // Add a timeout - give more time for user to respond to dialog
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
            if self.isCheckingPermissions {
                print("⏰ Network test timed out")
                self.isCheckingPermissions = false
                // Reset to unset state on timeout - let user try again
                self.networkPermissionState = .unset
            }
        }

        Task {
            do {
                // Use existing API client to make a health check request
                let apiClient = SleeperAPIClient()
                let _ = try await apiClient.healthCheck()

                await MainActor.run {
                    self.isCheckingPermissions = false

                    // Reset attempt counter on success
                    self.networkTestAttempts = 0

                    // Only set as granted if the request actually succeeded
                    self.networkPermissionState = .granted

                    // Store the successful state
                    UserDefaults.standard.set(true, forKey: "NetworkPermissionGranted")
                    UserDefaults.standard.set(false, forKey: "NetworkPermissionDenied")

                    print("✅ Network request succeeded - permission granted, moving to next step")
                    // Automatically move to next step after success
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                        if self.currentStep == 2 { // Only advance if still on the same step
                            withAnimation {
                                self.currentStep += 1
                            }
                        }
                    }
                }
            } catch {
                print("❌ Network test failed: \(error)")

                // Wait a moment to see if this was just the initial dialog delay
                try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds

                // Try one more time to confirm denial
                do {
                    let apiClient = SleeperAPIClient()
                    let _ = try await apiClient.healthCheck()

                    // If second attempt succeeds, user allowed permission
                    await MainActor.run {
                        self.isCheckingPermissions = false
                        self.networkTestAttempts = 0
                        self.networkPermissionState = .granted

                        UserDefaults.standard.set(true, forKey: "NetworkPermissionGranted")
                        UserDefaults.standard.set(false, forKey: "NetworkPermissionDenied")

                        print("✅ Network request succeeded on retry - permission granted")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                            if self.currentStep == 2 { // Only advance if still on the same step
                                withAnimation {
                                    self.currentStep += 1
                                }
                            }
                        }
                    }
                } catch {
                    // Second attempt also failed - user denied permission
                    await MainActor.run {
                        self.isCheckingPermissions = false
                        self.networkPermissionState = .denied

                        UserDefaults.standard.set(false, forKey: "NetworkPermissionGranted")
                        UserDefaults.standard.set(true, forKey: "NetworkPermissionDenied")

                        print("❌ Network request failed on retry - permission denied")
                    }
                }
            }
        }
    }

    private func checkLiveActivityPermission() {
        let authInfo = ActivityAuthorizationInfo()
        liveActivityPermissionGranted = authInfo.areActivitiesEnabled

        if liveActivityPermissionGranted {
            completeOnboarding()
        }
    }

    private func checkInitialPermissions() {
        // Check notification permissions
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                let isAuthorized = settings.authorizationStatus == .authorized
                let isDenied = settings.authorizationStatus == .denied
                print("🔔 Initial notification permission check: \(settings.authorizationStatus.rawValue) (authorized: \(isAuthorized), denied: \(isDenied))")
                self.notificationPermissionGranted = isAuthorized
                self.notificationPermissionDenied = isDenied
            }
        }

        // Check Live Activity permissions
        let authInfo = ActivityAuthorizationInfo()
        let areEnabled = authInfo.areActivitiesEnabled
        print("🎯 Initial Live Activity permission check: \(areEnabled)")
        liveActivityPermissionGranted = areEnabled
        liveActivityPermissionDenied = !areEnabled

        // Check network permission status from persistent storage and test
        checkNetworkPermissionStatus()
    }

    private func checkNetworkPermissionStatus() {
        // Check if we have a stored network permission state
        let storedGranted = UserDefaults.standard.bool(forKey: "NetworkPermissionGranted")
        let storedDenied = UserDefaults.standard.bool(forKey: "NetworkPermissionDenied")

        if storedDenied {
            // Previously denied, show denied state immediately without testing
            print("🌐 Network was previously denied, showing denied state")
            networkPermissionState = .denied
        } else if storedGranted {
            // Previously granted, show granted state immediately without testing
            print("🌐 Network was previously granted, showing granted state")
            networkPermissionState = .granted
        } else {
            // Never tested before
            networkPermissionState = .unset
        }
    }

    private func testNetworkPermissionSilently() {
        Task {
            do {
                let apiClient = SleeperAPIClient()
                let _ = try await apiClient.healthCheck()

                await MainActor.run {
                    self.networkPermissionState = .granted
                    // Store the successful state
                    UserDefaults.standard.set(true, forKey: "NetworkPermissionGranted")
                    UserDefaults.standard.set(false, forKey: "NetworkPermissionDenied")
                    print("✅ Network permission verified as granted")
                }
            } catch {
                await MainActor.run {
                    self.networkPermissionState = .denied
                    // Store the denied state
                    UserDefaults.standard.set(false, forKey: "NetworkPermissionGranted")
                    UserDefaults.standard.set(true, forKey: "NetworkPermissionDenied")
                    print("❌ Network permission verified as denied")
                }
            }
        }
    }

    private func verifyNetworkPermissionAfterSettings() {
        // This will run when user potentially returns from Settings
        // Only test if we're still showing denied state
        if networkPermissionState == .denied {
            print("🌐 Verifying network permission after Settings visit...")
            testNetworkPermissionSilently()
        }
    }

    private func openSettings() {
        if let settingsUrl = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(settingsUrl)
        }
    }

    private func completeOnboarding() {
        print("🎯 Attempting to complete onboarding...")
        print("   Notifications granted: \(notificationPermissionGranted)")
        print("   Live Activities granted: \(liveActivityPermissionGranted)")

        // Mark onboarding as completed regardless of permission status
        // The app can still function with limited permissions
        UserDefaults.standard.set(true, forKey: "OnboardingCompleted")

        print("🔄 Setting isCompleted to false to dismiss sheet...")
        isCompleted = false

        print("✅ Onboarding completed")
    }
}

struct PermissionFeatureRow: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(.blue)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .fontWeight(.medium)

                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
    }
}

#Preview {
    OnboardingView(isCompleted: .constant(false))
}