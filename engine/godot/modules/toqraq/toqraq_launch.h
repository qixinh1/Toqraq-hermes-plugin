// SPDX-License-Identifier: MIT

#pragma once

#include "core/string/ustring.h"

enum class ToqraqActivationStatus {
	DISABLED,
	READY,
	REJECTED,
};

struct ToqraqLaunchData {
	String endpoint;
	String credential;
	String session_id;
	int64_t run_revision = 0;

	void clear_credential();
	void clear();
};

bool toqraq_is_bridge_endpoint(const String &p_endpoint);
bool toqraq_parse_bootstrap(const String &p_json, ToqraqLaunchData &r_launch);
ToqraqActivationStatus toqraq_read_activation(ToqraqLaunchData &r_launch);
