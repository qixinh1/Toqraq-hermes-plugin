// SPDX-License-Identifier: MIT

#include "toqraq_identity.h"

#include "core/version.h"
#include "core/variant/variant.h"

#ifndef TOQRAQ_BUILD_ID
#error "TOQRAQ_BUILD_ID must be compiled into the bridge"
#endif

#ifndef TOQRAQ_DISTRIBUTION_ID
#error "TOQRAQ_DISTRIBUTION_ID must be compiled into the bridge"
#endif

#ifndef WINDOWS_ENABLED
#error "The current Toqraq bridge contribution supports Windows only"
#endif

namespace ToqraqIdentity {

String engine_version() {
	return String(GODOT_VERSION_NUMBER) + "-" + GODOT_VERSION_STATUS;
}

String build_id() {
	return TOQRAQ_BUILD_ID;
}

String distribution_id() {
	return TOQRAQ_DISTRIBUTION_ID;
}

String platform() {
	return "windows";
}

String architecture() {
#if defined(_M_X64) || defined(__x86_64__)
	return "x86_64";
#elif defined(_M_IX86) || defined(__i386__)
	return "x86_32";
#elif defined(_M_ARM64) || defined(__aarch64__)
	return "arm64";
#elif defined(_M_ARM) || defined(__arm__)
	return "arm32";
#else
#error "The Toqraq bridge cannot identify this compiled architecture"
#endif
}

Array capabilities() {
	Array values;
	values.push_back("toqraq.control.input");
	values.push_back("toqraq.observe.diagnostics");
	values.push_back("toqraq.observe.frame");
	values.push_back("toqraq.observe.hierarchy");
	values.push_back("toqraq.observe.performance");
	values.push_back("toqraq.observe.properties");
	values.push_back("toqraq.play.pause");
	values.push_back("toqraq.play.step");
	return values;
}

} // namespace ToqraqIdentity
