// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

class ToqraqObservationState;

class ToqraqFrameCapture {
	ToqraqObservationState &state;

public:
	explicit ToqraqFrameCapture(ToqraqObservationState &p_state);
	ToqraqFeatureResult capture(const Dictionary &p_params);
};
