// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_diagnostics.h"
#include "toqraq_frame.h"
#include "toqraq_hierarchy.h"
#include "toqraq_metrics.h"
#include "toqraq_objects.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"
#include "toqraq_simulation.h"

struct ToqraqOutboundMessage {
	String text;
	Vector<uint8_t> binary;
};

class ToqraqDispatcher {
	struct ReadyResponse {
		String request_id;
		int64_t request_sequence = 0;
		ToqraqFeatureResult response;
		String fixed_text;
		uint64_t ready_poll = 0;
		bool cancel_control = false;
	};

	ToqraqObservationState state;
	ToqraqHierarchyReader hierarchy;
	ToqraqObjectReader objects;
	ToqraqDiagnosticsReader diagnostics;
	ToqraqMetricsReader metrics;
	ToqraqFrameCapture frame;
	ToqraqSimulationControl simulation;
	Vector<ToqraqRpcRequest> queued;
	Vector<ReadyResponse> ready;
	String active_step_id;
	int64_t active_step_sequence = 0;
	int64_t highest_sequence = 0;
	uint64_t poll_sequence = 0;
	bool dirty_families[6] = {};

	void _schedule_fixed(const ToqraqRpcRequest &p_request, const String &p_text, bool p_cancel_control = false);
	void _schedule_cancelled(const String &p_request_id, int64_t p_sequence);
	void _schedule_feature(const ToqraqRpcRequest &p_request, ToqraqFeatureResult &&p_response);
	void _submit_cancel(const ToqraqRpcRequest &p_request);
	String _cancel_target(const String &p_id, int64_t p_sequence);
	void _start_next();
	ToqraqFeatureResult _execute(const ToqraqRpcRequest &p_request);
	String _encode_feature(
			const String &p_request_id,
			const ToqraqFeatureResult &p_response,
			bool &r_encoded_success) const;
	int _ordinary_outstanding() const;
	bool _has_cancel_control() const;
	void _mark_dirty(const Array &p_families);
	void _mark_input_state();
	void _emit_ready(Vector<ToqraqOutboundMessage> &r_messages);
	void _emit_state_changed(Vector<ToqraqOutboundMessage> &r_messages);

public:
	ToqraqDispatcher();
	bool submit_text(const String &p_message);
	Vector<ToqraqOutboundMessage> poll();
	void clear();
};
