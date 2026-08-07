// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

#include "core/templates/hash_map.h"

class ToqraqObservationState;

class ToqraqHierarchyReader {
	struct CursorState {
		String revision;
		String query_key;
		int matched_offset = 0;
	};

	ToqraqObservationState &state;
	HashMap<String, CursorState> cursors;
	int64_t next_cursor = 1;

public:
	explicit ToqraqHierarchyReader(ToqraqObservationState &p_state);
	ToqraqFeatureResult read(const Dictionary &p_params);
	void invalidate();
};
