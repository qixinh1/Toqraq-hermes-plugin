// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_input.h"

#include "core/input/input_event.h"
#include "core/templates/vector.h"
#include "core/variant/array.h"

namespace ToqraqInputContract {

constexpr int MAX_EVENTS = 128;
constexpr double MAX_POINTER_VALUE = 1000000.0;
constexpr double MAX_WHEEL_VALUE = 10000.0;

ToqraqInputDispatchResult invalid();
ToqraqInputDispatchResult rejected(const String &p_reason);
ToqraqInputDispatchResult success(int p_count);

bool read_bool(const Dictionary &p_value, const char *p_key, bool &r_value);
bool read_float(const Dictionary &p_value, const char *p_key, double p_minimum, double p_maximum, double &r_value);
bool read_string(const Dictionary &p_value, const char *p_key, String &r_value);
bool read_slot(const Dictionary &p_value, const char *p_key, int p_maximum, int &r_value);
bool read_events(const Dictionary &p_params, Array &r_events);
bool commit(const Vector<Ref<InputEvent>> &p_events);

} // namespace ToqraqInputContract
