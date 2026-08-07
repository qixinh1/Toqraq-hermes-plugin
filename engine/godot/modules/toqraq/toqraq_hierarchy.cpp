// SPDX-License-Identifier: MIT

#include "toqraq_hierarchy.h"

#include "toqraq_json.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"

#include "core/io/json.h"
#include "core/templates/hash_set.h"
#include "scene/main/node.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace {

constexpr int MAX_DEPTH = 16;
constexpr int MAX_FILTER_TYPES = 32;
constexpr int MAX_PAGE_ENTRIES = 256;
constexpr int MAX_SCAN_NODES = 16384;
constexpr int MAX_RETAINED_CURSORS = 64;
constexpr const char *KNOWN_KEYS[] = {
	"root", "depth", "name_contains", "native_types", "revision", "cursor", "limit"
};

struct HierarchyQuery {
	String root;
	int depth = 0;
	String name_contains;
	Array native_types;
	String revision;
	String cursor;
	int limit = 0;
	String query_key;
};

struct PendingNode {
	Node *node = nullptr;
	int depth = 0;
};

bool _known_keys_only(const Dictionary &p_params) {
	const Array keys = p_params.keys();
	for (int index = 0; index < keys.size(); index++) {
		if (keys[index].get_type() != Variant::STRING) {
			return false;
		}
		bool known = false;
		for (const char *key : KNOWN_KEYS) {
			known = known || keys[index] == key;
		}
		if (!known) {
			return false;
		}
	}
	return p_params.has("depth") && p_params.has("native_types") && p_params.has("limit");
}

bool _read_optional_token(const Dictionary &p_params, const char *p_key, String &r_value) {
	const Variant *value = p_params.getptr(p_key);
	if (value == nullptr || value->get_type() == Variant::NIL) {
		r_value.clear();
		return true;
	}
	if (value->get_type() != Variant::STRING || !toqraq_is_observation_token(*value)) {
		return false;
	}
	r_value = *value;
	return true;
}

bool _read_query(const Dictionary &p_params, HierarchyQuery &r_query) {
	if (!_known_keys_only(p_params) || !_read_optional_token(p_params, "root", r_query.root) ||
			!_read_optional_token(p_params, "revision", r_query.revision) ||
			!_read_optional_token(p_params, "cursor", r_query.cursor)) {
		return false;
	}
	const Variant *depth = p_params.getptr("depth");
	const Variant *types = p_params.getptr("native_types");
	const Variant *limit = p_params.getptr("limit");
	int64_t depth_value = 0;
	int64_t limit_value = 0;
	if (depth == nullptr || types == nullptr || limit == nullptr ||
			!toqraq_read_json_integer(*depth, depth_value) ||
			depth_value < 0 || depth_value > MAX_DEPTH ||
			!toqraq_read_json_integer(*limit, limit_value) ||
			limit_value < 1 || limit_value > MAX_PAGE_ENTRIES || types->get_type() != Variant::ARRAY) {
		return false;
	}
	r_query.depth = depth_value;
	r_query.limit = limit_value;
	r_query.native_types = *types;
	if (r_query.native_types.size() > MAX_FILTER_TYPES) {
		return false;
	}
	HashSet<String> unique_types;
	for (int index = 0; index < r_query.native_types.size(); index++) {
		if (r_query.native_types[index].get_type() != Variant::STRING ||
				!toqraq_is_observation_label(r_query.native_types[index], 256)) {
			return false;
		}
		unique_types.insert(r_query.native_types[index]);
	}
	if (unique_types.size() != r_query.native_types.size()) {
		return false;
	}
	const Variant *name = p_params.getptr("name_contains");
	if (name != nullptr && name->get_type() != Variant::NIL) {
		if (name->get_type() != Variant::STRING || !toqraq_is_observation_label(*name, 256)) {
			return false;
		}
		r_query.name_contains = *name;
	}
	if (!r_query.cursor.is_empty() && r_query.revision.is_empty()) {
		return false;
	}
	Dictionary identity;
	identity["root"] = r_query.root;
	identity["depth"] = r_query.depth;
	identity["name_contains"] = r_query.name_contains;
	identity["native_types"] = r_query.native_types;
	r_query.query_key = JSON::stringify(identity);
	return true;
}

bool _matches(Node *p_node, const HierarchyQuery &p_query) {
	if (!p_query.name_contains.is_empty() && String(p_node->get_name()).findn(p_query.name_contains) < 0) {
		return false;
	}
	if (p_query.native_types.is_empty()) {
		return true;
	}
	const String native_type = p_node->get_class();
	for (int index = 0; index < p_query.native_types.size(); index++) {
		if (p_query.native_types[index] == native_type) {
			return true;
		}
	}
	return false;
}

Dictionary _entry(Node *p_node, ToqraqObservationState &p_state) {
	Dictionary entry;
	entry["reference"] = p_state.reference_for(p_node);
	entry["display_name"] = String(p_node->get_name());
	entry["native_type"] = p_node->get_class();
	Node *parent = p_node->get_parent();
	entry["parent"] = parent != nullptr && parent != SceneTree::get_singleton()->get_root() ?
			Variant(p_state.reference_for(parent)) : Variant();
	entry["child_count"] = p_node->get_child_count();
	entry["component_type_count"] = 0;
	entry["component_types"] = Array();
	entry["components_truncated"] = false;
	Array extensions;
	Node *owner = p_node->get_owner();
	if (owner != nullptr) {
		Dictionary fact;
		fact["kind"] = "reference";
		fact["field_id"] = "godot.scene.owner";
		fact["value"] = p_state.reference_for(owner);
		extensions.push_back(fact);
	}
	entry["extensions"] = extensions;
	return entry;
}

} // namespace

ToqraqHierarchyReader::ToqraqHierarchyReader(ToqraqObservationState &p_state) :
		state(p_state) {}

ToqraqFeatureResult ToqraqHierarchyReader::read(const Dictionary &p_params) {
	HierarchyQuery query;
	if (!_read_query(p_params, query)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	const String current_revision = state.hierarchy();
	if (!query.revision.is_empty() && query.revision != current_revision) {
		return toqraq_feature_error("perception.stale", "conflict");
	}
	int matched_offset = 0;
	if (!query.cursor.is_empty()) {
		const CursorState *cursor = cursors.getptr(query.cursor);
		if (cursor == nullptr || cursor->revision != current_revision || cursor->query_key != query.query_key) {
			return toqraq_feature_error("perception.stale", "conflict");
		}
		matched_offset = cursor->matched_offset;
		cursors.erase(query.cursor);
	}
	SceneTree *tree = SceneTree::get_singleton();
	Node *root = query.root.is_empty() ? tree->get_current_scene() : Object::cast_to<Node>(state.resolve(query.root));
	if (root == nullptr || !root->is_inside_tree()) {
		return toqraq_feature_error("perception.object_not_found", "not_found");
	}
	Vector<PendingNode> pending;
	pending.push_back({ root, 0 });
	Array entries;
	int matched = 0;
	int scanned = 0;
	bool has_more = false;
	while (!pending.is_empty() && scanned < MAX_SCAN_NODES) {
		const PendingNode item = pending[pending.size() - 1];
		pending.resize(pending.size() - 1);
		scanned++;
		if (item.depth < query.depth) {
			for (int child = item.node->get_child_count() - 1; child >= 0; child--) {
				pending.push_back({ item.node->get_child(child), item.depth + 1 });
			}
		}
		if (!_matches(item.node, query)) {
			continue;
		}
		if (matched++ < matched_offset) {
			continue;
		}
		if (entries.size() == query.limit) {
			has_more = true;
			break;
		}
		if (!toqraq_is_observation_label(String(item.node->get_name()), 256) ||
				!toqraq_is_observation_label(item.node->get_class(), 256)) {
			return toqraq_feature_error("perception.capability_unavailable", "unavailable");
		}
		entries.push_back(_entry(item.node, state));
	}
	if (!pending.is_empty() && !has_more && scanned >= MAX_SCAN_NODES) {
		return toqraq_feature_error("perception.capability_unavailable", "unavailable");
	}
	String next;
	if (has_more) {
		if (cursors.size() >= MAX_RETAINED_CURSORS) {
			cursors.clear();
		}
		next = "hierarchy-cursor-" + itos(next_cursor++);
		CursorState cursor;
		cursor.revision = current_revision;
		cursor.query_key = query.query_key;
		cursor.matched_offset = matched_offset + entries.size();
		cursors.insert(next, cursor);
	}
	Dictionary result;
	result["revision"] = current_revision;
	result["observed_at_unix_ms"] = toqraq_observed_at_unix_ms();
	result["entries"] = entries;
	result["truncated"] = has_more;
	result["next_cursor"] = has_more ? Variant(next) : Variant();
	return toqraq_feature_success(result);
}

void ToqraqHierarchyReader::invalidate() {
	cursors.clear();
}
