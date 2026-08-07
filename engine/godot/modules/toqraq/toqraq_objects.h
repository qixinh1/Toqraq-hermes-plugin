// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

class ToqraqObservationState;

class ToqraqObjectReader {
	ToqraqObservationState &state;

public:
	explicit ToqraqObjectReader(ToqraqObservationState &p_state);
	ToqraqFeatureResult read(const Dictionary &p_params);
};
