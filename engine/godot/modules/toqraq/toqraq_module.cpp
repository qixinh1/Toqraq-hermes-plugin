// SPDX-License-Identifier: MIT

#include "toqraq_module.h"

#include "toqraq_diagnostic_log.h"
#include "toqraq_launch.h"
#include "toqraq_transport.h"

#include "core/error/error_macros.h"
#include "core/os/memory.h"
#include "scene/main/scene_tree.h"

#include <utility>

bool ToqraqModule::callback_registered = false;
bool ToqraqModule::enabled = false;
ToqraqBridge *ToqraqModule::owner = nullptr;

void ToqraqModule::initialize() {
	if (enabled) {
		return;
	}
	ToqraqLaunchData launch;
	const ToqraqActivationStatus activation = toqraq_read_activation(launch);
	if (activation != ToqraqActivationStatus::READY) {
		if (activation == ToqraqActivationStatus::REJECTED) {
			ERR_PRINT("Toqraq bridge activation was rejected.");
		}
		launch.clear();
		return;
	}
	if (!ToqraqDiagnosticLog::activate()) {
		launch.clear();
		return;
	}
	owner = memnew(ToqraqBridge(std::move(launch)));
	if (!callback_registered) {
		SceneTree::add_idle_callback(_idle);
		callback_registered = true;
	}
	enabled = true;
	launch.clear();
}

void ToqraqModule::uninitialize() {
	const bool was_enabled = enabled;
	enabled = false;
	if (owner != nullptr) {
		owner->close();
		memdelete(owner);
		owner = nullptr;
	}
	if (was_enabled) {
		ToqraqDiagnosticLog::deactivate();
	}
}

void ToqraqModule::_idle() {
	if (!enabled || owner == nullptr) {
		return;
	}
	owner->poll();
}
