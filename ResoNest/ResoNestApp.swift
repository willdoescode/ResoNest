//
//  ResoNestApp.swift
//  ResoNest
//
//  Created by Will Lane on 10/17/24.
//

import SwiftData
import SwiftUI

@main
struct ResoNestApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: Item.self)
    }
}
