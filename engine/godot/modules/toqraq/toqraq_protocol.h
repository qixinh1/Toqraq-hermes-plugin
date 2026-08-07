// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_launch.h"

#include "core/string/ustring.h"

enum class ToqraqHandshakeDecision {
	ACCEPTED,
	REJECTED,
	INVALID,
};

String toqraq_encode_handshake_request(const ToqraqLaunchData &p_launch);
ToqraqHandshakeDecision toqraq_decode_handshake_response(
		const String &p_json,
		const ToqraqLaunchData &p_launch);
