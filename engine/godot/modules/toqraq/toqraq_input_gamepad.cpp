// SPDX-License-Identifier: MIT

#include "toqraq_input_gamepad.h"

#include "toqraq_input_contract.h"
#include "toqraq_json.h"

#include "core/input/input.h"
#include "core/input/input_event.h"

namespace {

using namespace ToqraqInputContract;

JoyButton _joy_button(const String &p_name) {
	return p_name == "south" ? JoyButton::A : p_name == "east" ? JoyButton::B : p_name == "west" ? JoyButton::X :
			p_name == "north" ? JoyButton::Y : p_name == "left_bumper" ? JoyButton::LEFT_SHOULDER :
			p_name == "right_bumper" ? JoyButton::RIGHT_SHOULDER : p_name == "select" ? JoyButton::BACK :
			p_name == "start" ? JoyButton::START : p_name == "left_stick" ? JoyButton::LEFT_STICK :
			p_name == "right_stick" ? JoyButton::RIGHT_STICK : p_name == "dpad_up" ? JoyButton::DPAD_UP :
			p_name == "dpad_down" ? JoyButton::DPAD_DOWN : p_name == "dpad_left" ? JoyButton::DPAD_LEFT :
			p_name == "dpad_right" ? JoyButton::DPAD_RIGHT : p_name == "home" ? JoyButton::GUIDE :
			p_name == "touchpad" ? JoyButton::TOUCHPAD : JoyButton::INVALID;
}

JoyAxis _joy_axis(const String &p_name) {
	return p_name == "left_x" ? JoyAxis::LEFT_X : p_name == "left_y" ? JoyAxis::LEFT_Y :
			p_name == "right_x" ? JoyAxis::RIGHT_X : p_name == "right_y" ? JoyAxis::RIGHT_Y : JoyAxis::INVALID;
}

} // namespace

ToqraqInputDispatchResult toqraq_dispatch_gamepad_input(const Dictionary &p_params) {
	constexpr const char *keys[] = { "device_slot", "events" };
	int device;
	const Variant *events_value = p_params.getptr("events");
	if (!toqraq_has_exact_keys(p_params, keys, 2) || !read_slot(p_params, "device_slot", 15, device) ||
			events_value == nullptr || events_value->get_type() != Variant::ARRAY) {
		return invalid();
	}
	const Array events = *events_value;
	if (events.size() < 1 || events.size() > MAX_EVENTS) {
		return invalid();
	}
	Vector<Ref<InputEvent>> mapped;
	for (int index = 0; index < events.size(); index++) {
		if (events[index].get_type() != Variant::DICTIONARY) {
			return invalid();
		}
		const Dictionary item = events[index];
		String kind;
		if (!read_string(item, "kind", kind)) {
			return invalid();
		}
		if (kind == "axis") {
			constexpr const char *event_keys[] = { "kind", "axis", "value" };
			String axis_name;
			double value;
			if (!toqraq_has_exact_keys(item, event_keys, 3) || !read_string(item, "axis", axis_name) ||
					!read_float(item, "value", -1.0, 1.0, value)) {
				return invalid();
			}
			const JoyAxis axis = _joy_axis(axis_name);
			if (axis == JoyAxis::INVALID) {
				return invalid();
			}
			Ref<InputEventJoypadMotion> event;
			event.instantiate();
			event->set_device(device);
			event->set_axis(axis);
			event->set_axis_value((float)value);
			mapped.push_back(event);
		} else if (kind == "button") {
			constexpr const char *event_keys[] = { "kind", "button", "pressed", "value" };
			String button_name;
			bool pressed;
			double value;
			if (!toqraq_has_exact_keys(item, event_keys, 4) || !read_string(item, "button", button_name) ||
					!read_bool(item, "pressed", pressed) || !read_float(item, "value", 0.0, 1.0, value) ||
					pressed != (value > 0.0)) {
				return invalid();
			}
			if (button_name == "left_trigger" || button_name == "right_trigger") {
				Ref<InputEventJoypadMotion> event;
				event.instantiate();
				event->set_device(device);
				event->set_axis(button_name == "left_trigger" ? JoyAxis::TRIGGER_LEFT : JoyAxis::TRIGGER_RIGHT);
				event->set_axis_value((float)value);
				mapped.push_back(event);
			} else {
				const JoyButton button = _joy_button(button_name);
				if (button == JoyButton::INVALID) {
					return invalid();
				}
				Ref<InputEventJoypadButton> event;
				event.instantiate();
				event->set_device(device);
				event->set_button_index(button);
				event->set_pressed(pressed);
				event->set_pressure((float)value);
				mapped.push_back(event);
			}
		} else {
			return invalid();
		}
	}
	if (!commit(mapped)) {
		return rejected("input_unavailable");
	}
	return success(events.size());
}
