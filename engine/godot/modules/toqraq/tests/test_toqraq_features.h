// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_diagnostic_log.h"
#include "../toqraq_diagnostics.h"
#include "../toqraq_frame.h"
#include "../toqraq_hierarchy.h"
#include "../toqraq_limits.h"
#include "../toqraq_metrics.h"
#include "../toqraq_objects.h"
#include "../toqraq_observation_state.h"
#include "../toqraq_simulation.h"

#include "core/os/memory.h"
#include "core/string/print_string.h"
#include "main/performance.h"
#include "scene/main/scene_tree.h"
#include "tests/test_macros.h"

namespace TestToqraqFeatures {

struct DiagnosticLogScope {
	bool active = ToqraqDiagnosticLog::activate();
	~DiagnosticLogScope() {
		ToqraqDiagnosticLog::deactivate();
	}
};

Dictionary hierarchy_query(const String &p_root, int p_limit = 256) {
	Dictionary value;
	value["root"] = p_root;
	value["depth"] = 2;
	value["name_contains"] = Variant();
	value["native_types"] = Array();
	value["revision"] = Variant();
	value["cursor"] = Variant();
	value["limit"] = p_limit;
	return value;
}

TEST_CASE("[SceneTree][Toqraq] hierarchy and object readers expose opaque bounded live values") {
	SceneTree *tree = SceneTree::get_singleton();
	Node *fixture = memnew(Node);
	fixture->set_name("ToqraqFixture");
	Node *child = memnew(Node);
	child->set_name("Child");
	fixture->add_child(child);
	tree->get_root()->add_child(fixture);

	ToqraqObservationState state;
	state.observe_tree();
	const String root_reference = state.reference_for(fixture);
	ToqraqHierarchyReader hierarchy(state);
	ToqraqFeatureResult first = hierarchy.read(hierarchy_query(root_reference, 1));
	REQUIRE(first.succeeded);
	const Array first_entries = first.result["entries"];
	CHECK(first_entries.size() == 1);
	CHECK(bool(first.result["truncated"]));
	CHECK(String(Dictionary(first_entries[0])["reference"]).begins_with("object-"));

	Dictionary continued = hierarchy_query(root_reference, 1);
	continued["revision"] = first.result["revision"];
	continued["cursor"] = first.result["next_cursor"];
	ToqraqFeatureResult second = hierarchy.read(continued);
	REQUIRE(second.succeeded);
	CHECK(Array(second.result["entries"]).size() == 1);
	CHECK_FALSE(bool(second.result["truncated"]));

	Dictionary object_query;
	Array references;
	references.push_back(root_reference);
	object_query["references"] = references;
	Array fields;
	fields.push_back("properties");
	fields.push_back("components");
	fields.push_back("resources");
	fields.push_back("extensions");
	object_query["fields"] = fields;
	object_query["revision"] = Variant();
	object_query["per_value_max_bytes"] = 16384;
	object_query["total_value_max_bytes"] = ToqraqLimits::MAX_TEXT_MESSAGE_BYTES;
	ToqraqObjectReader objects(state);
	ToqraqFeatureResult snapshot = objects.read(object_query);
	REQUIRE(snapshot.succeeded);
	CHECK(snapshot.result["fields"] == fields);
	CHECK(Array(snapshot.result["objects"]).size() == 1);
	CHECK((int64_t)snapshot.result["value_bytes"] <= ToqraqLimits::MAX_TEXT_MESSAGE_BYTES);

	references[0] = "object-missing";
	object_query["references"] = references;
	ToqraqFeatureResult missing = objects.read(object_query);
	CHECK_FALSE(missing.succeeded);
	CHECK(missing.error_code == "perception.object_not_found");

	tree->get_root()->remove_child(fixture);
	memdelete(fixture);
}

TEST_CASE("[Toqraq] diagnostics and metrics apply wildcard and explicit selections") {
	DiagnosticLogScope diagnostic_log;
	CHECK(diagnostic_log.active);
	print_line("Toqraq diagnostic capture test.");
	ToqraqObservationState state;
	ToqraqDiagnosticsReader diagnostics(state);
	Dictionary diagnostic_query;
	diagnostic_query["source_ids"] = Array();
	diagnostic_query["severities"] = Array();
	diagnostic_query["revision"] = Variant();
	diagnostic_query["cursor"] = Variant();
	diagnostic_query["limit"] = 200;
	ToqraqFeatureResult diagnostic_page = diagnostics.read(diagnostic_query);
	REQUIRE(diagnostic_page.succeeded);
	CHECK(Array(diagnostic_page.result["records"]).size() >= 2);
	CHECK_FALSE(diagnostic_page.result.has("runtime"));

	ToqraqMetricsReader metrics(state);
	Dictionary metric_query;
	Array groups;
	groups.push_back("toqraq.performance");
	metric_query["groups"] = groups;
	metric_query["names"] = Array();
	metric_query["revision"] = Variant();
	metric_query["limit"] = 128;
	ToqraqFeatureResult metric_snapshot = metrics.read(metric_query);
	if (Performance::get_singleton() == nullptr) {
		CHECK_FALSE(metric_snapshot.succeeded);
		CHECK(metric_snapshot.error_code == "perception.capability_unavailable");
	} else {
		REQUIRE(metric_snapshot.succeeded);
		CHECK(Array(metric_snapshot.result["samples"]).size() >= 1);
		CHECK_FALSE(bool(metric_snapshot.result["truncated"]));

		groups.clear();
		groups.push_back("unknown.metrics");
		metric_query["groups"] = groups;
		ToqraqFeatureResult unavailable = metrics.read(metric_query);
		REQUIRE(unavailable.succeeded);
		CHECK(Array(unavailable.result["unavailable"]).size() == 1);
	}
}

TEST_CASE("[SceneTree][Toqraq] pause is desired-state idempotent and step requires pause") {
	SceneTree *tree = SceneTree::get_singleton();
	const bool original_pause = tree->is_paused();
	ToqraqObservationState state;
	ToqraqSimulationControl simulation(state);
	Dictionary pause;
	pause["paused"] = true;
	ToqraqFeatureResult first = simulation.set_paused(pause);
	REQUIRE(first.succeeded);
	CHECK(bool(first.result["paused"]));
	ToqraqFeatureResult second = simulation.set_paused(pause);
	REQUIRE(second.succeeded);
	CHECK_FALSE(bool(second.result["changed"]));

	Dictionary step;
	step["frame_count"] = 2;
	ToqraqStepStart started = simulation.start_step(step);
	CHECK(started.started);
	CHECK(simulation.is_stepping());
	simulation.cancel_step();
	CHECK_FALSE(simulation.is_stepping());
	tree->set_pause(original_pause);
}

TEST_CASE("[Toqraq] frame capture rejects malformed and over-negotiated work before capture") {
	ToqraqObservationState state;
	ToqraqFrameCapture frame(state);
	Dictionary query;
	Dictionary size;
	size["width"] = 960;
	size["height"] = 540;
	query["maximum_size"] = size;
	query["scaling"] = "contain";
	query["maximum_bytes"] = ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES + 1;
	ToqraqFeatureResult rejected = frame.capture(query);
	CHECK_FALSE(rejected.succeeded);
	CHECK(rejected.error_code == "bridge.params_invalid");
}

} // namespace TestToqraqFeatures
