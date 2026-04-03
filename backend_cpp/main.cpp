#include "third_party/httplib.h"
#include "third_party/json.hpp"

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

using json = nlohmann::json;

namespace {

bool is_text_like(unsigned char c) {
    return std::isalnum(c) || c >= 128;
}

bool is_garbage(const std::string& text) {
    if (text.empty()) {
        return true;
    }

    int letters_digits = 0;
    int special_chars = 0;
    bool has_space = false;

    for (unsigned char c : text) {
        if (std::isspace(c)) {
            has_space = true;
            continue;
        }

        if (is_text_like(c)) {
            letters_digits++;
        } else {
            special_chars++;
        }
    }

    if (!has_space) {
        return true;
    }

    return special_chars > letters_digits;
}

std::string clean_markdown(const std::string& text) {
    std::string cleaned;
    cleaned.reserve(text.size());

    bool in_code_block = false;
    bool line_start = true;

    for (size_t i = 0; i < text.size(); ++i) {
        if (i + 2 < text.size() && text[i] == '`' && text[i + 1] == '`' && text[i + 2] == '`') {
            in_code_block = !in_code_block;
            i += 2;
            continue;
        }

        if (in_code_block) {
            continue;
        }

        char c = text[i];

        if (line_start && (c == '#' || c == '-' || c == '*' || c == '>')) {
            while (i < text.size() && (text[i] == '#' || text[i] == '-' || text[i] == '*' || text[i] == '>' || text[i] == ' ')) {
                ++i;
            }
            if (i >= text.size()) {
                break;
            }
            c = text[i];
        }

        if (c == '`' || c == '*' || c == '_' || c == '[' || c == ']') {
            continue;
        }

        if (c == '\n' || c == '\r' || c == '\t') {
            c = ' ';
        }

        cleaned.push_back(c);
        line_start = (c == ' ');
    }

    std::string normalized;
    normalized.reserve(cleaned.size());
    bool prev_space = true;

    for (unsigned char c : cleaned) {
        if (std::isspace(c)) {
            if (!prev_space) {
                normalized.push_back(' ');
            }
            prev_space = true;
        } else {
            normalized.push_back(static_cast<char>(c));
            prev_space = false;
        }
    }

    if (!normalized.empty() && normalized.back() == ' ') {
        normalized.pop_back();
    }

    return normalized;
}

std::vector<std::string> chunk_text(const std::string& text, int chunk_size = 1000, int overlap = 100) {
    std::vector<std::string> chunks;
    if (text.empty()) {
        return chunks;
    }

    const int n = static_cast<int>(text.size());
    int start = 0;

    while (start < n) {
        int end = std::min(start + chunk_size, n);
        int length = end - start;

        if (length > 0) {
            chunks.push_back(text.substr(start, length));
        }

        if (end == n) {
            break;
        }

        start = end - overlap;
        if (start < 0) {
            start = 0;
        }
    }

    return chunks;
}

}  // namespace

int main() {
    httplib::Server server;

    server.Post("/process", [](const httplib::Request& req, httplib::Response& res) {
        try {
            json body = json::parse(req.body);

            if (!body.contains("text") || !body["text"].is_string()) {
                res.status = 400;
                res.set_content(json{{"error", "Field 'text' is required and must be string"}}.dump(), "application/json");
                return;
            }

            const std::string text = body["text"].get<std::string>();
            const bool garbage = is_garbage(text);

            json response;
            response["is_garbage"] = garbage;

            if (garbage) {
                response["chunks"] = json::array();
            } else {
                const std::string cleaned = clean_markdown(text);
                response["chunks"] = chunk_text(cleaned, 1000, 100);
            }

            res.set_content(response.dump(), "application/json");
        } catch (const json::exception& e) {
            res.status = 400;
            res.set_content(json{{"error", std::string("Invalid JSON: ") + e.what()}}.dump(), "application/json");
        } catch (const std::exception& e) {
            res.status = 500;
            res.set_content(json{{"error", e.what()}}.dump(), "application/json");
        }
    });

    server.listen("0.0.0.0", 8080);
    return 0;
}
