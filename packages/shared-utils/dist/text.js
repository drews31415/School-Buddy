"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.truncate = truncate;
exports.normalizeWhitespace = normalizeWhitespace;
function truncate(text, maxLength) {
    if (text.length <= maxLength)
        return text;
    return text.slice(0, maxLength - 3) + "...";
}
function normalizeWhitespace(text) {
    return text.replace(/\s+/g, " ").trim();
}
//# sourceMappingURL=text.js.map