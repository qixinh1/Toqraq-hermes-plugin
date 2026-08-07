// SPDX-License-Identifier: MIT

#include "toqraq_launch.h"

#include "toqraq_json.h"

#include "core/io/json.h"
#include "core/os/os.h"
#include "core/variant/dictionary.h"
#include "core/variant/variant.h"

#include <windows.h>

namespace {

constexpr const char *BRIDGE_ENVIRONMENT = "TOQRAQ_BRIDGE_URL";
constexpr const char *ENDPOINT_PREFIX = "ws://127.0.0.1:";
constexpr const char *ENDPOINT_PATH = "/toqraq/bridge";
constexpr int MAX_BOOTSTRAP_BYTES = 4096;
constexpr int MAX_SESSION_ID_BYTES = 512;
constexpr int64_t MAX_RUN_REVISION = 9007199254740991LL;

bool _is_lower_hex_credential(const String &p_value) {
	if (p_value.length() != 64) {
		return false;
	}
	for (int index = 0; index < p_value.length(); index++) {
		const char32_t character = p_value[index];
		if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'))) {
			return false;
		}
	}
	return true;
}

bool _is_session_id(const String &p_value) {
	if (p_value.is_empty() || !p_value.is_valid_string() || p_value.utf8().length() > MAX_SESSION_ID_BYTES) {
		return false;
	}
	for (int index = 0; index < p_value.length(); index++) {
		const char32_t character = p_value[index];
		if (character <= 0x1f || (character >= 0x7f && character <= 0x9f)) {
			return false;
		}
	}
	return true;
}

bool _read_private_pipe(Vector<uint8_t> &r_bytes) {
	HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
	if (input == nullptr || input == INVALID_HANDLE_VALUE) {
		return false;
	}
	const DWORD input_type = GetFileType(input) & ~FILE_TYPE_REMOTE;
	if (input_type != FILE_TYPE_PIPE) {
		SetStdHandle(STD_INPUT_HANDLE, nullptr);
		CloseHandle(input);
		return false;
	}

	r_bytes.resize(MAX_BOOTSTRAP_BYTES + 1);
	DWORD total = 0;
	bool complete = false;
	while (total < (DWORD)r_bytes.size()) {
		DWORD count = 0;
		const BOOL read = ReadFile(input, r_bytes.ptrw() + total, (DWORD)r_bytes.size() - total, &count, nullptr);
		if (!read) {
			complete = GetLastError() == ERROR_BROKEN_PIPE;
			break;
		}
		if (count == 0) {
			complete = true;
			break;
		}
		total += count;
	}
	const BOOL detached = SetStdHandle(STD_INPUT_HANDLE, nullptr);
	const BOOL closed = CloseHandle(input);
	if (!complete || !detached || !closed || total == 0 || total > MAX_BOOTSTRAP_BYTES) {
		r_bytes.fill(0);
		r_bytes.clear();
		return false;
	}
	r_bytes.resize((int)total);
	return true;
}

void _close_standard_input() {
	HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
	if (input == nullptr || input == INVALID_HANDLE_VALUE) {
		return;
	}
	SetStdHandle(STD_INPUT_HANDLE, nullptr);
	CloseHandle(input);
}

} // namespace

void ToqraqLaunchData::clear_credential() {
	credential.clear();
}

void ToqraqLaunchData::clear() {
	endpoint.clear();
	credential.clear();
	session_id.clear();
	run_revision = 0;
}

bool toqraq_is_bridge_endpoint(const String &p_endpoint) {
	if (!p_endpoint.begins_with(ENDPOINT_PREFIX) || !p_endpoint.ends_with(ENDPOINT_PATH)) {
		return false;
	}
	const int port_start = String(ENDPOINT_PREFIX).length();
	const int port_length = p_endpoint.length() - port_start - String(ENDPOINT_PATH).length();
	if (port_length < 1 || port_length > 5) {
		return false;
	}
	const String port_text = p_endpoint.substr(port_start, port_length);
	for (int index = 0; index < port_text.length(); index++) {
		if (port_text[index] < '0' || port_text[index] > '9') {
			return false;
		}
	}
	const int64_t port = port_text.to_int();
	return port >= 1 && port <= 65535 && String::num_int64(port) == port_text;
}

bool toqraq_parse_bootstrap(const String &p_json, ToqraqLaunchData &r_launch) {
	r_launch.clear();
	const int byte_length = p_json.utf8().length();
	if (byte_length < 1 || byte_length > MAX_BOOTSTRAP_BYTES || toqraq_count_json_members(p_json) != 3) {
		return false;
	}

	Ref<JSON> parser;
	parser.instantiate();
	if (parser->parse(p_json) != OK || parser->get_data().get_type() != Variant::DICTIONARY) {
		return false;
	}
	Dictionary document = parser->get_data();
	if (document.size() != 3) {
		return false;
	}
	const Variant *credential_value = document.getptr("credential");
	const Variant *session_value = document.getptr("session_id");
	const Variant *revision_value = document.getptr("run_revision");
	if (credential_value == nullptr || session_value == nullptr || revision_value == nullptr ||
			credential_value->get_type() != Variant::STRING || session_value->get_type() != Variant::STRING) {
		return false;
	}
	const String credential = *credential_value;
	const String session_id = *session_value;
	int64_t run_revision = 0;
	if (!_is_lower_hex_credential(credential) || !_is_session_id(session_id) ||
			!toqraq_read_json_integer(*revision_value, run_revision) || run_revision < 1 || run_revision > MAX_RUN_REVISION) {
		return false;
	}
	r_launch.credential = credential;
	r_launch.session_id = session_id;
	r_launch.run_revision = run_revision;
	document["credential"] = String();
	return true;
}

ToqraqActivationStatus toqraq_read_activation(ToqraqLaunchData &r_launch) {
	r_launch.clear();
	OS *os = OS::get_singleton();
	if (os == nullptr || !os->has_environment(BRIDGE_ENVIRONMENT)) {
		return ToqraqActivationStatus::DISABLED;
	}
	const String endpoint = os->get_environment(BRIDGE_ENVIRONMENT);
	if (!toqraq_is_bridge_endpoint(endpoint)) {
		_close_standard_input();
		return ToqraqActivationStatus::REJECTED;
	}
	Vector<uint8_t> bootstrap_bytes;
	if (!_read_private_pipe(bootstrap_bytes)) {
		return ToqraqActivationStatus::REJECTED;
	}
	String bootstrap_json;
	const Error decode_error = bootstrap_json.append_utf8((const char *)bootstrap_bytes.ptr(), bootstrap_bytes.size());
	bootstrap_bytes.fill(0);
	bootstrap_bytes.clear();
	if (decode_error != OK || !toqraq_parse_bootstrap(bootstrap_json, r_launch)) {
		bootstrap_json.clear();
		r_launch.clear();
		return ToqraqActivationStatus::REJECTED;
	}
	bootstrap_json.clear();
	r_launch.endpoint = endpoint;
	return ToqraqActivationStatus::READY;
}
