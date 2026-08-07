// SPDX-License-Identifier: MIT

#include "toqraq_input_contract.h"

#include "toqraq_json.h"

#include "core/input/input.h"
#include "core/input/input_map.h"

namespace ToqraqInputContract {

namespace {

constexpr const char *EVENTS_KEY[] = { "events" };

ToqraqInputDispatchResult _error(const String &p_code, const String &p_category, const String &p_reason = String()) {
	ToqraqInputDispatchResult value;
	value.handled = true;
	value.error_code = p_code;
	value.error_category = p_category;
	if (!p_reason.is_empty()) {
		value.error_details["reason"] = p_reason;
	}
	return value;
}

} // namespace

ToqraqInputDispatchResult invalid() {
	return _error("bridge.params_invalid", "invalid");
}

ToqraqInputDispatchResult rejected(const String &p_reason) {
	return _error("input.rejected", "conflict", p_reason);
}

ToqraqInputDispatchResult success(int p_count) {
	ToqraqInputDispatchResult value;
	value.handled = true;
	value.succeeded = true;
	value.result["accepted_event_count"] = p_count;
	return value;
}

bool read_bool(const Dictionary &p_value, const char *p_key, bool &r_value) {
	const Variant *field = p_value.getptr(p_key);
	if (field == nullptr || field->get_type() != Variant::BOOL) {
		return false;
	}
	r_value = *field;
	return true;
}

bool read_float(const Dictionary &p_value, const char *p_key, double p_minimum, double p_maximum, double &r_value) {
	const Variant *field = p_value.getptr(p_key);
	return field != nullptr && toqraq_read_json_float(*field, r_value) && r_value >= p_minimum && r_value <= p_maximum;
}

bool read_string(const Dictionary &p_value, const char *p_key, String &r_value) {
	const Variant *field = p_value.getptr(p_key);
	if (field == nullptr || field->get_type() != Variant::STRING) {
		return false;
	}
	r_value = *field;
	return r_value.is_valid_string();
}

bool read_slot(const Dictionary &p_value, const char *p_key, int p_maximum, int &r_value) {
	const Variant *field = p_value.getptr(p_key);
	int64_t value = 0;
	if (field == nullptr || !toqraq_read_json_integer(*field, value)) {
		return false;
	}
	if (value < 0 || value > p_maximum) {
		return false;
	}
	r_value = (int)value;
	return true;
}

bool read_events(const Dictionary &p_params, Array &r_events) {
	const Variant *events = p_params.getptr("events");
	if (!toqraq_has_exact_keys(p_params, EVENTS_KEY, 1) || events == nullptr || events->get_type() != Variant::ARRAY) {
		return false;
	}
	r_events = *events;
	return r_events.size() >= 1 && r_events.size() <= MAX_EVENTS;
}

bool commit(const Vector<Ref<InputEvent>> &p_events) {
	Input *input = Input::get_singleton();
	if (input == nullptr || InputMap::get_singleton() == nullptr) {
		return false;
	}
	for (const Ref<InputEvent> &event : p_events) {
		input->parse_input_event(event);
	}
	return true;
}

} // namespace ToqraqInputContract
