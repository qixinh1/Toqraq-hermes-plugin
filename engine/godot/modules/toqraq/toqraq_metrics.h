// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

class ToqraqObservationState;

class ToqraqMetricsReader {
	ToqraqObservationState &state;

public:
	explicit ToqraqMetricsReader(ToqraqObservationState &p_state);
	ToqraqFeatureResult read(const Dictionary &p_params);
};
