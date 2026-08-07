// SPDX-License-Identifier: MIT

#include "toqraq_simulation.h"

#include "toqraq_json.h"
#include "toqraq_observation_state.h"

#include "core/config/engine.h"
#include "scene/main/scene_tree.h"

namespace {

constexpr const char *PAUSE_KEYS[] = { "paused" };
constexpr const char *STEP_KEYS[] = { "frame_count" };

void _mark_pause_changed(ToqraqObservationState &p_state, ToqraqFeatureResult &r_result) {
	p_state.mark_simulation();
	p_state.mark_frame();
	p_state.mark_metrics();
	r_result.changed_families.push_back("frame");
	r_result.changed_families.push_back("metrics");
	r_result.changed_families.push_back("simulation");
}

void _mark_step_changed(ToqraqObservationState &p_state, ToqraqFeatureResult &r_result) {
	p_state.mark_hierarchy();
	p_state.mark_objects();
	p_state.mark_metrics();
	p_state.mark_frame();
	p_state.mark_simulation();
	r_result.changed_families.push_back("hierarchy");
	r_result.changed_families.push_back("objects");
	r_result.changed_families.push_back("metrics");
	r_result.changed_families.push_back("frame");
	r_result.changed_families.push_back("simulation");
}

Dictionary _step_result(int p_frames, const ToqraqObservationState &p_state) {
	Dictionary result;
	result["frame_count"] = p_frames;
	result["paused"] = true;
	result["simulation_revision"] = p_state.simulation();
	result["frame_revision"] = p_state.frame();
	return result;
}

} // namespace

ToqraqSimulationControl::ToqraqSimulationControl(ToqraqObservationState &p_state) :
		state(p_state) {}

ToqraqFeatureResult ToqraqSimulationControl::set_paused(const Dictionary &p_params) {
	if (!toqraq_has_exact_keys(p_params, PAUSE_KEYS, 1)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	const Variant *paused = p_params.getptr("paused");
	if (paused == nullptr || paused->get_type() != Variant::BOOL) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	SceneTree *tree = SceneTree::get_singleton();
	if (tree == nullptr || stepping) {
		return toqraq_feature_error("simulation.invalid_state", "conflict");
	}
	const bool desired = *paused;
	const bool changed = tree->is_paused() != desired;
	if (changed) {
		tree->set_pause(desired);
	}
	Dictionary result;
	result["paused"] = tree->is_paused();
	result["changed"] = changed;
	ToqraqFeatureResult response = toqraq_feature_success(result);
	if (changed) {
		_mark_pause_changed(state, response);
	}
	response.result["simulation_revision"] = state.simulation();
	response.result["frame_revision"] = state.frame();
	return response;
}

ToqraqStepStart ToqraqSimulationControl::start_step(const Dictionary &p_params) {
	ToqraqStepStart start;
	if (!toqraq_has_exact_keys(p_params, STEP_KEYS, 1)) {
		start.response = toqraq_feature_error("bridge.params_invalid", "invalid");
		return start;
	}
	const Variant *frame_count = p_params.getptr("frame_count");
	int64_t frames = 0;
	if (frame_count == nullptr || !toqraq_read_json_integer(*frame_count, frames) ||
			frames < 1 || frames > 120) {
		start.response = toqraq_feature_error("bridge.params_invalid", "invalid");
		return start;
	}
	SceneTree *tree = SceneTree::get_singleton();
	if (tree == nullptr || !tree->is_paused() || stepping) {
		start.response = toqraq_feature_error("simulation.invalid_state", "conflict");
		return start;
	}
	requested_frames = frames;
	remaining_frames = frames;
	last_process_frame = Engine::get_singleton()->get_process_frames();
	stepping = true;
	tree->set_pause(false);
	start.started = true;
	return start;
}

bool ToqraqSimulationControl::tick(ToqraqFeatureResult &r_response) {
	if (!stepping) {
		return false;
	}
	const uint64_t process_frame = Engine::get_singleton()->get_process_frames();
	if (process_frame <= last_process_frame) {
		return false;
	}
	const uint64_t advanced = process_frame - last_process_frame;
	last_process_frame = process_frame;
	remaining_frames -= MIN((uint64_t)remaining_frames, advanced);
	if (remaining_frames > 0) {
		return false;
	}
	SceneTree *tree = SceneTree::get_singleton();
	if (tree == nullptr) {
		stepping = false;
		r_response = toqraq_feature_error("simulation.invalid_state", "conflict");
		return true;
	}
	tree->set_pause(true);
	stepping = false;
	r_response = toqraq_feature_success(Dictionary());
	_mark_step_changed(state, r_response);
	r_response.result = _step_result(requested_frames, state);
	return true;
}

void ToqraqSimulationControl::cancel_step() {
	if (!stepping) {
		return;
	}
	if (SceneTree *tree = SceneTree::get_singleton()) {
		tree->set_pause(true);
	}
	stepping = false;
	remaining_frames = 0;
}

bool ToqraqSimulationControl::is_stepping() const {
	return stepping;
}
