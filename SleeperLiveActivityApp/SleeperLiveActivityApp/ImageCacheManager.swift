//
//  ImageCacheManager.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/14/25.
//

import SwiftUI
import UIKit

public class ImageCacheManager: ObservableObject {
    public static let shared = ImageCacheManager()
    private let cache = NSCache<NSString, UIImage>()
    private let fileManager = FileManager.default

    private init() {
        cache.countLimit = 100
        cache.totalCostLimit = 50 * 1024 * 1024 // 50MB
    }

    // Download and cache image for Live Activities (resize to proper dimensions)
    public func downloadAndCacheImage(from urlString: String, maxSize: CGSize = CGSize(width: 32, height: 32)) async -> UIImage? {
        let cacheKey = NSString(string: urlString)

        // Check cache first
        if let cachedImage = cache.object(forKey: cacheKey) {
            return cachedImage
        }

        // Download image
        guard let url = URL(string: urlString) else { return nil }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else { return nil }

            // Resize image to fit Live Activity constraints
            let resizedImage = resizeImage(image, to: maxSize)

            // Cache the resized image
            cache.setObject(resizedImage, forKey: cacheKey)

            // Save to shared container for widget extension
            await saveImageToSharedContainer(resizedImage, key: urlString)

            return resizedImage
        } catch {
            print("Failed to download image: \(error)")
            return nil
        }
    }

    // Get cached image or placeholder
    public func getCachedImage(for urlString: String) -> UIImage? {
        let cacheKey = NSString(string: urlString)
        return cache.object(forKey: cacheKey)
    }

    // Get image from shared container (for widget extension)
    public func getImageFromSharedContainer(key: String) -> UIImage? {
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.sleeper.liveactivity") else {
            print("❌ Failed to get shared container URL")
            return nil
        }

        let filename = key.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? "default"
        let imageURL = containerURL.appendingPathComponent("\(filename).png")

        guard let data = try? Data(contentsOf: imageURL) else {
            print("❌ Failed to load image from shared container: \(imageURL)")
            return nil
        }

        print("✅ Loaded image from shared container: \(filename)")
        return UIImage(data: data)
    }

    private func resizeImage(_ image: UIImage, to size: CGSize) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }

    private func saveImageToSharedContainer(_ image: UIImage, key: String) async {
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.sleeper.liveactivity"),
              let data = image.pngData() else {
            print("❌ Failed to get shared container URL or convert image to PNG")
            return
        }

        let filename = key.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? "default"
        let imageURL = containerURL.appendingPathComponent("\(filename).png")

        do {
            try data.write(to: imageURL)
            print("✅ Saved image to shared container: \(filename)")
        } catch {
            print("❌ Failed to save image to shared container: \(error)")
        }
    }
}