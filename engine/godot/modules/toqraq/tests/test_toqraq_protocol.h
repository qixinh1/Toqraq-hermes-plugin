// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_identity.h"
#include "../toqraq_limits.h"
#include "../toqraq_protocol.h"

#include "core/io/json.h"
#include "core/variant/dictionary.h"
#include "tests/test_macros.h"

namespace TestToqraqProtocol {

constexpr const char *CREDENTIAL = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

ToqraqLaunchData launch_data() {
	ToqraqLaunchData launch;
	launch.endpoint = "ws://127.0.0.1:32768/toqraq/bridge";
	launch.credential = CREDENTIAL;
	launch.session_id = "session-1";
	launch.run_revision = 7;
	return launch;
}

String success_response() {
	Dictionary owner;
	owner["session_id"] = "session-1";
	owner["run_revision"] = 7;
	Dictionary limits;
	limits["max_text_message_bytes"] = ToqraqLimits::MAX_TEXT_MESSAGE_BYTES;
	limits["max_binary_transfer_bytes"] = ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES;
	limits["max_in_flight_requests"] = ToqraqLimits::MAX_IN_FLIGHT_REQUESTS;
	Dictionary result;
	result["owner"] = owner;
	result["protocol"] = "1.0";
	result["capabilities"] = ToqraqIdentity::capabilities();
	result["limits"] = limits;
	Dictionary response;
	response["jsonrpc"] = "2.0";
	response["id"] = "handshake-1";
	response["result"] = result;
	return JSON::stringify(response);
}

TEST_CASE("[Toqraq] handshake request carries intrinsic and launch identity") {
	const ToqraqLaunchData launch = launch_data();
	Ref<JSON> parser;
	parser.instantiate();
	CHECK(parser->parse(toqraq_encode_handshake_request(launch)) == OK);
	const Dictionary request = parser->get_data();
	CHECK(request.size() == 4);
	CHECK(request["jsonrpc"] == "2.0");
	CHECK(request["id"] == "handshake-1");
	CHECK(request["method"] == "toqraq.handshake");
	const Dictionary parameters = request["params"];
	CHECK(parameters.size() == 13);
	CHECK(parameters["credential"] == CREDENTIAL);
	CHECK(parameters["session_id"] == "session-1");
	CHECK((int64_t)parameters["run_revision"] == 7);
	CHECK(parameters["engine_id"] == "godot");
	CHECK(parameters["engine_version"] == ToqraqIdentity::engine_version());
	CHECK(parameters["build_id"] == ToqraqIdentity::build_id());
	CHECK(parameters["distribution_id"] == ToqraqIdentity::distribution_id());
	CHECK(parameters["platform"] == ToqraqIdentity::platform());
	CHECK(parameters["architecture"] == ToqraqIdentity::architecture());
	CHECK(parameters["bridge_id"] == "toqraq.godot.bridge");
	CHECK(parameters["protocol"] == "1.0");
	CHECK(parameters["capabilities"] == ToqraqIdentity::capabilities());
	const Dictionary limits = parameters["limits"];
	CHECK(limits.size() == 3);
	CHECK((int64_t)limits["max_text_message_bytes"] == ToqraqLimits::MAX_TEXT_MESSAGE_BYTES);
	CHECK((int64_t)limits["max_binary_transfer_bytes"] == ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES);
	CHECK((int64_t)limits["max_in_flight_requests"] == ToqraqLimits::MAX_IN_FLIGHT_REQUESTS);
}

TEST_CASE("[Toqraq] handshake response is exact and duplicate-free") {
	const ToqraqLaunchData launch = launch_data();
	CHECK(toqraq_decode_handshake_response(success_response(), launch) == ToqraqHandshakeDecision::ACCEPTED);
	CHECK(toqraq_decode_handshake_response(
			"{\"jsonrpc\":\"2.0\",\"id\":\"handshake-1\",\"id\":\"handshake-1\",\"result\":{}}",
			launch) == ToqraqHandshakeDecision::INVALID);
	CHECK(toqraq_decode_handshake_response(
			"{\"jsonrpc\":\"2.0\",\"id\":\"other\",\"result\":{}}",
			launch) == ToqraqHandshakeDecision::INVALID);
}

TEST_CASE("[Toqraq] exact handshake error is terminal rejection") {
	const ToqraqLaunchData launch = launch_data();
	const String response =
			"{\"jsonrpc\":\"2.0\",\"id\":\"handshake-1\",\"error\":{"
			"\"code\":-32001,\"message\":\"Handshake mismatch\",\"data\":{"
			"\"code\":\"bridge.handshake_mismatch\",\"category\":\"unauthenticated\","
			"\"parameters\":{},\"details\":{},"
			"\"trace_id\":\"00000000-0000-4000-8000-000000000000\"}}}";
	CHECK(toqraq_decode_handshake_response(response, launch) == ToqraqHandshakeDecision::REJECTED);
	CHECK(toqraq_decode_handshake_response(
			response.replace("bridge.handshake_mismatch", "bridge.params_invalid"),
			launch) == ToqraqHandshakeDecision::INVALID);
	CHECK(toqraq_decode_handshake_response(
			response.replace("unauthenticated", "invalid"),
			launch) == ToqraqHandshakeDecision::INVALID);
	CHECK(toqraq_decode_handshake_response(
			response.replace("Handshake mismatch", "Invalid params"),
			launch) == ToqraqHandshakeDecision::INVALID);
	CHECK(toqraq_decode_handshake_response(
			response.replace("4000-8000", "3000-8000"),
			launch) == ToqraqHandshakeDecision::INVALID);
	CHECK(toqraq_decode_handshake_response(
			response.replace("\"parameters\":{}", "\"parameters\":{\"value\":[[[[[]]]]]}"),
			launch) == ToqraqHandshakeDecision::INVALID);
}

} // namespace TestToqraqProtocol
