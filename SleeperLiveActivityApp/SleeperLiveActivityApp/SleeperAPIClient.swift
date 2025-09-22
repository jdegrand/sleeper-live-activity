//
//  SleeperAPIClient.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import Foundation

class SleeperAPIClient {
    private let baseURL: String
    private let session = URLSession.shared

    // Lazy property to load API key when first accessed
    private lazy var apiKey: String? = {
        // Try to load from Config.plist (not committed to git)
        if let path = Bundle.main.path(forResource: "Config", ofType: "plist"),
           let plist = NSDictionary(contentsOfFile: path),
           let key = plist["API_KEY"] as? String, !key.isEmpty {
            return key
        }

        // If no config file or key, return nil (development mode)
        print("⚠️ No API key found in Config.plist - running in development mode")
        return nil
    }()

    init() {
        if let path = Bundle.main.path(forResource: "Info", ofType: "plist"),
           let plist = NSDictionary(contentsOfFile: path) {

            // Check if we should use localhost for development
            let useLocalhost = plist["USE_LOCALHOST"] as? Bool ?? false

            if useLocalhost {
                self.baseURL = "http://localhost:8000"
                print("🔧 Development Mode: Using localhost")
            } else if let url = plist["API_BASE_URL"] as? String {
                self.baseURL = url
                print("🌐 Production Mode: Using \(url)")
            } else {
                // Fallback to localhost if no URL specified
                self.baseURL = "http://localhost:8000"
                print("⚠️ No API_BASE_URL found, defaulting to localhost")
            }
        } else {
            // Fallback if Info.plist not found
            self.baseURL = "http://localhost:8000"
            print("⚠️ Info.plist not found, defaulting to localhost")
        }
    }

    private func addAuthHeaders(to request: inout URLRequest) {
        if let apiKey = apiKey {
            request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        }
    }

    private func createAuthenticatedRequest(url: URL, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        addAuthHeaders(to: &request)
        return request
    }
    
    func registerUser(config: UserConfig) async throws {
        let url = URL(string: "\(baseURL)/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeaders(to: &request)

        let jsonData = try JSONEncoder().encode(config)
        request.httpBody = jsonData

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.registrationFailed
        }
    }
    
    func getUserInfo(username: String) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/user/\(username)")!
        let request = createAuthenticatedRequest(url: url)
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    func getUserLeagues(userID: String, season: String = "2025") async throws -> [[String: Any]] {
        let url = URL(string: "\(baseURL)/user/\(userID)/leagues/\(season)")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }
        
        return try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
    }
    
    func getLeagueRosters(leagueID: String) async throws -> [[String: Any]] {
        let url = URL(string: "\(baseURL)/league/\(leagueID)/rosters")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
    }

    func getLeagueInfo(leagueID: String) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/league/\(leagueID)")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    func getMatchups(leagueID: String, week: Int) async throws -> [[String: Any]] {
        let url = URL(string: "\(baseURL)/league/\(leagueID)/matchups/\(week)")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }
        
        return try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
    }
    
    func getNFLPlayers() async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/players/nfl")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func getUser(userID: String) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/user/\(userID)")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func getUserByUsername(username: String) async throws -> [String: Any] {
        let url = URL(string: "https://api.sleeper.app/v1/user/\(username)")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    func getNFLState() async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/state/nfl")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }
        
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    func startLiveActivity(deviceID: String) async throws {
        let url = URL(string: "\(baseURL)/live-activity/start-by-id/\(deviceID)")!
        let request = createAuthenticatedRequest(url: url, method: "POST")

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.liveActivityFailed
        }
    }
    
    func endLiveActivity(deviceID: String) async throws {
        let url = URL(string: "\(baseURL)/live-activity/stop-by-id/\(deviceID)")!
        let request = createAuthenticatedRequest(url: url, method: "POST")

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.liveActivityFailed
        }
    }
    
    func getLiveActivityStatus(deviceID: String) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/live-activity/status/\(deviceID)")!
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }
        
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func registerLiveActivityToken(deviceID: String, liveActivityToken: String, activityID: String) async throws {
        let url = URL(string: "\(baseURL)/register-live-activity-token")!
        var request = createAuthenticatedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload: [String: Any] = [
            "device_id": deviceID,
            "live_activity_token": liveActivityToken,
            "activity_id": activityID
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            if let responseBody = String(data: data, encoding: .utf8) {
                print("❌ Server response: \(responseBody)")
            }
            throw APIError.registrationFailed
        }

        print("✅ Live Activity token registered successfully")
    }

    func getLeagueAvatars(leagueID: String) async throws -> [String: String] {
        let url = URL(string: "\(baseURL)/league/\(leagueID)/avatars")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        let jsonObject = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return jsonObject["avatars"] as? [String: String] ?? [:]
    }

    func getPlayerScores(deviceID: String) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/player-scores/\(deviceID)")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }

    func healthCheck() async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/health")!
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.fetchFailed
        }

        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
}

enum APIError: Error, LocalizedError {
    case registrationFailed
    case fetchFailed
    case liveActivityFailed
    
    var errorDescription: String? {
        switch self {
        case .registrationFailed:
            return "Failed to register with backend server"
        case .fetchFailed:
            return "Failed to fetch data from server"
        case .liveActivityFailed:
            return "Failed to manage Live Activity"
        }
    }
}
