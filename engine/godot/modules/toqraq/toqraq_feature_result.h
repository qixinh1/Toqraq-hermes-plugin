// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"
#include "core/templates/vector.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

struct ToqraqFeatureResult {
	bool succeeded = false;
	Dictionary result;
	String error_code;
	String error_category;
	Dictionary error_details;
	Vector<uint8_t> binary;
	Array changed_families;
};

inline ToqraqFeatureResult toqraq_feature_success(const Dictionary &p_result) {
	ToqraqFeatureResult value;
	value.succeeded = true;
	value.result = p_result;
	return value;
}

inline ToqraqFeatureResult toqraq_feature_error(const char *p_code, const char *p_category) {
	ToqraqFeatureResult value;
	value.error_code = p_code;
	value.error_category = p_category;
	return value;
}
