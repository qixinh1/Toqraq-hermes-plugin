// SPDX-License-Identifier: MIT

#include "toqraq_objects.h"

#include "toqraq_json.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"

#include "core/io/resource.h"
#include "core/math/math_funcs.h"
#include "core/templates/hash_set.h"
#include "scene/main/node.h"

namespace {

constexpr int MAX_REFERENCES = 64;
constexpr int MAX_PROPERTIES = 128;
constexpr int MAX_RESOURCES = 64;
constexpr int MAX_VALUE_BYTES = 16384;
constexpr int MAX_TOTAL_BYTES = 262144;
constexpr const char *KNOWN_KEYS[] = {
	"references", "fields", "revision", "per_value_max_bytes", "total_value_max_bytes"
};

struct ObjectQuery {
	Array references;
	Array fields;
	String revision;
	int per_value_bytes = 0;
	int total_value_bytes = 0;
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
	return p_params.has("references") && p_params.has("fields") &&
			p_params.has("per_value_max_bytes") && p_params.has("total_value_max_bytes");
}

bool _read_query(const Dictionary &p_params, ObjectQuery &r_query) {
	if (!_known_keys_only(p_params)) {
		return false;
	}
	const Variant *references = p_params.getptr("references");
	const Variant *fields = p_params.getptr("fields");
	const Variant *per_value = p_params.getptr("per_value_max_bytes");
	const Variant *total = p_params.getptr("total_value_max_bytes");
	int64_t per_value_integer = 0;
	int64_t total_integer = 0;
	if (references == nullptr || fields == nullptr || per_value == nullptr || total == nullptr ||
			references->get_type() != Variant::ARRAY || fields->get_type() != Variant::ARRAY ||
			!toqraq_read_json_integer(*per_value, per_value_integer) ||
			!toqraq_read_json_integer(*total, total_integer) || per_value_integer < 1 ||
			per_value_integer > MAX_VALUE_BYTES || total_integer < per_value_integer ||
			total_integer > MAX_TOTAL_BYTES) {
		return false;
	}
	r_query.references = *references;
	r_query.fields = *fields;
	r_query.per_value_bytes = per_value_integer;
	r_query.total_value_bytes = total_integer;
	if (r_query.references.is_empty() || r_query.references.size() > MAX_REFERENCES ||
			r_query.fields.is_empty() || r_query.fields.size() > 4) {
		return false;
	}
	HashSet<String> unique_references;
	for (int index = 0; index < r_query.references.size(); index++) {
		if (r_query.references[index].get_type() != Variant::STRING ||
				!toqraq_is_observation_token(r_query.references[index])) {
			return false;
		}
		unique_references.insert(r_query.references[index]);
	}
	if (unique_references.size() != r_query.references.size()) {
		return false;
	}
	HashSet<String> unique_fields;
	for (int index = 0; index < r_query.fields.size(); index++) {
		if (r_query.fields[index].get_type() != Variant::STRING) {
			return false;
		}
		const String field = r_query.fields[index];
		if (field != "properties" && field != "components" && field != "resources" && field != "extensions") {
			return false;
		}
		unique_fields.insert(field);
	}
	if (unique_fields.size() != r_query.fields.size()) {
		return false;
	}
	const Variant *revision = p_params.getptr("revision");
	if (revision != nullptr && revision->get_type() != Variant::NIL) {
		if (revision->get_type() != Variant::STRING || !toqraq_is_observation_token(*revision)) {
			return false;
		}
		r_query.revision = *revision;
	}
	return true;
}

bool _property_is_visible(const PropertyInfo &p_property) {
	return (p_property.usage & PROPERTY_USAGE_STORAGE) != 0 &&
			toqraq_is_observation_label(String(p_property.name), 256);
}

String _summary_for(const Variant &p_value) {
	switch (p_value.get_type()) {
		case Variant::ARRAY:
			return "<Array size=" + itos(Array(p_value).size()) + ">";
		case Variant::DICTIONARY:
			return "<Dictionary size=" + itos(Dictionary(p_value).size()) + ">";
		case Variant::PACKED_BYTE_ARRAY:
			return "<PackedByteArray size=" + itos(PackedByteArray(p_value).size()) + ">";
		default:
			return "<" + Variant::get_type_name(p_value.get_type()) + ">";
	}
}

bool _observed_value(
		const Variant &p_value,
		ToqraqObservationState &p_state,
		int p_per_value_budget,
		int p_total_remaining,
		Dictionary &r_value,
		int &r_text_bytes) {
	r_text_bytes = 0;
	switch (p_value.get_type()) {
		case Variant::NIL:
			r_value["kind"] = "null";
			return true;
		case Variant::BOOL:
			r_value["kind"] = "boolean";
			r_value["value"] = p_value;
			return true;
		case Variant::INT: {
			const int64_t integer = p_value;
			if (integer >= -9007199254740991LL && integer <= 9007199254740991LL) {
				r_value["kind"] = "integer";
				r_value["value"] = integer;
				return true;
			}
			break;
		}
		case Variant::FLOAT: {
			const double number = p_value;
			if (Math::is_finite(number)) {
				r_value["kind"] = "number";
				r_value["value"] = number;
				return true;
			}
			break;
		}
		case Variant::STRING: {
			const String text = p_value;
			const int bytes = text.utf8().length();
			if (text.is_valid_string() && text.find_char(0) < 0 && bytes <= p_per_value_budget && bytes <= p_total_remaining) {
				r_value["kind"] = "text";
				r_value["value"] = text;
				r_text_bytes = bytes;
				return true;
			}
			break;
		}
		case Variant::OBJECT: {
			Object *object = p_value;
			if (object == nullptr) {
				r_value["kind"] = "null";
			} else {
				r_value["kind"] = "reference";
				r_value["value"] = p_state.reference_for(object);
			}
			return true;
		}
		default:
			break;
	}
	const String summary = _summary_for(p_value);
	const int bytes = summary.utf8().length();
	if (bytes > p_per_value_budget || bytes > p_total_remaining || bytes > 1024) {
		return false;
	}
	r_value["kind"] = "summary";
	r_value["value"] = summary;
	r_text_bytes = bytes;
	return true;
}

Dictionary _property_group(
		Object *p_object,
		ToqraqObservationState &p_state,
		int p_per_value_budget,
		int p_total_budget,
		int &r_value_bytes) {
	List<PropertyInfo> properties;
	p_object->get_property_list(&properties);
	int total_count = 0;
	for (const PropertyInfo &property : properties) {
		total_count += _property_is_visible(property) ? 1 : 0;
	}
	Array items;
	for (const PropertyInfo &property : properties) {
		if (!_property_is_visible(property) || items.size() >= MAX_PROPERTIES) {
			continue;
		}
		bool valid = false;
		const Variant native_value = p_object->get(property.name, &valid);
		Dictionary value;
		int text_bytes = 0;
		if (!valid || !_observed_value(native_value, p_state, p_per_value_budget,
				p_total_budget - r_value_bytes, value, text_bytes)) {
			continue;
		}
		Dictionary item;
		item["name"] = String(property.name);
		item["native_type"] = Variant::get_type_name(property.type);
		item["value"] = value;
		items.push_back(item);
		r_value_bytes += text_bytes;
	}
	Dictionary group;
	group["kind"] = "properties";
	group["total_count"] = total_count;
	group["items"] = items;
	group["truncated"] = total_count > items.size();
	return group;
}

Dictionary _component_group() {
	Dictionary group;
	group["kind"] = "components";
	group["total_count"] = 0;
	group["items"] = Array();
	group["truncated"] = false;
	return group;
}

Dictionary _resource_group(Object *p_object, ToqraqObservationState &p_state) {
	List<PropertyInfo> properties;
	p_object->get_property_list(&properties);
	Array items;
	int total_count = 0;
	for (const PropertyInfo &property : properties) {
		if (!_property_is_visible(property) || property.type != Variant::OBJECT) {
			continue;
		}
		bool valid = false;
		Object *related = p_object->get(property.name, &valid);
		Resource *resource = valid ? Object::cast_to<Resource>(related) : nullptr;
		if (resource == nullptr) {
			continue;
		}
		total_count++;
		if (items.size() >= MAX_RESOURCES) {
			continue;
		}
		if (!toqraq_is_observation_label(resource->get_class(), 256)) {
			continue;
		}
		Dictionary item;
		item["reference"] = p_state.reference_for(resource);
		item["name"] = String(property.name);
		item["native_type"] = resource->get_class();
		items.push_back(item);
	}
	Dictionary group;
	group["kind"] = "resources";
	group["total_count"] = total_count;
	group["items"] = items;
	group["truncated"] = total_count > items.size();
	return group;
}

Dictionary _extension_group(Object *p_object) {
	Array items;
	Node *node = Object::cast_to<Node>(p_object);
	if (node != nullptr) {
		Dictionary fact;
		fact["kind"] = "boolean";
		fact["field_id"] = "godot.process.enabled";
		fact["value"] = node->can_process();
		items.push_back(fact);
	}
	Dictionary group;
	group["kind"] = "extensions";
	group["total_count"] = items.size();
	group["items"] = items;
	group["truncated"] = false;
	return group;
}

String _display_name(Object *p_object) {
	if (Node *node = Object::cast_to<Node>(p_object)) {
		return String(node->get_name());
	}
	if (Resource *resource = Object::cast_to<Resource>(p_object)) {
		const String name = resource->get_name();
		return name.is_empty() ? resource->get_class() : name;
	}
	return p_object->get_class();
}

} // namespace

ToqraqObjectReader::ToqraqObjectReader(ToqraqObservationState &p_state) :
		state(p_state) {}

ToqraqFeatureResult ToqraqObjectReader::read(const Dictionary &p_params) {
	ObjectQuery query;
	if (!_read_query(p_params, query)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	if (!query.revision.is_empty() && query.revision != state.objects()) {
		return toqraq_feature_error("perception.stale", "conflict");
	}
	Vector<Object *> resolved;
	for (int index = 0; index < query.references.size(); index++) {
		Object *object = state.resolve(query.references[index]);
		Node *node = Object::cast_to<Node>(object);
		if (object == nullptr || (node != nullptr && (!node->is_inside_tree() || node->is_queued_for_deletion()))) {
			return toqraq_feature_error("perception.object_not_found", "not_found");
		}
		resolved.push_back(object);
	}
	Array objects;
	int value_bytes = 0;
	for (int index = 0; index < resolved.size(); index++) {
		Object *object = resolved[index];
		const String display_name = _display_name(object);
		const String native_type = object->get_class();
		if (!toqraq_is_observation_label(display_name, 256) ||
				!toqraq_is_observation_label(native_type, 256)) {
			return toqraq_feature_error("perception.capability_unavailable", "unavailable");
		}
		Array groups;
		for (int field_index = 0; field_index < query.fields.size(); field_index++) {
			const String field = query.fields[field_index];
			if (field == "properties") {
				groups.push_back(_property_group(object, state, query.per_value_bytes,
						query.total_value_bytes, value_bytes));
			} else if (field == "components") {
				groups.push_back(_component_group());
			} else if (field == "resources") {
				groups.push_back(_resource_group(object, state));
			} else {
				groups.push_back(_extension_group(object));
			}
		}
		Dictionary value;
		value["reference"] = query.references[index];
		value["display_name"] = display_name;
		value["native_type"] = native_type;
		value["groups"] = groups;
		objects.push_back(value);
	}
	Dictionary result;
	result["revision"] = state.objects();
	result["observed_at_unix_ms"] = toqraq_observed_at_unix_ms();
	result["fields"] = query.fields;
	result["objects"] = objects;
	result["value_bytes"] = value_bytes;
	return toqraq_feature_success(result);
}
