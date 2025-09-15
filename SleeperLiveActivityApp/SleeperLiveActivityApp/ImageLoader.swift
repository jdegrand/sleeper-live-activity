import Foundation
import UIKit

class ImageLoader: ObservableObject {
    static let shared = ImageLoader()
    private let cache = NSCache<NSString, UIImage>()
    private let fileManager = FileManager.default
    private let imageCacheDirectory: URL
    
    private init() {
        // Create cache directory if it doesn't exist
        let paths = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)
        imageCacheDirectory = paths[0].appendingPathComponent("SleeperAvatars")
        
        do {
            try fileManager.createDirectory(at: imageCacheDirectory, withIntermediateDirectories: true)
        } catch {
            print("❌ Failed to create image cache directory: \(error)")
        }
    }
    
    func loadImage(from urlString: String?, completion: @escaping (String?) -> Void) {
        guard let urlString = urlString, let url = URL(string: urlString) else {
            completion(nil)
            return
        }
        
        // Check memory cache first
        if let cachedImage = cache.object(forKey: urlString as NSString) {
            // Save to disk for persistence
            saveImageToDisk(cachedImage, for: urlString)
            completion(localURL(for: urlString)?.path)
            return
        }
        
        // Check disk cache
        if let localPath = localURL(for: urlString)?.path,
           fileManager.fileExists(atPath: localPath) {
            // Load into memory cache
            if let image = UIImage(contentsOfFile: localPath) {
                cache.setObject(image, forKey: urlString as NSString)
                completion(localPath)
                return
            }
        }
        
        // Download the image
        let task = URLSession.shared.dataTask(with: url) { [weak self] data, _, error in
            guard let self = self,
                  let data = data,
                  let image = UIImage(data: data),
                  error == nil else {
                completion(nil)
                return
            }
            
            // Save to memory and disk
            self.cache.setObject(image, forKey: urlString as NSString)
            self.saveImageToDisk(image, for: urlString)
            
            DispatchQueue.main.async {
                completion(self.localURL(for: urlString)?.path)
            }
        }
        task.resume()
    }
    
    private func localURL(for urlString: String) -> URL? {
        guard let filename = urlString.components(separatedBy: "/").last else { return nil }
        return imageCacheDirectory.appendingPathComponent(filename)
    }
    
    private func saveImageToDisk(_ image: UIImage, for urlString: String) {
        guard let localURL = localURL(for: urlString),
              let data = image.pngData() else { return }
        
        do {
            try data.write(to: localURL)
            print("💾 Saved image to: \(localURL.path)")
        } catch {
            print("❌ Failed to save image: \(error)")
        }
    }
    
    func clearCache() {
        cache.removeAllObjects()
        do {
            let files = try fileManager.contentsOfDirectory(at: imageCacheDirectory, 
                                                         includingPropertiesForKeys: nil)
            for file in files {
                try fileManager.removeItem(at: file)
            }
        } catch {
            print("❌ Failed to clear image cache: \(error)")
        }
    }
}
