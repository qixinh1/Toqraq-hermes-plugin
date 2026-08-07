// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_feature_result.h"

#include "core/templates/hash_map.h"

class ToqraqObservationState;

class ToqraqDiagnosticsReader {
	struct CursorState {
		String revision;
		String query_key;
		int matched_offset = 0;
	};

	ToqraqObservationState &state;
	HashMap<String, CursorState> cursors;
	int64_t next_cursor = 1;
	uint64_t last_generation = 0;

	bool _synchronize(uint64_t p_generation);

public:
	explicit ToqraqDiagnosticsReader(ToqraqObservationState &p_state);
	bool synchronize();
	ToqraqFeatureResult read(const Dictionary &p_params);
	void clear();
};
