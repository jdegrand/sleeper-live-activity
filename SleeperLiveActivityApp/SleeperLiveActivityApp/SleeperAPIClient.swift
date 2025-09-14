//
//  SleeperAPIClient.swift
//  SleeperLiveActivityApp
//
//  Created by Joey DeGrand on 9/12/25.
//

import Foundation

class SleeperAPIClient {
    private let baseURL = "http://192.168.4.194:8000"
    private let session = URLSession.shared
    
    func registerUser(config: UserConfig) async throws {
        let url = URL(string: "\(baseURL)/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
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
        let (data, response) = try await session.data(from: url)
        
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
        let url = URL(string: "\(baseURL)/live-activity/start/\(deviceID)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (_, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.liveActivityFailed
        }
    }
    
    func endLiveActivity(deviceID: String) async throws {
        let url = URL(string: "\(baseURL)/live-activity/end/\(deviceID)")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
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
