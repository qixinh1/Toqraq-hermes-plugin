// SPDX-License-Identifier: MIT

#include "toqraq_rpc.h"

#include "toqraq_json.h"
#include "toqraq_limits.h"

#include "core/io/json.h"
#include "core/os/os.h"

namespace {

constexpr const char *ROOT_KEYS[] = { "jsonrpc", "id", "method", "params" };
constexpr const char *JSON_RPC_VERSION = "2.0";
constexpr const char *STATE_CHANGED_METHOD = "toqraq.state.changed";

struct MethodEntry {
	const char *name;
	ToqraqRpcMethod method;
};

constexpr MethodEntry METHODS[] = {
	{ "toqraq.hierarchy.read", ToqraqRpcMethod::HIERARCHY_READ },
	{ "toqraq.object.read", ToqraqRpcMethod::OBJECT_READ },
	{ "toqraq.diagnostics.read", ToqraqRpcMethod::DIAGNOSTICS_READ },
	{ "toqraq.metrics.read", ToqraqRpcMethod::METRICS_READ },
	{ "toqraq.frame.capture", ToqraqRpcMethod::FRAME_CAPTURE },
	{ "toqraq.simulation.set_paused", ToqraqRpcMethod::SIMULATION_SET_PAUSED },
	{ "toqraq.simulation.step", ToqraqRpcMethod::SIMULATION_STEP },
	{ "toqraq.input.semantic", ToqraqRpcMethod::INPUT_SEMANTIC },
	{ "toqraq.input.keyboard", ToqraqRpcMethod::INPUT_KEYBOARD },
	{ "toqraq.input.pointer", ToqraqRpcMethod::INPUT_POINTER },
	{ "toqraq.input.text", ToqraqRpcMethod::INPUT_TEXT },
	{ "toqraq.input.gamepad", ToqraqRpcMethod::INPUT_GAMEPAD },
	{ "toqraq.request.cancel", ToqraqRpcMethod::REQUEST_CANCEL },
};

uint64_t trace_sequence = 0;

bool _decode_host_id(const Variant &p_value, String &r_id, int64_t &r_sequence) {
	if (p_value.get_type() != Variant::STRING) {
		return false;
	}
	const String value = p_value;
	if (!value.begins_with("host-") || value.length() < 6 || value.length() > 21) {
		return false;
	}
	const String digits = value.substr(5);
	if (digits[0] == '0') {
		return false;
	}
	int64_t sequence = 0;
	for (int index = 0; index < digits.length(); index++) {
		const char32_t character = digits[index];
		if (character < '0' || character > '9') {
			return false;
		}
		const int digit = character - '0';
		if (sequence > (ToqraqLimits::MAX_SAFE_INTEGER - digit) / 10) {
			return false;
		}
		sequence = sequence * 10 + digit;
	}
	r_id = value;
	r_sequence = sequence;
	return true;
}

bool _find_method(const String &p_name, ToqraqRpcMethod &r_method) {
	for (const MethodEntry &entry : METHODS) {
		if (p_name == entry.name) {
			r_method = entry.method;
			return true;
		}
	}
	return false;
}

String _trace_id() {
	trace_sequence++;
	const String suffix = String::num_uint64(trace_sequence, 16).pad_zeros(12).right(12);
	return "00000000-0000-4000-8000-" + suffix;
}

} // namespace

bool toqraq_decode_host_request_id(const Variant &p_value, String &r_id, int64_t &r_sequence) {
	return _decode_host_id(p_value, r_id, r_sequence);
}

ToqraqRpcDecodeStatus toqraq_decode_rpc_request(const String &p_json, ToqraqRpcRequest &r_request) {
	Variant decoded;
	if (!toqraq_decode_bounded_json(p_json, ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded) ||
			decoded.get_type() != Variant::DICTIONARY) {
		return ToqraqRpcDecodeStatus::FATAL;
	}
	const Dictionary root = decoded;
	const Variant *id = root.getptr("id");
	if (id == nullptr || !_decode_host_id(*id, r_request.id, r_request.sequence)) {
		return ToqraqRpcDecodeStatus::FATAL;
	}
	if (!toqraq_has_exact_keys(root, ROOT_KEYS, 4)) {
		return ToqraqRpcDecodeStatus::FATAL;
	}
	const Variant *version = root.getptr("jsonrpc");
	const Variant *method = root.getptr("method");
	const Variant *params = root.getptr("params");
	if (version == nullptr || method == nullptr || params == nullptr ||
			version->get_type() != Variant::STRING || String(*version) != JSON_RPC_VERSION ||
			method->get_type() != Variant::STRING) {
		return ToqraqRpcDecodeStatus::FATAL;
	}
	r_request.method_name = String(*method);
	if (!_find_method(r_request.method_name, r_request.method)) {
		return ToqraqRpcDecodeStatus::METHOD_NOT_FOUND;
	}
	if (params->get_type() != Variant::DICTIONARY) {
		return ToqraqRpcDecodeStatus::PARAMS_INVALID;
	}
	r_request.params = *params;
	return ToqraqRpcDecodeStatus::ACCEPTED;
}

String toqraq_encode_rpc_success(const String &p_id, const Dictionary &p_result) {
	Dictionary response;
	response["jsonrpc"] = JSON_RPC_VERSION;
	response["id"] = p_id;
	response["result"] = p_result;
	return JSON::stringify(response);
}

String toqraq_encode_rpc_error(
		const String &p_id,
		int p_rpc_code,
		const String &p_code,
		const String &p_category,
		const Dictionary &p_parameters,
		const Dictionary &p_details) {
	Dictionary data;
	data["code"] = p_code;
	data["category"] = p_category;
	data["parameters"] = p_parameters;
	data["details"] = p_details;
	data["trace_id"] = _trace_id();
	Dictionary error;
	error["code"] = p_rpc_code;
	error["message"] = p_rpc_code == -32601 ? "Method not found" :
			p_rpc_code == -32602 ? "Invalid params" :
			p_rpc_code == -32603 ? "Internal error" :
			p_rpc_code == -32800 ? "Request cancelled" : "Application error";
	error["data"] = data;
	Dictionary response;
	response["jsonrpc"] = JSON_RPC_VERSION;
	response["id"] = p_id;
	response["error"] = error;
	return JSON::stringify(response);
}

String toqraq_encode_state_changed(const Array &p_families) {
	Dictionary params;
	params["families"] = p_families;
	Dictionary notification;
	notification["jsonrpc"] = JSON_RPC_VERSION;
	notification["method"] = STATE_CHANGED_METHOD;
	notification["params"] = params;
	return JSON::stringify(notification);
}

int64_t toqraq_observed_at_unix_ms() {
	const double milliseconds = OS::get_singleton()->get_unix_time() * 1000.0;
	return CLAMP((int64_t)milliseconds, (int64_t)0, ToqraqLimits::MAX_SAFE_INTEGER);
}
