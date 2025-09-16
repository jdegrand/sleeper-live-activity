//
//  SharedAvatarView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/14/25.
//  Shared avatar component for consistent image loading across app and widget
//

import SwiftUI

public struct SharedAvatarView: View {
    let avatarURL: String
    let placeholderColor: Color
    let size: CGFloat

    public init(avatarURL: String, placeholderColor: Color, size: CGFloat) {
        self.avatarURL = avatarURL
        self.placeholderColor = placeholderColor
        self.size = size
    }

    public var body: some View {
        ZStack {
            // For now, use placeholder since we're only using remote URLs
            // In the future, this could be enhanced to load from avatarURL
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