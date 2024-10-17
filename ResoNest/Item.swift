//
//  Item.swift
//  ResoNest
//
//  Created by Will Lane on 10/17/24.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date

    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
