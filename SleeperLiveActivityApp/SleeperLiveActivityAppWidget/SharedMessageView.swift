//
//  SharedMessageView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/17/25.
//  Shared message component with auto-disappear functionality
//

import SwiftUI
import Combine

public struct SharedMessageView: View {
    let message: String
    let lastUpdate: Date
    let width: CGFloat?
    let alignment: Alignment
    let shouldRemoveEmoji: Bool

    @State private var shouldShow: Bool = true
    @State private var timer: Timer?

    public init(
        message: String,
        lastUpdate: Date,
        width: CGFloat? = nil,
        alignment: Alignment = .leading,
        shouldRemoveEmoji: Bool = false
    ) {
        self.message = message
        self.lastUpdate = lastUpdate
        self.width = width
        self.alignment = alignment
        self.shouldRemoveEmoji = shouldRemoveEmoji
    }

    public var body: some View {
        if shouldShow && !message.isEmpty {
            let isScoreUpdate = message.contains(/🔥|⚡/)

            HStack {
                if isScoreUpdate && shouldRemoveEmoji {
                    Image(systemName: message.contains("🔥") ? "flame.fill" : "bolt.fill")
                        .font(.caption2)
                        .foregroundColor(.orange)
                } else {
                    Image(systemName: "doc.text.fill")
                        .font(.caption2)
                        .foregroundColor(.orange)
                }

                Text(shouldRemoveEmoji && isScoreUpdate ? MessageLogic.getDisplayMessage(message) : message)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .truncationMode(.tail)

                if alignment == .leading {
                    Spacer()
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.orange.opacity(0.15))
            .cornerRadius(8)
            .frame(width: width, alignment: alignment)
            .onAppear {
                startAutoDisappearTimer()
            }
            .onChange(of: message) { oldValue, newValue in
                if oldValue != newValue {
                    shouldShow = true
                    startAutoDisappearTimer()
                }
            }
            .onChange(of: lastUpdate) { oldValue, newValue in
                if oldValue != newValue {
                    shouldShow = true
                    startAutoDisappearTimer()
                }
            }
        }
    }

    private func startAutoDisappearTimer() {
        timer?.invalidate()

        timer = Timer.scheduledTimer(withTimeInterval: 60.0, repeats: false) { _ in
            withAnimation(.easeOut(duration: 0.3)) {
                shouldShow = false
            }
        }
    }
}

public struct MessageLogic {
    public static func isScoreUpdate(_ message: String) -> Bool {
        return message.contains(/🔥|⚡/)
    }

    public static func getDisplayMessage(_ message: String) -> String {
        let isScoreUpdate = isScoreUpdate(message)
        if isScoreUpdate {
            // Remove the emoji and following space
            if message.hasPrefix("🔥 ") {
                return String(message.dropFirst(2))
            } else if message.hasPrefix("⚡ ") {
                return String(message.dropFirst(2))
            }
        }
        return message
    }

    public static func getIconName(_ message: String) -> String? {
        guard isScoreUpdate(message) else { return nil }
        return message.contains("🔥") ? "flame.fill" : "bolt.fill"
    }
}
