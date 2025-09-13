//
//  SleeperLiveActivityAppApp.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import SwiftUI
import ActivityKit
import WidgetKit

@main
struct SleeperLiveActivityAppApp: App {
    @StateObject private var gameMonitor = GameStateMonitor()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(gameMonitor)
                .onAppear {
                    gameMonitor.startMonitoring()
                }
        }
    }
}

