//
//  SkeletonView.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/17/25.
//

import SwiftUI

struct SkeletonView: View {
    @State private var animateGradient = false

    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                SkeletonShape()
                    .frame(width: 120, height: 16)
                Spacer()
                SkeletonShape()
                    .frame(width: 80, height: 16)
            }

            // Main content area
            VStack(spacing: 12) {
                // User vs Opponent
                HStack(spacing: 16) {
                    // User side
                    HStack(spacing: 8) {
                        SkeletonShape()
                            .frame(width: 32, height: 32)
                            .clipShape(Circle())

                        VStack(alignment: .leading, spacing: 4) {
                            SkeletonShape()
                                .frame(width: 60, height: 12)
                            SkeletonShape()
                                .frame(width: 40, height: 16)
                        }
                    }

                    Spacer()

                    // VS
                    SkeletonShape()
                        .frame(width: 24, height: 12)

                    Spacer()

                    // Opponent side
                    HStack(spacing: 8) {
                        VStack(alignment: .trailing, spacing: 4) {
                            SkeletonShape()
                                .frame(width: 60, height: 12)
                            SkeletonShape()
                                .frame(width: 40, height: 16)
                        }

                        SkeletonShape()
                            .frame(width: 32, height: 32)
                            .clipShape(Circle())
                    }
                }

                // Status line
                HStack {
                    SkeletonShape()
                        .frame(width: 12, height: 12)
                        .clipShape(Circle())
                    SkeletonShape()
                        .frame(width: 100, height: 12)
                    Spacer()
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
}

struct SkeletonShape: View {
    @State private var animateGradient = false

    var body: some View {
        Rectangle()
            .fill(
                LinearGradient(
                    gradient: Gradient(colors: [
                        Color(.systemGray5),
                        Color(.systemGray4),
                        Color(.systemGray5)
                    ]),
                    startPoint: animateGradient ? .leading : .trailing,
                    endPoint: animateGradient ? .trailing : .leading
                )
            )
            .onAppear {
                withAnimation(
                    Animation.easeInOut(duration: 1.5)
                        .repeatForever(autoreverses: true)
                ) {
                    animateGradient.toggle()
                }
            }
    }
}

#Preview {
    SkeletonView()
        .padding()
}