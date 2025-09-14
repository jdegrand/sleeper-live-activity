//
//  SleeperLiveActivityAppWidgetBundle.swift
//  SleeperLiveActivityAppWidget
//
//  Created by Joey DeGrand on 9/14/25.
//

import WidgetKit
import SwiftUI

@main
struct SleeperLiveActivityAppWidgetBundle: WidgetBundle {
    var body: some Widget {
        SleeperLiveActivityAppWidget()
        SleeperLiveActivityAppWidgetLiveActivity()
    }
}
