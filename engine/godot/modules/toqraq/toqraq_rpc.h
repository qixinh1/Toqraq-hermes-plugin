// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

enum class ToqraqRpcMethod {
	HIERARCHY_READ,
	OBJECT_READ,
	DIAGNOSTICS_READ,
	METRICS_READ,
	FRAME_CAPTURE,
	SIMULATION_SET_PAUSED,
	SIMULATION_STEP,
	INPUT_SEMANTIC,
	INPUT_KEYBOARD,
	INPUT_POINTER,
	INPUT_TEXT,
	INPUT_GAMEPAD,
	REQUEST_CANCEL,
};

enum class ToqraqRpcDecodeStatus {
	ACCEPTED,
	METHOD_NOT_FOUND,
	PARAMS_INVALID,
	FATAL,
};

struct ToqraqRpcRequest {
	String id;
	int64_t sequence = 0;
	String method_name;
	ToqraqRpcMethod method = ToqraqRpcMethod::HIERARCHY_READ;
	Dictionary params;
};

ToqraqRpcDecodeStatus toqraq_decode_rpc_request(const String &p_json, ToqraqRpcRequest &r_request);
bool toqraq_decode_host_request_id(const Variant &p_value, String &r_id, int64_t &r_sequence);
String toqraq_encode_rpc_success(const String &p_id, const Dictionary &p_result);
String toqraq_encode_rpc_error(
		const String &p_id,
		int p_rpc_code,
		const String &p_code,
		const String &p_category,
		const Dictionary &p_parameters = Dictionary(),
		const Dictionary &p_details = Dictionary());
String toqraq_encode_state_changed(const Array &p_families);
int64_t toqraq_observed_at_unix_ms();
