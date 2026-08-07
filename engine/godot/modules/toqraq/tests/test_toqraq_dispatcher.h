// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_dispatcher.h"
#include "../toqraq_limits.h"

#include "core/io/json.h"
#include "scene/main/scene_tree.h"
#include "tests/test_macros.h"

namespace TestToqraqDispatcher {

String rpc_request(const String &p_id, const String &p_method, const Dictionary &p_params) {
	Dictionary request;
	request["jsonrpc"] = "2.0";
	request["id"] = p_id;
	request["method"] = p_method;
	request["params"] = p_params;
	return JSON::stringify(request);
}

bool messages_contain(const Vector<ToqraqOutboundMessage> &p_messages, const String &p_text) {
	for (const ToqraqOutboundMessage &message : p_messages) {
		if (message.text.contains(p_text)) {
			return true;
		}
	}
	return false;
}

Vector<ToqraqOutboundMessage> execute_request(
		ToqraqDispatcher &p_dispatcher,
		const String &p_id,
		const String &p_method,
		const Dictionary &p_params) {
	REQUIRE(p_dispatcher.submit_text(rpc_request(p_id, p_method, p_params)));
	p_dispatcher.poll();
	return p_dispatcher.poll();
}

TEST_CASE("[Toqraq] cancellation owns one terminal error and independent acknowledgement") {
	ToqraqDispatcher dispatcher;
	Dictionary metrics;
	Array groups;
	groups.push_back("toqraq.performance");
	metrics["groups"] = groups;
	metrics["names"] = Array();
	metrics["revision"] = Variant();
	metrics["limit"] = 8;
	REQUIRE(dispatcher.submit_text(rpc_request("host-1", "toqraq.metrics.read", metrics)));
	Dictionary cancel;
	cancel["target_request_id"] = "host-1";
	REQUIRE(dispatcher.submit_text(rpc_request("host-2", "toqraq.request.cancel", cancel)));
	const Vector<ToqraqOutboundMessage> messages = dispatcher.poll();
	CHECK(messages_contain(messages, "request.cancelled"));
	CHECK(messages_contain(messages, "requested"));
	CHECK_FALSE(messages_contain(messages, "toqraq.performance.fps"));
}

TEST_CASE("[Toqraq] request identities are strictly increasing and never reused") {
	ToqraqDispatcher dispatcher;
	Dictionary params;
	params["paused"] = true;
	CHECK(dispatcher.submit_text(rpc_request("host-2", "toqraq.simulation.set_paused", params)));
	CHECK_FALSE(dispatcher.submit_text(rpc_request("host-2", "toqraq.simulation.set_paused", params)));
	dispatcher.clear();
}

TEST_CASE("[Toqraq] ordinary work and cancellation occupy separate bounded slots") {
	ToqraqDispatcher dispatcher;
	Dictionary metrics;
	Array groups;
	groups.push_back("toqraq.performance");
	metrics["groups"] = groups;
	metrics["names"] = Array();
	metrics["revision"] = Variant();
	metrics["limit"] = 1;
	for (int index = 1; index <= ToqraqLimits::MAX_IN_FLIGHT_REQUESTS; index++) {
		REQUIRE(dispatcher.submit_text(rpc_request(
				"host-" + itos(index), "toqraq.metrics.read", metrics)));
	}
	Dictionary cancel;
	cancel["target_request_id"] = "host-1";
	const int cancel_request = ToqraqLimits::MAX_IN_FLIGHT_REQUESTS + 1;
	REQUIRE(dispatcher.submit_text(rpc_request(
			"host-" + itos(cancel_request), "toqraq.request.cancel", cancel)));
	cancel["target_request_id"] = "host-2";
	CHECK_FALSE(dispatcher.submit_text(rpc_request(
			"host-" + itos(cancel_request + 1), "toqraq.request.cancel", cancel)));
}

TEST_CASE("[SceneTree][Toqraq] successful mutation emits bounded state invalidation after its response") {
	ToqraqDispatcher dispatcher;
	const bool original_pause = SceneTree::get_singleton()->is_paused();
	Dictionary params;
	params["paused"] = !original_pause;
	REQUIRE(dispatcher.submit_text(rpc_request("host-1", "toqraq.simulation.set_paused", params)));
	dispatcher.poll();
	const Vector<ToqraqOutboundMessage> messages = dispatcher.poll();
	CHECK(messages_contain(messages, "simulation_revision"));
	CHECK(messages_contain(messages, "toqraq.state.changed"));
	CHECK(messages_contain(messages, "simulation"));
	Dictionary restore;
	restore["paused"] = original_pause;
	REQUIRE(dispatcher.submit_text(rpc_request("host-2", "toqraq.simulation.set_paused", restore)));
	dispatcher.poll();
	dispatcher.poll();
}

TEST_CASE("[SceneTree][Toqraq] host JSON integers reach scene-bound numeric feature fields") {
	ToqraqDispatcher dispatcher;
	Dictionary hierarchy;
	hierarchy["root"] = Variant();
	hierarchy["depth"] = 4;
	hierarchy["name_contains"] = Variant();
	hierarchy["native_types"] = Array();
	hierarchy["revision"] = Variant();
	hierarchy["cursor"] = Variant();
	hierarchy["limit"] = 64;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-1", "toqraq.hierarchy.read", hierarchy),
			"bridge.params_invalid"));

	Dictionary objects;
	Array references;
	references.push_back("object-missing");
	Array fields;
	fields.push_back("properties");
	objects["references"] = references;
	objects["fields"] = fields;
	objects["revision"] = Variant();
	objects["per_value_max_bytes"] = 1024;
	objects["total_value_max_bytes"] = 16384;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-2", "toqraq.object.read", objects),
			"bridge.params_invalid"));

	Dictionary diagnostics;
	diagnostics["source_ids"] = Array();
	diagnostics["severities"] = Array();
	diagnostics["revision"] = Variant();
	diagnostics["cursor"] = Variant();
	diagnostics["limit"] = 32;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-3", "toqraq.diagnostics.read", diagnostics),
			"bridge.params_invalid"));

	Dictionary metrics;
	Array groups;
	groups.push_back("toqraq.performance");
	metrics["groups"] = groups;
	metrics["names"] = Array();
	metrics["revision"] = Variant();
	metrics["limit"] = 8;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-4", "toqraq.metrics.read", metrics),
			"bridge.params_invalid"));

	Dictionary step;
	step["frame_count"] = 2;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-5", "toqraq.simulation.step", step),
			"bridge.params_invalid"));
}

TEST_CASE("[Toqraq] host JSON integers reach frame-capture numeric fields") {
	ToqraqDispatcher dispatcher;
	Dictionary maximum_size;
	maximum_size["width"] = 64;
	maximum_size["height"] = 64;
	Dictionary frame;
	frame["maximum_size"] = maximum_size;
	frame["scaling"] = "contain";
	frame["maximum_bytes"] = 1048576;
	CHECK_FALSE(messages_contain(
			execute_request(dispatcher, "host-1", "toqraq.frame.capture", frame),
			"bridge.params_invalid"));
}

} // namespace TestToqraqDispatcher
