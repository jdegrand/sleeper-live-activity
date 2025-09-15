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
    let localAvatarURL: String?
    let placeholderColor: Color
    let size: CGFloat

    public init(avatarURL: String, localAvatarURL: String?, placeholderColor: Color, size: CGFloat) {
        self.avatarURL = avatarURL
        self.localAvatarURL = localAvatarURL
        self.placeholderColor = placeholderColor
        self.size = size
    }

    public var body: some View {
        ZStack {
            if let localPath = localAvatarURL,
               let url = URL(string: localPath),
               let data = try? Data(contentsOf: url, options: [.mappedIfSafe]),
               let uiImage = UIImage(data: data) {
                Image(uiImage: uiImage)
                    .resizable()
                    .scaledToFill()
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
}