// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"
#include "core/variant/dictionary.h"

struct ToqraqInputDispatchResult {
	bool handled = false;
	bool succeeded = false;
	Dictionary result;
	String error_code;
	String error_category;
	Dictionary error_details;
};

ToqraqInputDispatchResult toqraq_dispatch_input(const String &p_method, const Dictionary &p_params);
