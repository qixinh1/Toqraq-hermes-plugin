// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"
#include "core/variant/array.h"

namespace ToqraqIdentity {

String engine_version();
String build_id();
String distribution_id();
String platform();
String architecture();
Array capabilities();

} // namespace ToqraqIdentity
