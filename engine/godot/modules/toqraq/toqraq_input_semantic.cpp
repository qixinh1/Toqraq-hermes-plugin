// SPDX-License-Identifier: MIT

#include "toqraq_input_semantic.h"

#include "toqraq_input_contract.h"
#include "toqraq_json.h"

#include "core/input/input.h"
#include "core/input/input_event.h"
#include "core/input/input_map.h"
#include "core/string/char_utils.h"

namespace {

using namespace ToqraqInputContract;

bool _valid_action(const String &p_action) {
	if (!toqraq_is_observation_label(p_action, 256)) {
		return false;
	}
	bool visible = false;
	for (int index = 0; index < p_action.length(); index++) {
		visible |= !is_whitespace(p_action[index]);
	}
	return visible;
}

} // namespace

ToqraqInputDispatchResult toqraq_dispatch_semantic_input(const Dictionary &p_params) {
	Array events;
	if (!read_events(p_params, events)) {
		return invalid();
	}
	Vector<StringName> actions;
	Vector<Ref<InputEvent>> mapped;
	for (int index = 0; index < events.size(); index++) {
		if (events[index].get_type() != Variant::DICTIONARY) {
			return invalid();
		}
		const Dictionary item = events[index];
		constexpr const char *keys[] = { "action", "pressed", "strength" };
		String action;
		bool pressed;
		double strength;
		if (!toqraq_has_exact_keys(item, keys, 3) || !read_string(item, "action", action) || !_valid_action(action) ||
				!read_bool(item, "pressed", pressed) || !read_float(item, "strength", 0.0, 1.0, strength) ||
				pressed != (strength > 0.0)) {
			return invalid();
		}
		Ref<InputEventAction> event;
		event.instantiate();
		event->set_action(StringName(action));
		event->set_pressed(pressed);
		event->set_strength((float)strength);
		actions.push_back(StringName(action));
		mapped.push_back(event);
	}
	Input *input = Input::get_singleton();
	InputMap *input_map = InputMap::get_singleton();
	if (input == nullptr || input_map == nullptr) {
		return rejected("input_unavailable");
	}
	for (const StringName &action : actions) {
		if (!input_map->has_action(action)) {
			return rejected("action_unavailable");
		}
	}
	if (!commit(mapped)) {
		return rejected("input_unavailable");
	}
	return success(events.size());
}
