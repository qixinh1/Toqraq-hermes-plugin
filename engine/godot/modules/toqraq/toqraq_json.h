// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"
#include "core/variant/variant.h"

int toqraq_count_json_members(const String &p_json);
bool toqraq_read_json_integer(const Variant &p_value, int64_t &r_value);
bool toqraq_read_json_float(const Variant &p_value, double &r_value);
bool toqraq_decode_bounded_json(const String &p_json, int p_maximum_bytes, Variant &r_value);
bool toqraq_has_exact_keys(const Dictionary &p_value, const char *const *p_keys, int p_key_count);
bool toqraq_is_bounded_utf8(const String &p_value, int p_maximum_bytes, bool p_allow_empty = false);
bool toqraq_is_observation_label(const String &p_value, int p_maximum_bytes);
bool toqraq_is_observation_token(const String &p_value);
bool toqraq_is_namespaced_id(const String &p_value);
