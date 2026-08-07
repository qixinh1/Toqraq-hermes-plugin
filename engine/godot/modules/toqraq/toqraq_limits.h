// SPDX-License-Identifier: MIT

#pragma once

#include <cstdint>

namespace ToqraqLimits {

constexpr int MAX_TEXT_MESSAGE_BYTES = 262144;
constexpr int MAX_BINARY_PAYLOAD_BYTES = 32 << 20;
constexpr int TRANSFER_PREFIX_BYTES = 16;
constexpr int MAX_IN_FLIGHT_REQUESTS = 16;
constexpr int MAX_QUEUED_PACKETS = MAX_IN_FLIGHT_REQUESTS * 2 + 2;
constexpr int MAX_JSON_DEPTH = 16;
constexpr int MAX_JSON_NODES = 4096;
constexpr int MAX_JSON_COLLECTION_ITEMS = 256;
constexpr int64_t MAX_SAFE_INTEGER = 9007199254740991LL;

} // namespace ToqraqLimits
