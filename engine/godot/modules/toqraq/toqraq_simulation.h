// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

class ToqraqObservationState;

struct ToqraqStepStart {
	bool started = false;
	ToqraqFeatureResult response;
};

class ToqraqSimulationControl {
	ToqraqObservationState &state;
	bool stepping = false;
	int requested_frames = 0;
	int remaining_frames = 0;
	uint64_t last_process_frame = 0;

public:
	explicit ToqraqSimulationControl(ToqraqObservationState &p_state);
	ToqraqFeatureResult set_paused(const Dictionary &p_params);
	ToqraqStepStart start_step(const Dictionary &p_params);
	bool tick(ToqraqFeatureResult &r_response);
	void cancel_step();
	bool is_stepping() const;
};
