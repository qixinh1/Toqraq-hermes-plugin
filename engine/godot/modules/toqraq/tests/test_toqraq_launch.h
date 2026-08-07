// SPDX-License-Identifier: MIT

#pragma once

#include "../toqraq_launch.h"

#include "tests/test_macros.h"

namespace TestToqraqLaunch {

constexpr const char *CREDENTIAL = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

String valid_bootstrap() {
	return String("{\"credential\":\"") + CREDENTIAL +
			"\",\"session_id\":\"session-1\",\"run_revision\":7}";
}

TEST_CASE("[Toqraq] bridge endpoint is exact loopback URL") {
	CHECK(toqraq_is_bridge_endpoint("ws://127.0.0.1:1/toqraq/bridge"));
	CHECK(toqraq_is_bridge_endpoint("ws://127.0.0.1:65535/toqraq/bridge"));
	CHECK_FALSE(toqraq_is_bridge_endpoint("ws://localhost:80/toqraq/bridge"));
	CHECK_FALSE(toqraq_is_bridge_endpoint("ws://127.0.0.1:080/toqraq/bridge"));
	CHECK_FALSE(toqraq_is_bridge_endpoint("ws://127.0.0.1:65536/toqraq/bridge"));
	CHECK_FALSE(toqraq_is_bridge_endpoint("ws://127.0.0.1:80/other"));
}

TEST_CASE("[Toqraq] bootstrap accepts only exact bounded launch fields") {
	ToqraqLaunchData launch;
	CHECK(toqraq_parse_bootstrap(valid_bootstrap(), launch));
	CHECK(launch.credential == CREDENTIAL);
	CHECK(launch.session_id == "session-1");
	CHECK(launch.run_revision == 7);
	launch.clear();

	CHECK_FALSE(toqraq_parse_bootstrap(
			String("{\"credential\":\"") + CREDENTIAL +
					"\",\"session_id\":\"session-1\",\"run_revision\":7,\"run_revision\":8}",
			launch));
	CHECK(launch.session_id.is_empty());
	CHECK(launch.run_revision == 0);
	CHECK_FALSE(toqraq_parse_bootstrap(
			String("{\"credential\":\"") + CREDENTIAL +
					"\",\"session_id\":\"session-1\",\"run_revision\":7,\"extra\":true}",
			launch));
	CHECK_FALSE(toqraq_parse_bootstrap(
			String("{\"credential\":\"") + CREDENTIAL +
					"\",\"\\u0073ession_id\":\"session-1\",\"session_id\":\"session-2\",\"run_revision\":7}",
			launch));
	CHECK_FALSE(toqraq_parse_bootstrap(
			"{\"credential\":\"ABC\",\"session_id\":\"session-1\",\"run_revision\":7}",
			launch));
	CHECK_FALSE(toqraq_parse_bootstrap(
			String("{\"credential\":\"") + CREDENTIAL +
					"\",\"session_id\":\"session\\n1\",\"run_revision\":7}",
			launch));
	CHECK_FALSE(toqraq_parse_bootstrap(
			String("{\"credential\":\"") + CREDENTIAL +
					"\",\"session_id\":\"session-1\",\"run_revision\":9007199254740992}",
			launch));
	CHECK(launch.credential.is_empty());
}

TEST_CASE("[Toqraq] bootstrap enforces the exact byte boundary") {
	ToqraqLaunchData launch;
	const String base = valid_bootstrap();
	const int padding = 4096 - base.utf8().length();
	const String at_limit = base + String(" ").repeat(padding);
	CHECK(at_limit.utf8().length() == 4096);
	CHECK(toqraq_parse_bootstrap(at_limit, launch));
	launch.clear();
	CHECK_FALSE(toqraq_parse_bootstrap(at_limit + " ", launch));
}

} // namespace TestToqraqLaunch
