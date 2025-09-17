//
//  SharedAvatarView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/14/25.
//  Shared avatar component for consistent image loading across app and widget
//

import SwiftUI

public struct SharedAvatarView: View {
    let userID: String
    let placeholderColor: Color
    let size: CGFloat
    let useMinimized: Bool

    public init(userID: String, placeholderColor: Color, size: CGFloat, useMinimized: Bool = false) {
        self.userID = userID
        self.placeholderColor = placeholderColor
        self.size = size
        self.useMinimized = useMinimized || size <= 30 // Auto-use minimized for small sizes
    }

    public var body: some View {
        ZStack {
            if let localImageURL = getLocalImageURL(),
               let imageData = try? Data(contentsOf: localImageURL),
               let uiImage = UIImage(data: imageData) {
                Image(uiImage: uiImage)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: size, height: size)
                    .clipShape(Circle())
            } else {
                Circle()
                    .fill(placeholderColor.opacity(0.3))
                    .frame(width: size, height: size)
                    .overlay(
                        Image(systemName: "person.fill")
                            .foregroundColor(placeholderColor)
                            .font(.system(size: size * 0.4))
                    )
            }
        }
    }

    private func getLocalImageURL() -> URL? {
        // Don't try to load avatar if userID is empty
        guard !userID.isEmpty else {
            return nil
        }

        guard let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: "group.jdegrand.SleeperLiveActivityApp") else {
            print("❌ SharedAvatarView: No access to shared container")
            return nil
        }

        // Use minimized version if requested, otherwise use regular version
        let filename = useMinimized ? "\(userID)_mini.jpg" : "\(userID).jpg"
        let fileURL = containerURL.appendingPathComponent(filename)

        print("🔍 SharedAvatarView: UserID: \(userID), useMinimized: \(useMinimized)")
        print("🔍 SharedAvatarView: Looking for: \(filename)")

        if FileManager.default.fileExists(atPath: fileURL.path) {
            print("✅ SharedAvatarView: Found avatar file at: \(fileURL.path)")
            return fileURL
        } else {
            print("❌ SharedAvatarView: Avatar file not found at: \(fileURL.path)")
            return nil
        }
    }
}