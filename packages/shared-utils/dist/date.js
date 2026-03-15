"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toISOString = toISOString;
exports.nowISO = nowISO;
function toISOString(date) {
    return date.toISOString();
}
function nowISO() {
    return new Date().toISOString();
}
//# sourceMappingURL=date.js.map