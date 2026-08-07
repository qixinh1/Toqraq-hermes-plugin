// SPDX-License-Identifier: MIT

#include "toqraq_input_text.h"

#include "toqraq_input_contract.h"
#include "toqraq_json.h"

#include "scene/gui/control.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

using namespace ToqraqInputContract;

namespace {

Control *_focused_text_surface(Window *p_window) {
	Window *focused_window = p_window;
	while (focused_window->get_focused_subwindow() != nullptr) {
		focused_window = focused_window->get_focused_subwindow();
	}
	Control *focus = focused_window->gui_get_focus_owner();
	return focus != nullptr && focus->has_method(SNAME("_set_text")) ? focus : nullptr;
}

} // namespace

ToqraqInputDispatchResult toqraq_dispatch_text_input(const Dictionary &p_params) {
	constexpr const char *keys[] = { "text" };
	String text;
	if (!toqraq_has_exact_keys(p_params, keys, 1) || !read_string(p_params, "text", text) ||
			!toqraq_is_bounded_utf8(text, 4096) || text.find_char(0) >= 0) {
		return invalid();
	}
	SceneTree *tree = SceneTree::get_singleton();
	Window *window = tree == nullptr ? nullptr : tree->get_root();
	if (window == nullptr || _focused_text_surface(window) == nullptr) {
		return rejected("text_focus_unavailable");
	}
	window->push_text_input(text);
	return success(1);
}
