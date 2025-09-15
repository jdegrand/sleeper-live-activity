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

    // Download and cache image for Live Activities, return local file URL
    public func downloadAndCacheImageAsLocalURL(from urlString: String, maxSize: CGSize = CGSize(width: 40, height: 40)) async -> String? {
        // Check if we already have a local file for this URL
        if let localURL = getLocalFileURL(for: urlString), FileManager.default.fileExists(atPath: localURL.path) {
            print("✅ Using existing local file: \(localURL.absoluteString)")
            return localURL.absoluteString
        }

        // Download image
        guard let url = URL(string: urlString) else { return nil }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else { return nil }

            // Crop to square and resize to small size (40x40)
            let squareImage = cropToSquare(image)
            let resizedImage = resizeImage(squareImage, to: maxSize)

            // Compress to PNG and save locally
            guard let pngData = resizedImage.pngData() else { return nil }

            // Ensure file size is small (limit to 50KB for safety)
            if pngData.count > 50_000 {
                print("⚠️ Image too large after compression (\(pngData.count) bytes), skipping")
                return nil
            }

            // Save to local documents directory
            guard let localURL = saveImageToLocalFile(data: pngData, key: urlString) else { return nil }

            // Also cache in memory for app use
            let cacheKey = NSString(string: urlString)
            cache.setObject(resizedImage, forKey: cacheKey)

            print("✅ Saved image locally: \(localURL.absoluteString) (\(pngData.count) bytes)")
            return localURL.absoluteString

        } catch {
            print("❌ Error downloading image: \(error)")
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
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.jdegrand.SleeperLiveActivityApp") else {
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
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.jdegrand.SleeperLiveActivityApp"),
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

    // Helper methods for local file URL approach
    private func getLocalFileURL(for urlString: String) -> URL? {
        guard let containerURL = fileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.jdegrand.SleeperLiveActivityApp") else {
            print("❌ Failed to get shared container URL for local file")
            return nil
        }
        
        // Extract the filename from the URL
        guard let url = URL(string: urlString) else {
            print("❌ Invalid URL string: \(urlString)")
            return nil
        }
        
        // Use the last path component as the filename
        let filename = url.lastPathComponent
        let fileURL = containerURL.appendingPathComponent(filename)
        
        // Log the generated file URL
        print("📁 Generated local file URL: \(fileURL.absoluteString)")
        return fileURL
    }

    private func saveImageToLocalFile(data: Data, key: String) -> URL? {
        guard let localURL = getLocalFileURL(for: key) else { 
            print("❌ Failed to get local URL for key: \(key)")
            return nil 
        }
        
        // Ensure directory exists
        let directory = localURL.deletingLastPathComponent()
        do {
            try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
            print("✅ Created directory: \(directory.path)")
        } catch {
            print("❌ Failed to create directory: \(error)")
            return nil
        }

        do {
            try data.write(to: localURL)
            print("✅ Successfully saved image to: \(localURL.path)")
            return localURL
        } catch {
            print("❌ Failed to save image to local file: \(error)")
            return nil
        }
    }

    private func cropToSquare(_ image: UIImage) -> UIImage {
        let size = min(image.size.width, image.size.height)
        let x = (image.size.width - size) / 2
        let y = (image.size.height - size) / 2
        let cropRect = CGRect(x: x, y: y, width: size, height: size)

        guard let cgImage = image.cgImage?.cropping(to: cropRect) else { return image }
        return UIImage(cgImage: cgImage)
    }
}