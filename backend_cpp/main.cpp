#include "third_party/httplib.h"
#include "third_party/json.hpp"
#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

using json = nlohmann::json;

// Check if text is garbage (too many special characters or nonsense)
bool is_garbage(const std::string& text) {
    if (text.empty()) return true;
    
    int letters_digits = 0;
    int total_chars = 0;
    int word_count = 0;
    int word_length = 0;
    int total_word_length = 0;
    
    for (char c : text) {
        unsigned char uc = static_cast<unsigned char>(c);
        if (std::isspace(uc)) {
            if (word_length > 0) {
                word_count++;
                total_word_length += word_length;
                word_length = 0;
            }
        } else {
            total_chars++;
            if (std::isalnum(uc)) {
                letters_digits++;
            }
            word_length++;
        }
    }
    
    if (word_length > 0) {
        word_count++;
        total_word_length += word_length;
    }
    
    if (total_chars == 0) return true;
    
    double letter_ratio = static_cast<double>(letters_digits) / total_chars;
    double avg_word_length = word_count > 0 ? static_cast<double>(total_word_length) / word_count : 0;
    
    // If less than 70% letters/digits OR average word length > 20 => garbage
    if (letter_ratio < 0.70 || avg_word_length > 20.0) {
        return true;
    }
    
    return false;
}

// Clean markdown formatting
std::string clean_markdown(const std::string& text) {
    std::string cleaned = text;
    
    // Remove common markdown symbols
    std::string markdown_chars = "#*_~`>";
    for (char c : markdown_chars) {
        cleaned.erase(std::remove(cleaned.begin(), cleaned.end(), c), cleaned.end());
    }
    
    // Replace multiple spaces with single space
    auto new_end = std::unique(cleaned.begin(), cleaned.end(), 
        [](char a, char b) { return std::isspace(a) && std::isspace(b); });
    cleaned.erase(new_end, cleaned.end());
    
    return cleaned;
}

// Chunk text into pieces with overlap
std::vector<std::string> chunk_text(const std::string& text, int chunk_size = 1000, int overlap = 100) {
    std::vector<std::string> chunks;
    
    if (text.empty()) return chunks;
    
    std::string cleaned = clean_markdown(text);
    
    int start = 0;
    int text_length = cleaned.length();
    
    while (start < text_length) {
        int end = std::min(start + chunk_size, text_length);
        
        // Try to break at word boundary
        if (end < text_length) {
            while (end > start && !std::isspace(static_cast<unsigned char>(cleaned[end]))) {
                end--;
            }
            if (end == start) {
                end = std::min(start + chunk_size, text_length);
            }
        }
        
        std::string chunk = cleaned.substr(start, end - start);
        
        // Trim whitespace
        chunk.erase(0, chunk.find_first_not_of(" \n\r\t"));
        chunk.erase(chunk.find_last_not_of(" \n\r\t") + 1);
        
        if (!chunk.empty()) {
            chunks.push_back(chunk);
        }
        
        int next_start = end - overlap;
        if (next_start <= start) {
            next_start = end;
        }
        start = next_start;
        if (start < 0) start = 0;
        if (start >= text_length) break;
    }
    
    return chunks;
}

int main() {
    httplib::Server svr;
    
    // Health check endpoint
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        json response = {{"status", "ok"}};
        res.set_content(response.dump(), "application/json");
    });
    
    // Main processing endpoint
    svr.Post("/process", [](const httplib::Request& req, httplib::Response& res) {
        try {
            auto body = json::parse(req.body);
            
            if (!body.contains("text")) {
                res.status = 400;
                json error = {{"error", "Missing 'text' field"}};
                res.set_content(error.dump(), "application/json");
                return;
            }
            
            std::string text = body["text"];
            
            json response;
            response["is_garbage"] = is_garbage(text);
            
            if (!response["is_garbage"]) {
                int chunk_size = body.value("chunk_size", 1000);
                int overlap = body.value("overlap", 100);
                
                auto chunks = chunk_text(text, chunk_size, overlap);
                response["chunks"] = chunks;
            } else {
                response["chunks"] = json::array();
            }
            
            res.set_content(response.dump(), "application/json");
            
        } catch (const std::exception& e) {
            res.status = 500;
            json error = {{"error", e.what()}};
            res.set_content(error.dump(), "application/json");
        }
    });
    
    std::cout << "C++ Backend starting on 0.0.0.0:8080..." << std::endl;
    svr.listen("0.0.0.0", 8080);
    
    return 0;
}
