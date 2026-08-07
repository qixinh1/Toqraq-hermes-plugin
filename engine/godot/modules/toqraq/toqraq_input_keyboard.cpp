// SPDX-License-Identifier: MIT

#include "toqraq_input_keyboard.h"

#include "toqraq_input_contract.h"
#include "toqraq_json.h"

#include "core/input/input.h"
#include "core/input/input_event.h"
#include "core/string/char_utils.h"

namespace {

using namespace ToqraqInputContract;

struct KeyEntry {
	const char *name;
	Key key;
};

constexpr KeyEntry PHYSICAL_KEYS[] = {
	{ "AltLeft", Key::ALT }, { "AltRight", Key::ALT }, { "ArrowDown", Key::DOWN }, { "ArrowLeft", Key::LEFT },
	{ "ArrowRight", Key::RIGHT }, { "ArrowUp", Key::UP }, { "Backquote", Key::QUOTELEFT }, { "Backslash", Key::BACKSLASH },
	{ "Backspace", Key::BACKSPACE }, { "BracketLeft", Key::BRACKETLEFT }, { "BracketRight", Key::BRACKETRIGHT },
	{ "CapsLock", Key::CAPSLOCK }, { "Comma", Key::COMMA }, { "ContextMenu", Key::MENU }, { "ControlLeft", Key::CTRL },
	{ "ControlRight", Key::CTRL }, { "Convert", Key::JIS_KANA }, { "Delete", Key::KEY_DELETE }, { "End", Key::END },
	{ "Enter", Key::ENTER }, { "Equal", Key::EQUAL }, { "Escape", Key::ESCAPE }, { "Help", Key::HELP }, { "Home", Key::HOME },
	{ "Insert", Key::INSERT }, { "IntlBackslash", Key::BAR }, { "IntlRo", Key::BACKSLASH }, { "IntlYen", Key::YEN },
	{ "KanaMode", Key::JIS_KANA }, { "MetaLeft", Key::META }, { "MetaRight", Key::META }, { "Minus", Key::MINUS },
	{ "NonConvert", Key::JIS_EISU }, { "NumLock", Key::NUMLOCK }, { "NumpadAdd", Key::KP_ADD },
	{ "NumpadDecimal", Key::KP_PERIOD }, { "NumpadDivide", Key::KP_DIVIDE }, { "NumpadEnter", Key::KP_ENTER },
	{ "NumpadMultiply", Key::KP_MULTIPLY }, { "NumpadSubtract", Key::KP_SUBTRACT }, { "PageDown", Key::PAGEDOWN },
	{ "PageUp", Key::PAGEUP }, { "Pause", Key::PAUSE }, { "Period", Key::PERIOD }, { "PrintScreen", Key::PRINT },
	{ "Quote", Key::APOSTROPHE }, { "ScrollLock", Key::SCROLLLOCK }, { "Semicolon", Key::SEMICOLON },
	{ "ShiftLeft", Key::SHIFT }, { "ShiftRight", Key::SHIFT }, { "Slash", Key::SLASH }, { "Space", Key::SPACE }, { "Tab", Key::TAB },
};

constexpr KeyEntry LOGICAL_KEYS[] = {
	{ "Alt", Key::ALT }, { "AltGraph", Key::ALT }, { "ArrowDown", Key::DOWN }, { "ArrowLeft", Key::LEFT },
	{ "ArrowRight", Key::RIGHT }, { "ArrowUp", Key::UP }, { "Backspace", Key::BACKSPACE }, { "CapsLock", Key::CAPSLOCK },
	{ "ContextMenu", Key::MENU }, { "Control", Key::CTRL }, { "Convert", Key::JIS_KANA }, { "Dead", Key::UNKNOWN },
	{ "Delete", Key::KEY_DELETE }, { "End", Key::END }, { "Enter", Key::ENTER }, { "Escape", Key::ESCAPE },
	{ "Help", Key::HELP }, { "Home", Key::HOME }, { "Insert", Key::INSERT }, { "KanaMode", Key::JIS_KANA },
	{ "Meta", Key::META }, { "NonConvert", Key::JIS_EISU }, { "NumLock", Key::NUMLOCK }, { "PageDown", Key::PAGEDOWN },
	{ "PageUp", Key::PAGEUP }, { "Pause", Key::PAUSE }, { "PrintScreen", Key::PRINT }, { "ScrollLock", Key::SCROLLLOCK },
	{ "Shift", Key::SHIFT }, { "Tab", Key::TAB },
};

Key _lookup_key(const String &p_name, const KeyEntry *p_entries, int p_count) {
	for (int index = 0; index < p_count; index++) {
		if (p_name == p_entries[index].name) {
			return p_entries[index].key;
		}
	}
	return Key::NONE;
}

Key _physical_key(const String &p_code) {
	if (p_code.length() == 6 && p_code.begins_with("Digit") && p_code[5] >= '0' && p_code[5] <= '9') {
		return Key::KEY_0 + (p_code[5] - '0');
	}
	if (p_code.length() == 4 && p_code.begins_with("Key") && p_code[3] >= 'A' && p_code[3] <= 'Z') {
		return Key::A + (p_code[3] - 'A');
	}
	if (p_code.begins_with("F") && (p_code.length() == 2 || p_code.length() == 3)) {
		const int number = p_code.substr(1).to_int();
		if (number >= 1 && number <= 12 && p_code == "F" + String::num_int64(number)) {
			return (Key)((int)Key::F1 + number - 1);
		}
	}
	if (p_code.length() == 7 && p_code.begins_with("Numpad") && p_code[6] >= '0' && p_code[6] <= '9') {
		return Key::KP_0 + (p_code[6] - '0');
	}
	return _lookup_key(p_code, PHYSICAL_KEYS, sizeof(PHYSICAL_KEYS) / sizeof(PHYSICAL_KEYS[0]));
}

bool _apply_modifiers(const Array &p_values, const Ref<InputEventKey> &p_event) {
	if (p_values.size() > 4) {
		return false;
	}
	int mask = 0;
	for (int index = 0; index < p_values.size(); index++) {
		if (p_values[index].get_type() != Variant::STRING) {
			return false;
		}
		const String value = p_values[index];
		const int bit = value == "shift" ? 1 : value == "control" ? 2 : value == "alt" ? 4 : value == "meta" ? 8 : 0;
		if (bit == 0 || (mask & bit) != 0) {
			return false;
		}
		mask |= bit;
	}
	p_event->set_shift_pressed((mask & 1) != 0);
	p_event->set_ctrl_pressed((mask & 2) != 0);
	p_event->set_alt_pressed((mask & 4) != 0);
	p_event->set_meta_pressed((mask & 8) != 0);
	return true;
}

bool _is_combining_sequence_shape(const String &p_value) {
	for (int index = 1; index < p_value.length(); index++) {
		if (is_unicode_identifier_start(p_value[index]) || !is_unicode_identifier_continue(p_value[index])) {
			return false;
		}
	}
	return true;
}

} // namespace

ToqraqInputDispatchResult toqraq_dispatch_keyboard_input(const Dictionary &p_params) {
	Array events;
	if (!read_events(p_params, events)) {
		return invalid();
	}
	Vector<Ref<InputEvent>> mapped;
	for (int index = 0; index < events.size(); index++) {
		if (events[index].get_type() != Variant::DICTIONARY) {
			return invalid();
		}
		const Dictionary item = events[index];
		constexpr const char *keys[] = { "physical_code", "logical_key", "location", "modifiers", "pressed", "repeated" };
		const Variant *physical = item.getptr("physical_code");
		const Variant *logical = item.getptr("logical_key");
		const Variant *modifiers = item.getptr("modifiers");
		String location;
		bool pressed;
		bool repeated;
		if (!toqraq_has_exact_keys(item, keys, 6) || physical == nullptr || logical == nullptr || modifiers == nullptr ||
				modifiers->get_type() != Variant::ARRAY || !read_string(item, "location", location) ||
				(location != "standard" && location != "left" && location != "right" && location != "numpad") ||
				!read_bool(item, "pressed", pressed) || !read_bool(item, "repeated", repeated) || (repeated && !pressed)) {
			return invalid();
		}
		Ref<InputEventKey> event;
		event.instantiate();
		if (!_apply_modifiers(Array(*modifiers), event)) {
			return invalid();
		}
		if (physical->get_type() == Variant::STRING) {
			const Key key = _physical_key(String(*physical));
			if (key == Key::NONE) {
				return invalid();
			}
			event->set_physical_keycode(key);
		} else if (physical->get_type() != Variant::NIL) {
			return invalid();
		}
		if (logical->get_type() == Variant::STRING) {
			const String key_name = *logical;
			if (!toqraq_is_bounded_utf8(key_name, 64)) {
				return invalid();
			}
			Key key = _lookup_key(key_name, LOGICAL_KEYS, sizeof(LOGICAL_KEYS) / sizeof(LOGICAL_KEYS[0]));
			if (key == Key::NONE && key_name.begins_with("F")) {
				key = _physical_key(key_name);
			}
			if (key != Key::NONE) {
				event->set_keycode(key);
			} else if (key_name.length() == 1 && !is_control(key_name[0])) {
				event->set_keycode((Key)key_name[0]);
				event->set_unicode(key_name[0]);
			} else if (key_name.length() > 1) {
				return _is_combining_sequence_shape(key_name) ? rejected("logical_key_unmappable") : invalid();
			} else {
				return invalid();
			}
		} else if (logical->get_type() != Variant::NIL) {
			return invalid();
		}
		if (physical->get_type() == Variant::NIL && logical->get_type() == Variant::NIL) {
			return invalid();
		}
		event->set_location(location == "left" ? KeyLocation::LEFT : location == "right" ? KeyLocation::RIGHT : KeyLocation::UNSPECIFIED);
		event->set_device(InputEvent::DEVICE_ID_KEYBOARD);
		event->set_pressed(pressed);
		event->set_echo(repeated);
		mapped.push_back(event);
	}
	if (!commit(mapped)) {
		return rejected("input_unavailable");
	}
	return success(events.size());
}
