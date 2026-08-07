// SPDX-License-Identifier: MIT

#include "toqraq_protocol.h"

#include "toqraq_identity.h"
#include "toqraq_json.h"
#include "toqraq_limits.h"

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"
#include "core/variant/variant.h"

namespace {

constexpr const char *JSON_RPC_VERSION = "2.0";
constexpr const char *HANDSHAKE_ID = "handshake-1";
constexpr const char *HANDSHAKE_METHOD = "toqraq.handshake";
constexpr const char *BRIDGE_ID = "toqraq.godot.bridge";
constexpr const char *BRIDGE_PROTOCOL = "1.0";
constexpr int MAX_ERROR_FIELDS = 32;
constexpr int MAX_ERROR_KEY_CHARACTERS = 64;
constexpr int MAX_ERROR_STRING_CHARACTERS = 512;
constexpr int MAX_ERROR_SEQUENCE_ITEMS = 32;
constexpr int MAX_ERROR_DEPTH = 4;
constexpr int MAX_ERROR_NODES = 128;
struct HandshakeErrorContract {
	int64_t rpc_code;
	const char *data_code;
	const char *category;
	const char *message;
};

constexpr HandshakeErrorContract HANDSHAKE_ERRORS[] = {
	{ -32700, "bridge.json_invalid", "invalid", "Parse error" },
	{ -32600, "bridge.request_invalid", "invalid", "Invalid Request" },
	{ -32601, "bridge.method_not_found", "invalid", "Method not found" },
	{ -32602, "bridge.params_invalid", "invalid", "Invalid params" },
	{ -32001, "bridge.handshake_mismatch", "unauthenticated", "Handshake mismatch" },
	{ -32002, "bridge.message_too_large", "invalid", "Message too large" },
};

bool _validate_error_value(const Variant &p_value, int p_depth, int &r_nodes);

bool _validate_error_mapping(const Dictionary &p_value, int p_depth, int &r_nodes) {
	if (p_depth > MAX_ERROR_DEPTH || p_value.size() > MAX_ERROR_FIELDS) {
		return false;
	}
	const Array keys = p_value.keys();
	for (int index = 0; index < keys.size(); index++) {
		if (++r_nodes > MAX_ERROR_NODES || keys[index].get_type() != Variant::STRING) {
			return false;
		}
		const String key = keys[index];
		if (key.is_empty() || key.length() > MAX_ERROR_KEY_CHARACTERS || !key.is_valid_string()) {
			return false;
		}
		const Variant *value = p_value.getptr(keys[index]);
		if (value == nullptr || !_validate_error_value(*value, p_depth + 1, r_nodes)) {
			return false;
		}
	}
	return true;
}

bool _validate_error_value(const Variant &p_value, int p_depth, int &r_nodes) {
	if (p_depth > MAX_ERROR_DEPTH) {
		return false;
	}
	switch (p_value.get_type()) {
		case Variant::NIL:
		case Variant::BOOL:
			return true;
		case Variant::INT: {
			const int64_t value = p_value;
			return value >= -ToqraqLimits::MAX_SAFE_INTEGER && value <= ToqraqLimits::MAX_SAFE_INTEGER;
		}
		case Variant::FLOAT: {
			const double value = p_value;
			return Math::is_finite(value) &&
					(Math::floor(value) != value || (value >= -ToqraqLimits::MAX_SAFE_INTEGER && value <= ToqraqLimits::MAX_SAFE_INTEGER));
		}
		case Variant::STRING: {
			const String value = p_value;
			return value.length() <= MAX_ERROR_STRING_CHARACTERS && value.is_valid_string();
		}
		case Variant::DICTIONARY:
			return _validate_error_mapping(p_value, p_depth, r_nodes);
		case Variant::ARRAY: {
			const Array value = p_value;
			if (value.size() > MAX_ERROR_SEQUENCE_ITEMS) {
				return false;
			}
			for (int index = 0; index < value.size(); index++) {
				if (++r_nodes > MAX_ERROR_NODES || !_validate_error_value(value[index], p_depth + 1, r_nodes)) {
					return false;
				}
			}
			return true;
		}
		default:
			return false;
	}
}

bool _is_uuid4(const String &p_value) {
	if (p_value.length() != 36 || p_value[8] != '-' || p_value[13] != '-' ||
			p_value[14] != '4' || p_value[18] != '-' || p_value[23] != '-' ||
			(p_value[19] != '8' && p_value[19] != '9' && p_value[19] != 'a' && p_value[19] != 'b')) {
		return false;
	}
	for (int index = 0; index < p_value.length(); index++) {
		if (index == 8 || index == 13 || index == 18 || index == 23) {
			continue;
		}
		const char32_t character = p_value[index];
		if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'))) {
			return false;
		}
	}
	return true;
}

const HandshakeErrorContract *_find_error_contract(int64_t p_rpc_code) {
	for (const HandshakeErrorContract &contract : HANDSHAKE_ERRORS) {
		if (contract.rpc_code == p_rpc_code) {
			return &contract;
		}
	}
	return nullptr;
}

bool _has_success_keys(const Dictionary &p_value) {
	return p_value.size() == 3 && p_value.has("jsonrpc") && p_value.has("id") && p_value.has("result");
}

bool _has_error_keys(const Dictionary &p_value) {
	return p_value.size() == 3 && p_value.has("jsonrpc") && p_value.has("id") && p_value.has("error");
}

bool _validate_owner(const Variant &p_value, const ToqraqLaunchData &p_launch) {
	if (p_value.get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary owner = p_value;
	const Variant *session = owner.getptr("session_id");
	const Variant *revision = owner.getptr("run_revision");
	int64_t revision_value = 0;
	return owner.size() == 2 && session != nullptr && revision != nullptr && session->get_type() == Variant::STRING &&
			String(*session) == p_launch.session_id && toqraq_read_json_integer(*revision, revision_value) &&
			revision_value == p_launch.run_revision;
}

bool _validate_capabilities(const Variant &p_value) {
	if (p_value.get_type() != Variant::ARRAY) {
		return false;
	}
	const Array actual = p_value;
	const Array expected = ToqraqIdentity::capabilities();
	if (actual.size() != expected.size()) {
		return false;
	}
	for (int index = 0; index < actual.size(); index++) {
		if (actual[index].get_type() != Variant::STRING || actual[index] != expected[index]) {
			return false;
		}
	}
	return true;
}

bool _validate_limits(const Variant &p_value) {
	if (p_value.get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary limits = p_value;
	const Variant *text = limits.getptr("max_text_message_bytes");
	const Variant *binary = limits.getptr("max_binary_transfer_bytes");
	const Variant *requests = limits.getptr("max_in_flight_requests");
	if (limits.size() != 3 || text == nullptr || binary == nullptr || requests == nullptr) {
		return false;
	}
	int64_t text_value = 0;
	int64_t binary_value = 0;
	int64_t request_value = 0;
	if (!toqraq_read_json_integer(*text, text_value) || !toqraq_read_json_integer(*binary, binary_value) ||
			!toqraq_read_json_integer(*requests, request_value)) {
		return false;
	}
	return text_value >= 4096 && text_value <= ToqraqLimits::MAX_TEXT_MESSAGE_BYTES &&
			binary_value >= 1 && binary_value <= ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES &&
			request_value >= 1 && request_value <= ToqraqLimits::MAX_IN_FLIGHT_REQUESTS;
}

bool _validate_success(const Dictionary &p_root, const ToqraqLaunchData &p_launch) {
	const Variant *result_value = p_root.getptr("result");
	if (result_value == nullptr || result_value->get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary result = *result_value;
	const Variant *owner = result.getptr("owner");
	const Variant *protocol = result.getptr("protocol");
	const Variant *capabilities = result.getptr("capabilities");
	const Variant *limits = result.getptr("limits");
	return result.size() == 4 && owner != nullptr && protocol != nullptr && capabilities != nullptr && limits != nullptr &&
			protocol->get_type() == Variant::STRING && String(*protocol) == BRIDGE_PROTOCOL &&
			_validate_owner(*owner, p_launch) && _validate_capabilities(*capabilities) && _validate_limits(*limits);
}

bool _validate_error(const Dictionary &p_root) {
	const Variant *error_value = p_root.getptr("error");
	if (error_value == nullptr || error_value->get_type() != Variant::DICTIONARY) {
		return false;
	}
	const Dictionary error = *error_value;
	const Variant *code = error.getptr("code");
	const Variant *message = error.getptr("message");
	const Variant *data_value = error.getptr("data");
	if (error.size() != 3 || code == nullptr || message == nullptr || data_value == nullptr ||
			message->get_type() != Variant::STRING ||
			String(*message).is_empty() || String(*message).length() > 64 || data_value->get_type() != Variant::DICTIONARY) {
		return false;
	}
	int64_t rpc_code = 0;
	if (!toqraq_read_json_integer(*code, rpc_code)) {
		return false;
	}
	const HandshakeErrorContract *contract = _find_error_contract(rpc_code);
	if (contract == nullptr || String(*message) != contract->message) {
		return false;
	}
	const Dictionary data = *data_value;
	const Variant *data_code = data.getptr("code");
	const Variant *category = data.getptr("category");
	const Variant *parameters_value = data.getptr("parameters");
	const Variant *details_value = data.getptr("details");
	const Variant *trace_id = data.getptr("trace_id");
	if (data.size() != 5 || data_code == nullptr || category == nullptr || parameters_value == nullptr ||
			details_value == nullptr || trace_id == nullptr || data_code->get_type() != Variant::STRING ||
			category->get_type() != Variant::STRING || parameters_value->get_type() != Variant::DICTIONARY ||
			details_value->get_type() != Variant::DICTIONARY || trace_id->get_type() != Variant::STRING ||
			String(*data_code) != contract->data_code || String(*category) != contract->category || !_is_uuid4(*trace_id)) {
		return false;
	}
	int parameter_nodes = 0;
	int detail_nodes = 0;
	return _validate_error_mapping(*parameters_value, 0, parameter_nodes) &&
			_validate_error_mapping(*details_value, 0, detail_nodes);
}

} // namespace

String toqraq_encode_handshake_request(const ToqraqLaunchData &p_launch) {
	Dictionary limits;
	limits["max_text_message_bytes"] = ToqraqLimits::MAX_TEXT_MESSAGE_BYTES;
	limits["max_binary_transfer_bytes"] = ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES;
	limits["max_in_flight_requests"] = ToqraqLimits::MAX_IN_FLIGHT_REQUESTS;

	Dictionary parameters;
	parameters["credential"] = p_launch.credential;
	parameters["session_id"] = p_launch.session_id;
	parameters["run_revision"] = p_launch.run_revision;
	parameters["engine_id"] = "godot";
	parameters["engine_version"] = ToqraqIdentity::engine_version();
	parameters["build_id"] = ToqraqIdentity::build_id();
	parameters["distribution_id"] = ToqraqIdentity::distribution_id();
	parameters["platform"] = ToqraqIdentity::platform();
	parameters["architecture"] = ToqraqIdentity::architecture();
	parameters["bridge_id"] = BRIDGE_ID;
	parameters["protocol"] = BRIDGE_PROTOCOL;
	parameters["capabilities"] = ToqraqIdentity::capabilities();
	parameters["limits"] = limits;

	Dictionary request;
	request["jsonrpc"] = JSON_RPC_VERSION;
	request["id"] = HANDSHAKE_ID;
	request["method"] = HANDSHAKE_METHOD;
	request["params"] = parameters;
	return JSON::stringify(request);
}

ToqraqHandshakeDecision toqraq_decode_handshake_response(const String &p_json, const ToqraqLaunchData &p_launch) {
	Variant root_value;
	if (!toqraq_decode_bounded_json(p_json, ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, root_value) ||
			root_value.get_type() != Variant::DICTIONARY) {
		return ToqraqHandshakeDecision::INVALID;
	}
	const Dictionary root = root_value;
	const Variant *version = root.getptr("jsonrpc");
	const Variant *request_id = root.getptr("id");
	if (version == nullptr || request_id == nullptr || version->get_type() != Variant::STRING ||
			request_id->get_type() != Variant::STRING || String(*version) != JSON_RPC_VERSION || String(*request_id) != HANDSHAKE_ID) {
		return ToqraqHandshakeDecision::INVALID;
	}
	if (_has_success_keys(root)) {
		return _validate_success(root, p_launch) ? ToqraqHandshakeDecision::ACCEPTED : ToqraqHandshakeDecision::INVALID;
	}
	if (_has_error_keys(root)) {
		return _validate_error(root) ? ToqraqHandshakeDecision::REJECTED : ToqraqHandshakeDecision::INVALID;
	}
	return ToqraqHandshakeDecision::INVALID;
}
