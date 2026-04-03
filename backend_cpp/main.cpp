#include "third_party/httplib.h"
#include "third_party/json.hpp"
#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

using json = nlohmann::json;

// Текст мусор ?
bool is_garbage(const std::string& text, std::string& reason) {
    if (text.empty()) {
        reason = "Empty text";
        return true;
    }
    
    if (text.length() < 50) {
        reason = "Text too short: " + std::to_string(text.length()) + " characters (minimum 50)";
        return true;
    }
    
    int letters_digits = 0;
    int total_chars = 0;
    int spaces = 0;
    int special_chars = 0;
    int word_count = 0;
    int word_length = 0;
    int total_word_length = 0;
    int unprintable = 0;
    int utf8_chars = 0;
    
    for (size_t i = 0; i < text.length(); ++i) {
        unsigned char uc = static_cast<unsigned char>(text[i]);
        
        // UTF-8 multi-byte character (кириллица, etc)
        if (uc >= 0x80) {
            // Count as letter for UTF-8
            utf8_chars++;
            letters_digits++;
            total_chars++;
            word_length++;
            
            // Skip continuation bytes
            while (i + 1 < text.length() && (static_cast<unsigned char>(text[i + 1]) & 0xC0) == 0x80) {
                i++;
            }
            continue;
        }
        
        // Check for unprintable ASCII characters
        if (uc < 32 && uc != '\n' && uc != '\r' && uc != '\t') {
            unprintable++;
        }
        
        if (std::isspace(uc)) {
            spaces++;
            if (word_length > 0) {
                word_count++;
                total_word_length += word_length;
                word_length = 0;
            }
        } else {
            total_chars++;
            if (std::isalnum(uc)) {
                letters_digits++;
            } else {
                special_chars++;
            }
            word_length++;
        }
    }
    
    if (word_length > 0) {
        word_count++;
        total_word_length += word_length;
    }
    
    // No non-space characters
    if (total_chars == 0) {
        reason = "No readable characters found";
        return true;
    }
    
    // Check for unprintable characters
    if (unprintable > 0) {
        double unprintable_ratio = static_cast<double>(unprintable) / text.length() * 100.0;
        if (unprintable_ratio > 5.0) {
            reason = "High unprintable character ratio: " + std::to_string(static_cast<int>(unprintable_ratio)) + "%";
            return true;
        }
    }
    
    // Check letter/digit ratio (including UTF-8)
    double letter_ratio = static_cast<double>(letters_digits) / total_chars;
    if (letter_ratio < 0.40) {  // Lowered threshold to be more permissive
        reason = "High special character ratio: " + std::to_string(static_cast<int>((1.0 - letter_ratio) * 100)) + "%. Text appears corrupted.";
        return true;
    }
    
    // Check for spaces (no spaces = probably garbage)
    if (spaces == 0 && text.length() > 100) {
        reason = "No spaces found. Text appears to be corrupted binary data.";
        return true;
    }
    
    // Check average word length
    double avg_word_length = word_count > 0 ? static_cast<double>(total_word_length) / word_count : 0;
    if (avg_word_length > 30.0) {
        reason = "Abnormally long words (avg: " + std::to_string(static_cast<int>(avg_word_length)) + " chars). Text appears corrupted.";
        return true;
    }
    
    // Check minimum word count
    if (word_count < 5) {
        reason = "Too few words: " + std::to_string(word_count) + " (minimum 5)";
        return true;
    }
    
    return false;
}

// Clean markdown formatting (оптимизировано для памяти)
std::string clean_markdown(const std::string& text) {
    std::string cleaned;
    cleaned.reserve(text.length());  // Резервируем память заранее
    
    bool in_code_block = false;
    bool line_start = true;
    
    const size_t len = text.length();
    for (size_t i = 0; i < len; ++i) {
        char c = text[i];
        
        // Check for code blocks ```
        if (i + 2 < len && text[i] == '`' && text[i+1] == '`' && text[i+2] == '`') {
            in_code_block = !in_code_block;
            i += 2;
            continue;
        }
        
        // Skip content in code blocks
        if (in_code_block) {
            continue;
        }
        
        // Remove markdown headers at line start
        if (line_start && c == '#') {
            while (i < len && text[i] == '#') i++;
            while (i < len && text[i] == ' ') i++;
            line_start = false;
            if (i >= len) break;
            c = text[i];
        }
        
        // Remove list markers at line start
        if (line_start && (c == '*' || c == '-' || c == '+')) {
            if (i + 1 < len && text[i+1] == ' ') {
                i++;
                line_start = false;
                continue;
            }
        }
        
        // Skip inline code `
        if (c == '`') {
            continue;
        }
        
        // Skip bold/italic markers
        if (c == '*' || c == '_') {
            // Check if it's emphasis marker (surrounded by non-space)
            if ((i > 0 && !std::isspace(text[i-1])) || 
                (i + 1 < len && !std::isspace(text[i+1]))) {
                continue;
            }
        }
        
        // Track line starts
        if (c == '\n') {
            line_start = true;
        } else if (!std::isspace(c)) {
            line_start = false;
        }
        
        cleaned += c;
    }
    
    // Replace multiple spaces/newlines with single space (in-place)
    std::string result;
    result.reserve(cleaned.length());
    bool prev_space = false;
    
    for (char c : cleaned) {
        if (std::isspace(c)) {
            if (!prev_space) {
                result += ' ';
                prev_space = true;
            }
        } else {
            result += c;
            prev_space = false;
        }
    }
    
    // Trim (избегаем лишнего substr)
    if (!result.empty()) {
        size_t start = 0;
        size_t end = result.length() - 1;
        
        while (start < result.length() && std::isspace(result[start])) start++;
        while (end > start && std::isspace(result[end])) end--;
        
        if (start > 0 || end < result.length() - 1) {
            result = result.substr(start, end - start + 1);
        }
    }
    
    return result;
}

// Find sentence boundary near position
int find_sentence_boundary(const std::string& text, int pos, int search_window = 50) {
    int best_pos = pos;
    int best_score = -1;
    
    int start = std::max(0, pos - search_window);
    int end = std::min(static_cast<int>(text.length()), pos + search_window);
    
    for (int i = start; i < end; ++i) {
        if (i >= text.length()) break;
        
        char c = text[i];
        int score = 0;
        
        // Best: sentence end (. ! ?)
        if ((c == '.' || c == '!' || c == '?') && 
            i + 1 < text.length() && std::isspace(text[i + 1])) {
            score = 100;
            // Even better if followed by capital letter
            if (i + 2 < text.length() && std::isupper(text[i + 2])) {
                score = 120;
            }
        }
        // Good: paragraph break
        else if (c == '\n' && i + 1 < text.length() && text[i + 1] == '\n') {
            score = 90;
        }
        // OK: single newline
        else if (c == '\n') {
            score = 70;
        }
        // Acceptable: comma or semicolon
        else if (c == ',' || c == ';') {
            score = 40;
        }
        // Last resort: space
        else if (std::isspace(c)) {
            score = 20;
        }
        
        // Prefer positions closer to target
        int distance_penalty = std::abs(i - pos) / 2;
        score -= distance_penalty;
        
        if (score > best_score) {
            best_score = score;
            best_pos = i + 1; // Start after the boundary
        }
    }
    
    return best_pos;
}

// Chunk text into pieces with smart overlap (оптимизировано)
std::vector<std::string> chunk_text(const std::string& text, int chunk_size = 1000, int overlap = 100) {
    std::vector<std::string> chunks;
    
    if (text.empty()) return chunks;
    
    const int text_length = static_cast<int>(text.length());
    
    // Резервируем память для вектора
    chunks.reserve((text_length / chunk_size) + 2);
    
    int start = 0;
    
    while (start < text_length) {
        int end = std::min(start + chunk_size, text_length);
        
        // Try to find smart boundary (sentence end)
        if (end < text_length) {
            end = find_sentence_boundary(text, end);
        }
        
        // Найти границы без пробелов (избегаем копирования)
        int chunk_start = start;
        int chunk_end = end;
        
        while (chunk_start < chunk_end && std::isspace(text[chunk_start])) {
            chunk_start++;
        }
        while (chunk_end > chunk_start && std::isspace(text[chunk_end - 1])) {
            chunk_end--;
        }
        
        int chunk_len = chunk_end - chunk_start;
        
        if (chunk_len >= 10) {
            chunks.emplace_back(text.substr(chunk_start, chunk_len));
        }
        
        // Calculate next start with overlap
        int next_start = end - overlap;
        if (next_start <= start) {
            next_start = end;
        }
        
        // Try to find good overlap point
        if (next_start > start && next_start < text_length) {
            next_start = find_sentence_boundary(text, next_start, 30);
        }
        
        start = next_start;
        if (start >= text_length) break;
    }
    
    return chunks;
}

int main() {
    httplib::Server svr;
    
    // Health check endpoint
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        json response = {
            {"status", "healthy"},
            {"service", "cpp_backend"},
            {"version", "1.0.0"}
        };
        res.set_content(response.dump(), "application/json");
    });
    
    // Main processing endpoint
    svr.Post("/process", [](const httplib::Request& req, httplib::Response& res) {
        // Enable CORS
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "POST, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type");
        
        try {
            auto body = json::parse(req.body);
            
            if (!body.contains("text")) {
                res.status = 400;
                json error = {{"error", "Missing 'text' field"}};
                res.set_content(error.dump(), "application/json");
                return;
            }
            
            std::string text = body["text"];
            int chunk_size = body.value("chunk_size", 1000);
            int overlap = body.value("overlap", 100);
            
            std::string reason;
            bool garbage = is_garbage(text, reason);
            
            json response;
            response["is_garbage"] = garbage;
            
            if (garbage) {
                response["reason"] = reason;
                response["chunks"] = json::array();
                response["cleaned_text"] = "";
                response["stats"] = {
                    {"original_length", text.length()},
                    {"cleaned_length", 0},
                    {"chunks_count", 0}
                };
            } else {
                std::string cleaned = clean_markdown(text);
                auto chunks = chunk_text(cleaned, chunk_size, overlap);
                
                response["reason"] = "";
                response["chunks"] = chunks;
                response["cleaned_text"] = cleaned;
                response["stats"] = {
                    {"original_length", text.length()},
                    {"cleaned_length", cleaned.length()},
                    {"chunks_count", chunks.size()}
                };
            }
            
            res.set_content(response.dump(), "application/json");
            
        } catch (const json::exception& e) {
            res.status = 400;
            json error = {{"error", "Invalid JSON: " + std::string(e.what())}};
            res.set_content(error.dump(), "application/json");
        } catch (const std::exception& e) {
            res.status = 500;
            json error = {{"error", e.what()}};
            res.set_content(error.dump(), "application/json");
        }
    });
    
    // CORS preflight
    svr.Options("/process", [](const httplib::Request&, httplib::Response& res) {
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "POST, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type");
        res.status = 204;
    });
    
    std::cout << "C++ Backend starting on 0.0.0.0:8080..." << std::endl;
    svr.listen("0.0.0.0", 8080);
    
    return 0;
}
