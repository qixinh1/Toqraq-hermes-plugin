// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_json.h"
#include "../toqraq_limits.h"
#include "../toqraq_rpc.h"

#include "core/io/json.h"
#include "tests/test_macros.h"

namespace TestToqraqRpc {

String request(const String &p_id, const String &p_method, const Variant &p_params = Dictionary()) {
	Dictionary value;
	value["jsonrpc"] = "2.0";
	value["id"] = p_id;
	value["method"] = p_method;
	value["params"] = p_params;
	return JSON::stringify(value);
}

TEST_CASE("[Toqraq] post-auth request decoder accepts only exact host envelopes") {
	ToqraqRpcRequest decoded;
	CHECK(toqraq_decode_rpc_request(
			request("host-1", "toqraq.hierarchy.read"), decoded) == ToqraqRpcDecodeStatus::ACCEPTED);
	CHECK(decoded.id == "host-1");
	CHECK(decoded.sequence == 1);
	CHECK(decoded.method == ToqraqRpcMethod::HIERARCHY_READ);
	CHECK(toqraq_decode_rpc_request(
			request("host-01", "toqraq.hierarchy.read"), decoded) == ToqraqRpcDecodeStatus::FATAL);
	CHECK(toqraq_decode_rpc_request(
			request("host-9007199254740992", "toqraq.hierarchy.read"), decoded) == ToqraqRpcDecodeStatus::FATAL);
	CHECK(toqraq_decode_rpc_request(
			request("host-2", "toqraq.unknown"), decoded) == ToqraqRpcDecodeStatus::METHOD_NOT_FOUND);
	CHECK(toqraq_decode_rpc_request(
			request("host-3", "toqraq.metrics.read", Array()), decoded) == ToqraqRpcDecodeStatus::PARAMS_INVALID);
	CHECK(toqraq_decode_rpc_request(
			"{\"jsonrpc\":\"2.0\",\"id\":\"host-4\",\"id\":\"host-5\",\"method\":\"toqraq.metrics.read\",\"params\":{}}",
			decoded) == ToqraqRpcDecodeStatus::FATAL);
}

TEST_CASE("[Toqraq] post-auth decoder recognizes every common method") {
	const char *methods[] = {
		"toqraq.hierarchy.read", "toqraq.object.read", "toqraq.diagnostics.read",
		"toqraq.metrics.read", "toqraq.frame.capture", "toqraq.simulation.set_paused",
		"toqraq.simulation.step", "toqraq.input.semantic", "toqraq.input.keyboard",
		"toqraq.input.pointer", "toqraq.input.text", "toqraq.input.gamepad",
		"toqraq.request.cancel"
	};
	for (int index = 0; index < 13; index++) {
		ToqraqRpcRequest decoded;
		CHECK(toqraq_decode_rpc_request(
				request("host-" + itos(index + 1), methods[index]), decoded) == ToqraqRpcDecodeStatus::ACCEPTED);
	}
}

TEST_CASE("[Toqraq] RPC encoders keep exact success error and notification shapes") {
	Dictionary result;
	result["accepted_event_count"] = 1;
	Ref<JSON> parser;
	parser.instantiate();
	CHECK(parser->parse(toqraq_encode_rpc_success("host-1", result)) == OK);
	Dictionary success = parser->get_data();
	CHECK(success.size() == 3);
	CHECK(success["id"] == "host-1");
	CHECK(Dictionary(success["result"]).size() == 1);

	CHECK(parser->parse(toqraq_encode_rpc_error(
			"host-2", -32800, "request.cancelled", "conflict")) == OK);
	Dictionary error = parser->get_data();
	Dictionary error_value = error["error"];
	Dictionary data = error_value["data"];
	CHECK((int64_t)error_value["code"] == -32800);
	CHECK(error_value["message"] == "Request cancelled");
	CHECK(data["code"] == "request.cancelled");
	CHECK(data["category"] == "conflict");
	CHECK(Dictionary(data["parameters"]).is_empty());
	CHECK(Dictionary(data["details"]).is_empty());

	Array families;
	families.push_back("frame");
	families.push_back("simulation");
	CHECK(parser->parse(toqraq_encode_state_changed(families)) == OK);
	Dictionary notification = parser->get_data();
	CHECK(notification.size() == 3);
	CHECK(!notification.has("id"));
}

TEST_CASE("[Toqraq] bounded JSON rejects non-finite duplicate and excessive shapes") {
	Variant decoded;
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":NaN}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":1,\"value\":2}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":\"\\u0000\"}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":\"\\ud800\"}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":9007199254740992}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK_FALSE(toqraq_decode_bounded_json(
			"{\"value\":-9007199254740992}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	CHECK(toqraq_decode_bounded_json(
			"{\"value\":9007199254740991}", ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
	String nested = "0";
	for (int index = 0; index < 18; index++) {
		nested = "[" + nested + "]";
	}
	CHECK_FALSE(toqraq_decode_bounded_json(nested, ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, decoded));
}

} // namespace TestToqraqRpc
