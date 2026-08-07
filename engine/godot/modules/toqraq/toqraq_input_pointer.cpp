// SPDX-License-Identifier: MIT

#include "toqraq_input_pointer.h"

#include "toqraq_input_contract.h"
#include "toqraq_json.h"

#include "core/input/input.h"
#include "core/input/input_event.h"
#include "core/math/math_funcs.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

namespace {

using namespace ToqraqInputContract;

enum class PointerEventKind {
	MOTION,
	BUTTON,
	WHEEL,
};

struct PointerEventValue {
	PointerEventKind kind = PointerEventKind::MOTION;
	double x = 0.0;
	double y = 0.0;
	double delta_x = 0.0;
	double delta_y = 0.0;
	MouseButton button = MouseButton::NONE;
	bool pressed = false;
};

MouseButton _pointer_button(const String &p_name) {
	return p_name == "primary" ? MouseButton::LEFT : p_name == "secondary" ? MouseButton::RIGHT :
			p_name == "middle" ? MouseButton::MIDDLE : p_name == "back" ? MouseButton::MB_XBUTTON1 :
			p_name == "forward" ? MouseButton::MB_XBUTTON2 : MouseButton::NONE;
}

int _mouse_device(int p_pointer_id) {
	return InputEvent::DEVICE_ID_MOUSE + p_pointer_id;
}

bool _decode_event(const Dictionary &p_item, bool p_normalized, PointerEventValue &r_value) {
	String kind;
	const double coordinate_maximum = p_normalized ? 1.0 : MAX_POINTER_VALUE;
	if (!read_string(p_item, "kind", kind) || !read_float(p_item, "x", 0.0, coordinate_maximum, r_value.x) ||
			!read_float(p_item, "y", 0.0, coordinate_maximum, r_value.y)) {
		return false;
	}
	if (kind == "motion") {
		constexpr const char *keys[] = { "kind", "x", "y", "delta_x", "delta_y" };
		r_value.kind = PointerEventKind::MOTION;
		return toqraq_has_exact_keys(p_item, keys, 5) &&
				read_float(p_item, "delta_x", -coordinate_maximum, coordinate_maximum, r_value.delta_x) &&
				read_float(p_item, "delta_y", -coordinate_maximum, coordinate_maximum, r_value.delta_y);
	}
	if (kind == "button") {
		constexpr const char *keys[] = { "kind", "x", "y", "button", "pressed" };
		String button;
		r_value.kind = PointerEventKind::BUTTON;
		if (!toqraq_has_exact_keys(p_item, keys, 5) || !read_string(p_item, "button", button) ||
				!read_bool(p_item, "pressed", r_value.pressed)) {
			return false;
		}
		r_value.button = _pointer_button(button);
		return r_value.button != MouseButton::NONE;
	}
	if (kind == "wheel") {
		constexpr const char *keys[] = { "kind", "x", "y", "delta_x", "delta_y", "unit" };
		String unit;
		r_value.kind = PointerEventKind::WHEEL;
		return toqraq_has_exact_keys(p_item, keys, 6) &&
				read_float(p_item, "delta_x", -MAX_WHEEL_VALUE, MAX_WHEEL_VALUE, r_value.delta_x) &&
				read_float(p_item, "delta_y", -MAX_WHEEL_VALUE, MAX_WHEEL_VALUE, r_value.delta_y) &&
				(r_value.delta_x != 0.0 || r_value.delta_y != 0.0) && read_string(p_item, "unit", unit) &&
				(unit == "pixels" || unit == "lines" || unit == "pages");
	}
	return false;
}

bool _decode_events(const Array &p_events, bool p_normalized, Vector<PointerEventValue> &r_values) {
	if (p_events.size() < 1 || p_events.size() > MAX_EVENTS) {
		return false;
	}
	for (int index = 0; index < p_events.size(); index++) {
		if (p_events[index].get_type() != Variant::DICTIONARY) {
			return false;
		}
		PointerEventValue value;
		if (!_decode_event(Dictionary(p_events[index]), p_normalized, value)) {
			return false;
		}
		r_values.push_back(value);
	}
	return true;
}

void _add_mouse_button(Vector<Ref<InputEvent>> &r_events, MouseButton p_button, const Vector2 &p_position,
		bool p_pressed, float p_factor, const BitField<MouseButtonMask> &p_button_mask, int p_device,
		int64_t p_window) {
	Ref<InputEventMouseButton> event;
	event.instantiate();
	event->set_button_index(p_button);
	event->set_button_mask(p_button_mask);
	event->set_position(p_position);
	event->set_global_position(p_position);
	event->set_pressed(p_pressed);
	event->set_factor(p_factor);
	event->set_device(p_device);
	event->set_window_id(p_window);
	r_events.push_back(event);
}

Vector2 _viewport_position(const PointerEventValue &p_value, bool p_normalized, const Vector2 &p_size) {
	return p_normalized ? Vector2(p_value.x * MAX(p_size.x - 1.0f, 0.0f), p_value.y * MAX(p_size.y - 1.0f, 0.0f)) :
			Vector2(p_value.x, p_value.y);
}

void _map_motion(Vector<Ref<InputEvent>> &r_events, const Vector2 &p_position, const Vector2 &p_relative,
		bool p_touch, const BitField<MouseButtonMask> &p_button_mask, int p_pointer_id, int64_t p_window) {
	if (p_touch) {
		Ref<InputEventScreenDrag> event;
		event.instantiate();
		event->set_index(p_pointer_id);
		event->set_position(p_position);
		event->set_relative(p_relative);
		event->set_relative_screen_position(p_relative);
		event->set_window_id(p_window);
		r_events.push_back(event);
		return;
	}
	Ref<InputEventMouseMotion> event;
	event.instantiate();
	event->set_position(p_position);
	event->set_global_position(p_position);
	event->set_relative(p_relative);
	event->set_relative_screen_position(p_relative);
	event->set_button_mask(p_button_mask);
	event->set_device(_mouse_device(p_pointer_id));
	event->set_window_id(p_window);
	r_events.push_back(event);
}

ToqraqInputDispatchResult _map_button(Vector<Ref<InputEvent>> &r_events, const PointerEventValue &p_value,
		const Vector2 &p_position, bool p_touch, BitField<MouseButtonMask> &r_button_mask, int p_pointer_id,
		int64_t p_window) {
	if (!p_touch) {
		const int device = _mouse_device(p_pointer_id);
		const MouseButtonMask changed_button = mouse_button_to_mask(p_value.button);
		if (p_value.pressed) {
			r_button_mask.set_flag(changed_button);
		} else {
			r_button_mask.clear_flag(changed_button);
		}
		_add_mouse_button(r_events, p_value.button, p_position, p_value.pressed, 1.0f, r_button_mask,
				device, p_window);
		return ToqraqInputDispatchResult();
	}
	if (p_value.button != MouseButton::LEFT) {
		return rejected("touch_button_unmappable");
	}
	Ref<InputEventScreenTouch> event;
	event.instantiate();
	event->set_index(p_pointer_id);
	event->set_position(p_position);
	event->set_pressed(p_value.pressed);
	event->set_window_id(p_window);
	r_events.push_back(event);
	return ToqraqInputDispatchResult();
}

void _add_wheel_axis(Vector<Ref<InputEvent>> &r_events, MouseButton p_button, float p_factor,
		const Vector2 &p_position, const BitField<MouseButtonMask> &p_button_mask, int p_pointer_id,
		int64_t p_window) {
	BitField<MouseButtonMask> pressed_mask = p_button_mask;
	pressed_mask.set_flag(mouse_button_to_mask(p_button));
	_add_mouse_button(r_events, p_button, p_position, true, p_factor, pressed_mask, p_pointer_id, p_window);
	_add_mouse_button(r_events, p_button, p_position, false, p_factor, p_button_mask, p_pointer_id, p_window);
}

ToqraqInputDispatchResult _map_wheel(Vector<Ref<InputEvent>> &r_events, const PointerEventValue &p_value,
		const Vector2 &p_position, bool p_touch, const BitField<MouseButtonMask> &p_button_mask,
		int p_pointer_id, int64_t p_window) {
	if (p_touch) {
		return rejected("touch_wheel_unmappable");
	}
	const int device = _mouse_device(p_pointer_id);
	if (p_value.delta_x != 0.0) {
		_add_wheel_axis(r_events, p_value.delta_x < 0.0 ? MouseButton::WHEEL_LEFT : MouseButton::WHEEL_RIGHT,
				Math::abs((float)p_value.delta_x), p_position, p_button_mask, device, p_window);
	}
	if (p_value.delta_y != 0.0) {
		_add_wheel_axis(r_events, p_value.delta_y < 0.0 ? MouseButton::WHEEL_UP : MouseButton::WHEEL_DOWN,
				Math::abs((float)p_value.delta_y), p_position, p_button_mask, device, p_window);
	}
	return ToqraqInputDispatchResult();
}

} // namespace

ToqraqInputDispatchResult toqraq_dispatch_pointer_input(const Dictionary &p_params) {
	constexpr const char *keys[] = { "pointer_id", "pointer_kind", "coordinate_space", "events" };
	int pointer_id;
	String pointer_kind;
	String coordinate_space;
	const Variant *events = p_params.getptr("events");
	if (!toqraq_has_exact_keys(p_params, keys, 4) || !read_slot(p_params, "pointer_id", 31, pointer_id) ||
			!read_string(p_params, "pointer_kind", pointer_kind) ||
			(pointer_kind != "mouse" && pointer_kind != "pen" && pointer_kind != "touch") ||
			!read_string(p_params, "coordinate_space", coordinate_space) ||
			(coordinate_space != "viewport_pixels" && coordinate_space != "viewport_normalized") ||
			events == nullptr || events->get_type() != Variant::ARRAY) {
		return invalid();
	}
	const bool normalized = coordinate_space == "viewport_normalized";
	Vector<PointerEventValue> values;
	if (!_decode_events(Array(*events), normalized, values)) {
		return invalid();
	}
	SceneTree *tree = SceneTree::get_singleton();
	Window *window = tree == nullptr ? nullptr : tree->get_root();
	if (window == nullptr || Input::get_singleton() == nullptr) {
		return rejected("viewport_unavailable");
	}
	const Vector2 viewport_size = window->get_visible_rect().size;
	if (viewport_size.x <= 0.0f || viewport_size.y <= 0.0f) {
		return rejected("viewport_unavailable");
	}
	const bool touch = pointer_kind == "touch";
	const int64_t window_id = window->get_window_id();
	BitField<MouseButtonMask> mouse_button_mask = Input::get_singleton()->get_mouse_button_mask();
	Vector<Ref<InputEvent>> mapped;
	for (const PointerEventValue &value : values) {
		if (!normalized && (value.x >= viewport_size.x || value.y >= viewport_size.y)) {
			return rejected("pointer_outside_viewport");
		}
		const Vector2 position = _viewport_position(value, normalized, viewport_size);
		if (value.kind == PointerEventKind::MOTION) {
			const Vector2 relative = normalized ? Vector2(value.delta_x * viewport_size.x, value.delta_y * viewport_size.y) :
					Vector2(value.delta_x, value.delta_y);
			_map_motion(mapped, position, relative, touch, mouse_button_mask, pointer_id, window_id);
		} else {
			const ToqraqInputDispatchResult map_result = value.kind == PointerEventKind::BUTTON ?
					_map_button(mapped, value, position, touch, mouse_button_mask, pointer_id, window_id) :
					_map_wheel(mapped, value, position, touch, mouse_button_mask, pointer_id, window_id);
			if (map_result.handled) {
				return map_result;
			}
		}
	}
	if (!commit(mapped)) {
		return rejected("input_unavailable");
	}
	return success(values.size());
}
