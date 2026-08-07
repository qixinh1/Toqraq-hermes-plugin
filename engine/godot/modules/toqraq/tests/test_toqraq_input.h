// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_input.h"
#include "../toqraq_json.h"
#include "../toqraq_limits.h"

#include "core/input/input.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"
#include "scene/gui/line_edit.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"
#include "tests/test_macros.h"

namespace TestToqraqInput {

Dictionary keyboard_event(const Variant &p_physical_code) {
	Dictionary event;
	event["physical_code"] = p_physical_code;
	event["logical_key"] = Variant();
	event["location"] = "standard";
	event["modifiers"] = Array();
	event["pressed"] = false;
	event["repeated"] = false;
	return event;
}

Dictionary event_batch(const Array &p_events) {
	Dictionary parameters;
	parameters["events"] = p_events;
	return parameters;
}

TEST_CASE("[Toqraq] unknown input method is not handled") {
	const ToqraqInputDispatchResult result = toqraq_dispatch_input("toqraq.input.unknown", Dictionary());
	CHECK_FALSE(result.handled);
	CHECK_FALSE(result.succeeded);
}

TEST_CASE("[Toqraq] malformed focused input DTOs fail as invalid parameters") {
	Dictionary semantic_event;
	semantic_event["action"] = "ui_accept";
	semantic_event["pressed"] = true;
	semantic_event["strength"] = 1;
	Array semantic_events;
	semantic_events.push_back(semantic_event);
	const ToqraqInputDispatchResult semantic = toqraq_dispatch_input("toqraq.input.semantic", event_batch(semantic_events));
	CHECK(semantic.handled);
	CHECK_FALSE(semantic.succeeded);
	CHECK(semantic.error_code == "bridge.params_invalid");
	CHECK(semantic.error_category == "invalid");

	Dictionary pointer;
	pointer["pointer_id"] = 0;
	pointer["pointer_kind"] = "mouse";
	pointer["coordinate_space"] = "screen_pixels";
	pointer["events"] = Array();
	CHECK(toqraq_dispatch_input("toqraq.input.pointer", pointer).error_code == "bridge.params_invalid");

	Dictionary text;
	text["text"] = "";
	CHECK(toqraq_dispatch_input("toqraq.input.text", text).error_code == "bridge.params_invalid");

	Dictionary gamepad;
	gamepad["device_slot"] = 0.0;
	gamepad["events"] = Array();
	CHECK(toqraq_dispatch_input("toqraq.input.gamepad", gamepad).error_code == "bridge.params_invalid");
}

TEST_CASE("[SceneTree][Toqraq] keyboard batch validation is atomic") {
	Dictionary press = keyboard_event("KeyA");
	press["pressed"] = true;
	Dictionary malformed = keyboard_event("NotAKey");
	Array events;
	events.push_back(press);
	events.push_back(malformed);
	const ToqraqInputDispatchResult result = toqraq_dispatch_input("toqraq.input.keyboard", event_batch(events));
	CHECK(result.error_code == "bridge.params_invalid");
}

TEST_CASE("[SceneTree][Toqraq] integral JSON numbers reach pointer and gamepad slots") {
	Variant pointer_value;
	REQUIRE(toqraq_decode_bounded_json(
			R"({"pointer_id":0,"pointer_kind":"mouse","coordinate_space":"viewport_normalized","events":[{"kind":"motion","x":0.5,"y":0.5,"delta_x":0.0,"delta_y":0.0}]})",
			ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, pointer_value));
	REQUIRE(pointer_value.get_type() == Variant::DICTIONARY);
	const ToqraqInputDispatchResult pointer =
			toqraq_dispatch_input("toqraq.input.pointer", Dictionary(pointer_value));
	CHECK(pointer.succeeded);
	CHECK((int64_t)pointer.result["accepted_event_count"] == 1);

	Variant gamepad_value;
	REQUIRE(toqraq_decode_bounded_json(
			R"({"device_slot":0,"events":[{"kind":"axis","axis":"left_x","value":0.5}]})",
			ToqraqLimits::MAX_TEXT_MESSAGE_BYTES, gamepad_value));
	REQUIRE(gamepad_value.get_type() == Variant::DICTIONARY);
	const ToqraqInputDispatchResult gamepad =
			toqraq_dispatch_input("toqraq.input.gamepad", Dictionary(gamepad_value));
	CHECK(gamepad.succeeded);
	CHECK((int64_t)gamepad.result["accepted_event_count"] == 1);
}

TEST_CASE("[SceneTree][Toqraq] required W3C physical keyboard codes all map") {
	REQUIRE(Input::get_singleton() != nullptr);
	constexpr const char *named_codes[] = {
		"AltLeft", "AltRight", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowUp", "Backquote", "Backslash",
		"Backspace", "BracketLeft", "BracketRight", "CapsLock", "Comma", "ContextMenu", "ControlLeft", "ControlRight",
		"Convert", "Delete", "End", "Enter", "Equal", "Escape", "Help", "Home", "Insert", "IntlBackslash", "IntlRo",
		"IntlYen", "KanaMode", "MetaLeft", "MetaRight", "Minus", "NonConvert", "NumLock", "NumpadAdd", "NumpadDecimal",
		"NumpadDivide", "NumpadEnter", "NumpadMultiply", "NumpadSubtract", "PageDown", "PageUp", "Pause", "Period",
		"PrintScreen", "Quote", "ScrollLock", "Semicolon", "ShiftLeft", "ShiftRight", "Slash", "Space", "Tab",
	};
	Array events;
	for (const char *code : named_codes) {
		events.push_back(keyboard_event(code));
	}
	for (int digit = 0; digit < 10; digit++) {
		events.push_back(keyboard_event("Digit" + String::num_int64(digit)));
		events.push_back(keyboard_event("Numpad" + String::num_int64(digit)));
	}
	for (int function = 1; function <= 12; function++) {
		events.push_back(keyboard_event("F" + String::num_int64(function)));
	}
	for (char32_t letter = 'A'; letter <= 'Z'; letter++) {
		events.push_back(keyboard_event("Key" + String::chr(letter)));
	}
	const ToqraqInputDispatchResult result = toqraq_dispatch_input("toqraq.input.keyboard", event_batch(events));
	const bool dispatch_available = result.succeeded || result.error_code == "input.rejected";
	CHECK(dispatch_available);
	if (result.succeeded) {
		CHECK((int64_t)result.result["accepted_event_count"] == events.size());
	}
}

TEST_CASE("[Toqraq] duplicate keyboard modifiers are rejected before dispatch") {
	Dictionary event = keyboard_event("KeyA");
	Array modifiers;
	modifiers.push_back("shift");
	modifiers.push_back("shift");
	event["modifiers"] = modifiers;
	Array events;
	events.push_back(event);
	CHECK(toqraq_dispatch_input("toqraq.input.keyboard", event_batch(events)).error_code == "bridge.params_invalid");
	event = keyboard_event(Variant());
	event["logical_key"] = "madeUpNamedKey";
	events.clear();
	events.push_back(event);
	CHECK(toqraq_dispatch_input("toqraq.input.keyboard", event_batch(events)).error_code == "bridge.params_invalid");
}

TEST_CASE("[SceneTree][Toqraq] text input follows the focused embedded subwindow") {
	SceneTree *tree = SceneTree::get_singleton();
	REQUIRE(tree != nullptr);
	Window *root = tree->get_root();
	REQUIRE(root != nullptr);
	REQUIRE(root->get_focused_subwindow() == nullptr);
	const bool was_embedding = root->is_embedding_subwindows();
	root->set_embedding_subwindows(true);
	Window *subwindow = memnew(Window);
	LineEdit *line_edit = memnew(LineEdit);
	subwindow->add_child(line_edit);
	root->add_child(subwindow);
	subwindow->show();
	line_edit->grab_focus();

	Dictionary parameters;
	parameters["text"] = "focused text";
	const ToqraqInputDispatchResult result = toqraq_dispatch_input("toqraq.input.text", parameters);
	CHECK(root->get_focused_subwindow() == subwindow);
	CHECK(subwindow->gui_get_focus_owner() == line_edit);
	CHECK(result.succeeded);
	CHECK(line_edit->get_text() == "focused text");

	subwindow->hide();
	root->remove_child(subwindow);
	memdelete(subwindow);
	root->set_embedding_subwindows(was_embedding);
}

} // namespace TestToqraqInput
