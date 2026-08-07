// SPDX-License-Identifier: MIT

#pragma once

class ToqraqModule {
	static bool callback_registered;
	static bool enabled;
	static class ToqraqBridge *owner;

	static void _idle();

public:
	static void initialize();
	static void uninitialize();
};
