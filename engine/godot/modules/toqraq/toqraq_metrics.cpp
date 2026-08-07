// SPDX-License-Identifier: MIT

#include "toqraq_metrics.h"

#include "toqraq_json.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"

#include "core/math/math_funcs.h"
#include "core/os/os.h"
#include "core/templates/hash_set.h"
#include "main/performance.h"

namespace {

constexpr int MAX_GROUPS = 16;
constexpr int MAX_NAMES = 64;
constexpr int MAX_SAMPLES = 128;
constexpr const char *KNOWN_KEYS[] = { "groups", "names", "revision", "limit" };

struct MetricDefinition {
	const char *name;
	const char *unit;
	Performance::Monitor first;
	Performance::Monitor second;
	bool integer;
};

constexpr MetricDefinition METRICS[] = {
	{ "toqraq.performance.fps", "toqraq.unit.frames_per_second", Performance::TIME_FPS, Performance::MONITOR_MAX, false },
	{ "toqraq.performance.process_seconds", "toqraq.unit.seconds", Performance::TIME_PROCESS, Performance::MONITOR_MAX, false },
	{ "toqraq.performance.physics_seconds", "toqraq.unit.seconds", Performance::TIME_PHYSICS_PROCESS, Performance::MONITOR_MAX, false },
	{ "godot.rendering.draw_calls", "toqraq.unit.count", Performance::RENDER_TOTAL_DRAW_CALLS_IN_FRAME, Performance::MONITOR_MAX, true },
	{ "godot.physics.active_bodies", "toqraq.unit.count", Performance::PHYSICS_2D_ACTIVE_OBJECTS, Performance::PHYSICS_3D_ACTIVE_OBJECTS, true },
	{ "godot.memory.static_bytes", "toqraq.unit.bytes", Performance::MEMORY_STATIC, Performance::MONITOR_MAX, true },
	{ "godot.objects.nodes", "toqraq.unit.count", Performance::OBJECT_NODE_COUNT, Performance::MONITOR_MAX, true },
	{ "godot.audio.output_latency_seconds", "toqraq.unit.seconds", Performance::AUDIO_OUTPUT_LATENCY, Performance::MONITOR_MAX, false },
};

struct MetricsQuery {
	Array groups;
	Array names;
	String revision;
	int limit = 0;
};

bool _known_keys_only(const Dictionary &p_params) {
	const Array keys = p_params.keys();
	for (int index = 0; index < keys.size(); index++) {
		bool known = false;
		for (const char *key : KNOWN_KEYS) {
			known = known || keys[index] == key;
		}
		if (!known) {
			return false;
		}
	}
	return p_params.has("groups") && p_params.has("names") && p_params.has("limit");
}

bool _read_selection(const Variant *p_value, int p_maximum, Array &r_values) {
	if (p_value == nullptr || p_value->get_type() != Variant::ARRAY) {
		return false;
	}
	r_values = *p_value;
	if (r_values.size() > p_maximum) {
		return false;
	}
	HashSet<String> unique;
	for (int index = 0; index < r_values.size(); index++) {
		if (r_values[index].get_type() != Variant::STRING || !toqraq_is_namespaced_id(r_values[index])) {
			return false;
		}
		unique.insert(r_values[index]);
	}
	return unique.size() == r_values.size();
}

bool _read_query(const Dictionary &p_params, MetricsQuery &r_query) {
	if (!_known_keys_only(p_params) || !_read_selection(p_params.getptr("groups"), MAX_GROUPS, r_query.groups) ||
			!_read_selection(p_params.getptr("names"), MAX_NAMES, r_query.names) ||
			(r_query.groups.is_empty() && r_query.names.is_empty())) {
		return false;
	}
	const Variant *limit = p_params.getptr("limit");
	int64_t limit_value = 0;
	if (limit == nullptr || !toqraq_read_json_integer(*limit, limit_value) ||
			limit_value < 1 || limit_value > MAX_SAMPLES) {
		return false;
	}
	r_query.limit = limit_value;
	const Variant *revision = p_params.getptr("revision");
	if (revision != nullptr && revision->get_type() != Variant::NIL) {
		if (revision->get_type() != Variant::STRING || !toqraq_is_observation_token(*revision)) {
			return false;
		}
		r_query.revision = *revision;
	}
	return true;
}

bool _selected(const String &p_name, const MetricsQuery &p_query) {
	for (int index = 0; index < p_query.names.size(); index++) {
		if (p_query.names[index] == p_name) {
			return true;
		}
	}
	for (int index = 0; index < p_query.groups.size(); index++) {
		const String group = p_query.groups[index];
		if (p_name == group || p_name.begins_with(group + ".")) {
			return true;
		}
	}
	return false;
}

bool _supported_selection(const String &p_selection, bool p_group) {
	for (const MetricDefinition &metric : METRICS) {
		const String name = metric.name;
		if ((!p_group && name == p_selection) ||
				(p_group && (name == p_selection || name.begins_with(p_selection + ".")))) {
			return true;
		}
	}
	return false;
}

Dictionary _sample(const MetricDefinition &p_metric, Performance *p_performance, int64_t p_observed_at) {
	double value = p_performance->get_monitor(p_metric.first);
	if (p_metric.second != Performance::MONITOR_MAX) {
		value += p_performance->get_monitor(p_metric.second);
	}
	Dictionary sample;
	sample["name"] = p_metric.name;
	sample["unit"] = p_metric.unit;
	sample["observed_at_unix_ms"] = p_observed_at;
	if (p_metric.integer) {
		sample["kind"] = "integer";
		sample["value"] = CLAMP((int64_t)value, -9007199254740991LL, 9007199254740991LL);
	} else {
		sample["kind"] = "number";
		sample["value"] = Math::is_finite(value) ? value : 0.0;
	}
	return sample;
}

} // namespace

ToqraqMetricsReader::ToqraqMetricsReader(ToqraqObservationState &p_state) :
		state(p_state) {}

ToqraqFeatureResult ToqraqMetricsReader::read(const Dictionary &p_params) {
	MetricsQuery query;
	if (!_read_query(p_params, query)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	if (!query.revision.is_empty() && query.revision != state.metrics()) {
		return toqraq_feature_error("perception.stale", "conflict");
	}
	Performance *performance = Performance::get_singleton();
	if (performance == nullptr) {
		return toqraq_feature_error("perception.capability_unavailable", "unavailable");
	}
	const uint64_t started = OS::get_singleton()->get_ticks_usec();
	const int64_t observed_at = toqraq_observed_at_unix_ms();
	Array samples;
	int total_count = 0;
	for (const MetricDefinition &metric : METRICS) {
		if (!_selected(metric.name, query)) {
			continue;
		}
		total_count++;
		if (samples.size() < query.limit) {
			samples.push_back(_sample(metric, performance, observed_at));
		}
	}
	Array unavailable;
	for (int index = 0; index < query.names.size(); index++) {
		if (!_supported_selection(query.names[index], false)) {
			Dictionary value;
			value["selection_id"] = query.names[index];
			value["reason"] = "unsupported";
			unavailable.push_back(value);
		}
	}
	for (int index = 0; index < query.groups.size(); index++) {
		if (!_supported_selection(query.groups[index], true) && unavailable.size() < MAX_NAMES) {
			Dictionary value;
			value["selection_id"] = query.groups[index];
			value["reason"] = "unsupported";
			unavailable.push_back(value);
		}
	}
	Dictionary result;
	result["revision"] = state.metrics();
	result["observed_at_unix_ms"] = observed_at;
	result["samples"] = samples;
	result["total_count"] = total_count;
	result["truncated"] = total_count > samples.size();
	result["unavailable"] = unavailable;
	result["collection_duration_microseconds"] =
			(int64_t)(OS::get_singleton()->get_ticks_usec() - started);
	return toqraq_feature_success(result);
}
