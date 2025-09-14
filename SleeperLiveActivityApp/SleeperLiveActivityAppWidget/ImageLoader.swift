//
//  ImageLoader.swift
//  SleeperLiveActivityAppWidget
//
//  Created by Joey DeGrand on 9/14/25.
//

import Foundation
import UIKit

class ImageLoader {
    static let shared = ImageLoader()
    private let fileManager = FileManager.default

    private init() {}

    func getImageFromSharedContainer(url: String) -> UIImage? {
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.sleeper.liveactivity") else {
            print("❌ Widget: Failed to get shared container URL")
            return nil
        }

        let filename = url.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? "default"
        let imageURL = containerURL.appendingPathComponent("\(filename).png")

        print("🔍 Widget: Looking for image at: \(imageURL.path)")

        // List files in shared container for debugging
        do {
            let files = try fileManager.contentsOfDirectory(at: containerURL, includingPropertiesForKeys: nil)
            print("📁 Widget: Files in shared container: \(files.map { $0.lastPathComponent })")
        } catch {
            print("❌ Widget: Failed to list shared container contents: \(error)")
        }

        guard let data = try? Data(contentsOf: imageURL) else {
            print("❌ Widget: Failed to load image from shared container: \(imageURL.path)")
            return nil
        }

        print("✅ Widget: Loaded image from shared container: \(filename)")
        return UIImage(data: data)
    }
}