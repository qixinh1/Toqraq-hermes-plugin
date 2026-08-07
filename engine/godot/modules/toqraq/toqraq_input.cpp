// SPDX-License-Identifier: MIT

#include "toqraq_input.h"

#include "toqraq_input_gamepad.h"
#include "toqraq_input_keyboard.h"
#include "toqraq_input_pointer.h"
#include "toqraq_input_semantic.h"
#include "toqraq_input_text.h"

ToqraqInputDispatchResult toqraq_dispatch_input(const String &p_method, const Dictionary &p_params) {
	if (p_method == "toqraq.input.semantic") {
		return toqraq_dispatch_semantic_input(p_params);
	}
	if (p_method == "toqraq.input.keyboard") {
		return toqraq_dispatch_keyboard_input(p_params);
	}
	if (p_method == "toqraq.input.pointer") {
		return toqraq_dispatch_pointer_input(p_params);
	}
	if (p_method == "toqraq.input.text") {
		return toqraq_dispatch_text_input(p_params);
	}
	if (p_method == "toqraq.input.gamepad") {
		return toqraq_dispatch_gamepad_input(p_params);
	}
	return ToqraqInputDispatchResult();
}
