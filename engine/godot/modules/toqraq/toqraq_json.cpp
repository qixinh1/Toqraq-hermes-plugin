// SPDX-License-Identifier: MIT

#include "toqraq_json.h"

#include "toqraq_limits.h"

#include "core/io/json.h"
#include "core/math/math_funcs.h"
#include "core/string/char_utils.h"
#include "core/variant/array.h"
#include "core/variant/dictionary.h"

namespace {

struct JsonBounds {
	int nodes = 0;
	int object_members = 0;
};

int _hex_digit(char32_t p_character) {
	if (p_character >= '0' && p_character <= '9') {
		return p_character - '0';
	}
	if (p_character >= 'a' && p_character <= 'f') {
		return p_character - 'a' + 10;
	}
	if (p_character >= 'A' && p_character <= 'F') {
		return p_character - 'A' + 10;
	}
	return -1;
}

bool _read_unicode_escape(const String &p_json, int p_slash, int &r_value) {
	if (p_slash + 5 >= p_json.length() || p_json[p_slash] != '\\' || p_json[p_slash + 1] != 'u') {
		return false;
	}
	int value = 0;
	for (int offset = 2; offset < 6; offset++) {
		const int digit = _hex_digit(p_json[p_slash + offset]);
		if (digit < 0) {
			return false;
		}
		value = value * 16 + digit;
	}
	r_value = value;
	return true;
}

bool _valid_unicode_escapes(const String &p_json) {
	bool quoted = false;
	for (int index = 0; index < p_json.length(); index++) {
		const char32_t character = p_json[index];
		if (!quoted) {
			quoted = character == '"';
			continue;
		}
		if (character == '"') {
			quoted = false;
			continue;
		}
		if (character != '\\') {
			continue;
		}
		if (index + 1 >= p_json.length()) {
			return false;
		}
		if (p_json[index + 1] != 'u') {
			index++;
			continue;
		}
		int value = 0;
		if (!_read_unicode_escape(p_json, index, value) || value == 0 ||
				(value >= 0xdc00 && value <= 0xdfff)) {
			return false;
		}
		if (value >= 0xd800 && value <= 0xdbff) {
			int low = 0;
			if (!_read_unicode_escape(p_json, index + 6, low) || low < 0xdc00 || low > 0xdfff) {
				return false;
			}
			index += 11;
		} else {
			index += 5;
		}
	}
	return !quoted;
}

bool _validate_json_bounds(const Variant &p_value, int p_depth, JsonBounds &r_bounds) {
	r_bounds.nodes++;
	if (r_bounds.nodes > ToqraqLimits::MAX_JSON_NODES || p_depth > ToqraqLimits::MAX_JSON_DEPTH) {
		return false;
	}
	switch (p_value.get_type()) {
		case Variant::DICTIONARY: {
			const Dictionary dictionary = p_value;
			if (dictionary.size() > ToqraqLimits::MAX_JSON_COLLECTION_ITEMS) {
				return false;
			}
			r_bounds.object_members += dictionary.size();
			const Array keys = dictionary.keys();
			for (int index = 0; index < keys.size(); index++) {
				if (keys[index].get_type() != Variant::STRING || !String(keys[index]).is_valid_string()) {
					return false;
				}
				const Variant *value = dictionary.getptr(keys[index]);
				if (value == nullptr || !_validate_json_bounds(*value, p_depth + 1, r_bounds)) {
					return false;
				}
			}
			return true;
		}
		case Variant::ARRAY: {
			const Array array = p_value;
			if (array.size() > ToqraqLimits::MAX_JSON_COLLECTION_ITEMS) {
				return false;
			}
			for (int index = 0; index < array.size(); index++) {
				if (!_validate_json_bounds(array[index], p_depth + 1, r_bounds)) {
					return false;
				}
			}
			return true;
		}
		case Variant::STRING:
			return String(p_value).is_valid_string();
		case Variant::FLOAT: {
			const double value = p_value;
			return Math::is_finite(value) &&
					(Math::floor(value) != value ||
							(value >= -ToqraqLimits::MAX_SAFE_INTEGER &&
									value <= ToqraqLimits::MAX_SAFE_INTEGER));
		}
		case Variant::NIL:
		case Variant::BOOL:
			return true;
		case Variant::INT: {
			const int64_t value = p_value;
			return value >= -ToqraqLimits::MAX_SAFE_INTEGER &&
					value <= ToqraqLimits::MAX_SAFE_INTEGER;
		}
		default:
			return false;
	}
}

} // namespace

int toqraq_count_json_members(const String &p_json) {
	bool quoted = false;
	bool escaped = false;
	int count = 0;
	for (int index = 0; index < p_json.length(); index++) {
		const char32_t character = p_json[index];
		if (quoted) {
			if (escaped) {
				escaped = false;
			} else if (character == '\\') {
				escaped = true;
			} else if (character == '"') {
				quoted = false;
			}
		} else if (character == '"') {
			quoted = true;
		} else if (character == ':') {
			count++;
		}
	}
	return count;
}

bool toqraq_read_json_integer(const Variant &p_value, int64_t &r_value) {
	double number = 0.0;
	if (p_value.get_type() == Variant::INT) {
		const int64_t integer = p_value;
		if (integer < -ToqraqLimits::MAX_SAFE_INTEGER || integer > ToqraqLimits::MAX_SAFE_INTEGER) {
			return false;
		}
		r_value = integer;
		return true;
	}
	if (p_value.get_type() != Variant::FLOAT) {
		return false;
	}
	number = p_value;
	if (!Math::is_finite(number) || Math::floor(number) != number ||
			number < -ToqraqLimits::MAX_SAFE_INTEGER || number > ToqraqLimits::MAX_SAFE_INTEGER) {
		return false;
	}
	r_value = (int64_t)number;
	return true;
}

bool toqraq_read_json_float(const Variant &p_value, double &r_value) {
	if (p_value.get_type() != Variant::FLOAT) {
		return false;
	}
	const double value = p_value;
	if (!Math::is_finite(value)) {
		return false;
	}
	r_value = value;
	return true;
}

bool toqraq_decode_bounded_json(const String &p_json, int p_maximum_bytes, Variant &r_value) {
	const int bytes = p_json.utf8().length();
	if (bytes < 1 || bytes > p_maximum_bytes || p_maximum_bytes > ToqraqLimits::MAX_TEXT_MESSAGE_BYTES ||
			!_valid_unicode_escapes(p_json)) {
		return false;
	}
	Ref<JSON> parser;
	parser.instantiate();
	if (parser->parse(p_json) != OK) {
		return false;
	}
	JsonBounds bounds;
	const Variant decoded = parser->get_data();
	if (!_validate_json_bounds(decoded, 0, bounds) || bounds.object_members != toqraq_count_json_members(p_json)) {
		return false;
	}
	r_value = decoded;
	return true;
}

bool toqraq_has_exact_keys(const Dictionary &p_value, const char *const *p_keys, int p_key_count) {
	if (p_value.size() != p_key_count) {
		return false;
	}
	for (int index = 0; index < p_key_count; index++) {
		if (!p_value.has(p_keys[index])) {
			return false;
		}
	}
	return true;
}

bool toqraq_is_bounded_utf8(const String &p_value, int p_maximum_bytes, bool p_allow_empty) {
	return p_value.is_valid_string() && (p_allow_empty || !p_value.is_empty()) &&
			p_value.utf8().length() <= p_maximum_bytes;
}

bool toqraq_is_observation_label(const String &p_value, int p_maximum_bytes) {
	if (!toqraq_is_bounded_utf8(p_value, p_maximum_bytes)) {
		return false;
	}
	for (int index = 0; index < p_value.length(); index++) {
		const char32_t character = p_value[index];
		if (is_control(character) || (character >= 0xd800 && character <= 0xf8ff) ||
				(character >= 0xf0000 && character <= 0xffffd) ||
				(character >= 0x100000 && character <= 0x10fffd) || character == 0x00ad ||
				character == 0x061c || (character >= 0x200b && character <= 0x200f) ||
				(character >= 0x202a && character <= 0x202e) ||
				(character >= 0x2060 && character <= 0x206f) || character == 0xfeff) {
			return false;
		}
	}
	return true;
}

bool toqraq_is_observation_token(const String &p_value) {
	if (p_value.is_empty() || p_value.length() > 128) {
		return false;
	}
	for (int index = 0; index < p_value.length(); index++) {
		const char32_t character = p_value[index];
		const bool alphanumeric = (character >= 'A' && character <= 'Z') ||
				(character >= 'a' && character <= 'z') || (character >= '0' && character <= '9');
		if (!alphanumeric && character != '.' && character != '_' && character != ':' && character != '-') {
			return false;
		}
		if (index == 0 && !alphanumeric) {
			return false;
		}
	}
	return true;
}

bool toqraq_is_namespaced_id(const String &p_value) {
	if (p_value.length() < 3 || p_value.length() > 128 || p_value.find_char('.') < 1) {
		return false;
	}
	bool separator = false;
	for (int index = 0; index < p_value.length(); index++) {
		const char32_t character = p_value[index];
		const bool lowercase = character >= 'a' && character <= 'z';
		const bool digit = character >= '0' && character <= '9';
		const bool current_separator = character == '.' || character == '_' || character == '-';
		if ((!lowercase && !digit && !current_separator) || (index == 0 && !lowercase) ||
				(separator && current_separator)) {
			return false;
		}
		separator = current_separator;
	}
	return !separator;
}
