// SPDX-License-Identifier: MIT

#include "toqraq_diagnostics.h"

#include "toqraq_diagnostic_log.h"
#include "toqraq_json.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"

#include "core/io/json.h"
#include "core/templates/hash_set.h"

namespace {

constexpr int MAX_SOURCE_FILTERS = 16;
constexpr int MAX_RECORDS = 200;
constexpr int MAX_RETAINED_CURSORS = 64;
constexpr const char *KNOWN_KEYS[] = { "source_ids", "severities", "revision", "cursor", "limit" };

struct DiagnosticsQuery {
	Array sources;
	Array severities;
	String revision;
	String cursor;
	String query_key;
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
	return p_params.has("source_ids") && p_params.has("severities") && p_params.has("limit");
}

bool _read_optional_token(const Dictionary &p_params, const char *p_key, String &r_value) {
	const Variant *value = p_params.getptr(p_key);
	if (value == nullptr || value->get_type() == Variant::NIL) {
		return true;
	}
	if (value->get_type() != Variant::STRING || !toqraq_is_observation_token(*value)) {
		return false;
	}
	r_value = *value;
	return true;
}

bool _valid_severity(const String &p_value) {
	return p_value == "debug" || p_value == "info" || p_value == "warning" ||
			p_value == "error" || p_value == "fatal";
}

bool _read_query(const Dictionary &p_params, DiagnosticsQuery &r_query) {
	if (!_known_keys_only(p_params) || !_read_optional_token(p_params, "revision", r_query.revision) ||
			!_read_optional_token(p_params, "cursor", r_query.cursor)) {
		return false;
	}
	const Variant *sources = p_params.getptr("source_ids");
	const Variant *severities = p_params.getptr("severities");
	const Variant *limit = p_params.getptr("limit");
	int64_t limit_value = 0;
	if (sources == nullptr || severities == nullptr || limit == nullptr ||
			sources->get_type() != Variant::ARRAY || severities->get_type() != Variant::ARRAY ||
			!toqraq_read_json_integer(*limit, limit_value) ||
			limit_value < 1 || limit_value > MAX_RECORDS) {
		return false;
	}
	r_query.sources = *sources;
	r_query.severities = *severities;
	r_query.limit = limit_value;
	if (r_query.sources.size() > MAX_SOURCE_FILTERS || r_query.severities.size() > 5) {
		return false;
	}
	HashSet<String> unique_sources;
	for (int index = 0; index < r_query.sources.size(); index++) {
		if (r_query.sources[index].get_type() != Variant::STRING ||
				!toqraq_is_namespaced_id(r_query.sources[index])) {
			return false;
		}
		unique_sources.insert(r_query.sources[index]);
	}
	HashSet<String> unique_severities;
	for (int index = 0; index < r_query.severities.size(); index++) {
		if (r_query.severities[index].get_type() != Variant::STRING ||
				!_valid_severity(r_query.severities[index])) {
			return false;
		}
		unique_severities.insert(r_query.severities[index]);
	}
	if (unique_sources.size() != r_query.sources.size() ||
			unique_severities.size() != r_query.severities.size() ||
			(!r_query.cursor.is_empty() && r_query.revision.is_empty())) {
		return false;
	}
	Dictionary identity;
	identity["source_ids"] = r_query.sources;
	identity["severities"] = r_query.severities;
	r_query.query_key = JSON::stringify(identity);
	return true;
}

bool _selected(const ToqraqDiagnosticRecord &p_record, const DiagnosticsQuery &p_query) {
	bool source_selected = p_query.sources.is_empty();
	for (int index = 0; index < p_query.sources.size(); index++) {
		source_selected = source_selected || p_query.sources[index] == p_record.source_id;
	}
	bool severity_selected = p_query.severities.is_empty();
	for (int index = 0; index < p_query.severities.size(); index++) {
		severity_selected = severity_selected || p_query.severities[index] == p_record.severity;
	}
	return source_selected && severity_selected;
}

Dictionary _wire_record(const ToqraqDiagnosticRecord &p_record) {
	Dictionary record;
	record["sequence"] = p_record.sequence;
	record["occurred_at_unix_ms"] = p_record.occurred_at_unix_ms;
	record["source_id"] = p_record.source_id;
	record["severity"] = p_record.severity;
	record["code"] = p_record.code;
	record["summary"] = p_record.summary;
	record["details"] = Array();
	if (p_record.resource.is_empty()) {
		record["location"] = Variant();
	} else {
		Dictionary location;
		location["resource"] = p_record.resource;
		location["line"] = p_record.line > 0 ? Variant(p_record.line) : Variant();
		location["column"] = Variant();
		record["location"] = location;
	}
	return record;
}

} // namespace

ToqraqDiagnosticsReader::ToqraqDiagnosticsReader(ToqraqObservationState &p_state) :
		state(p_state) {}

bool ToqraqDiagnosticsReader::_synchronize(uint64_t p_generation) {
	if (p_generation == last_generation) {
		return false;
	}
	last_generation = p_generation;
	cursors.clear();
	state.mark_diagnostics();
	return true;
}

bool ToqraqDiagnosticsReader::synchronize() {
	return _synchronize(ToqraqDiagnosticLog::generation());
}

ToqraqFeatureResult ToqraqDiagnosticsReader::read(const Dictionary &p_params) {
	DiagnosticsQuery query;
	if (!_read_query(p_params, query)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	uint64_t generation = 0;
	const Vector<ToqraqDiagnosticRecord> records = ToqraqDiagnosticLog::snapshot(generation);
	const bool changed = _synchronize(generation);
	const String revision = state.diagnostics();
	if (!query.revision.is_empty() && query.revision != revision) {
		return toqraq_feature_error("perception.stale", "conflict");
	}
	int offset = 0;
	if (!query.cursor.is_empty()) {
		const CursorState *cursor = cursors.getptr(query.cursor);
		if (cursor == nullptr || cursor->revision != revision || cursor->query_key != query.query_key) {
			return toqraq_feature_error("perception.stale", "conflict");
		}
		offset = cursor->matched_offset;
		cursors.erase(query.cursor);
	}
	Array selected;
	int matched = 0;
	bool has_more = false;
	for (const ToqraqDiagnosticRecord &record : records) {
		if (!_selected(record, query)) {
			continue;
		}
		if (matched++ < offset) {
			continue;
		}
		if (selected.size() == query.limit) {
			has_more = true;
			break;
		}
		selected.push_back(_wire_record(record));
	}
	String next;
	if (has_more) {
		if (cursors.size() >= MAX_RETAINED_CURSORS) {
			cursors.clear();
		}
		next = "diagnostics-cursor-" + itos(next_cursor++);
		CursorState cursor;
		cursor.revision = revision;
		cursor.query_key = query.query_key;
		cursor.matched_offset = offset + selected.size();
		cursors.insert(next, cursor);
	}
	Dictionary result;
	result["revision"] = revision;
	result["observed_at_unix_ms"] = toqraq_observed_at_unix_ms();
	result["records"] = selected;
	result["truncated"] = has_more;
	result["next_cursor"] = has_more ? Variant(next) : Variant();
	ToqraqFeatureResult response = toqraq_feature_success(result);
	if (changed) {
		response.changed_families.push_back("diagnostics");
	}
	return response;
}

void ToqraqDiagnosticsReader::clear() {
	cursors.clear();
	last_generation = 0;
}
