// SPDX-License-Identifier: MIT

#include "toqraq_dispatcher.h"

#include "toqraq_input.h"
#include "toqraq_json.h"
#include "toqraq_limits.h"

#include <utility>

namespace {

constexpr const char *CANCEL_KEYS[] = { "target_request_id" };
constexpr const char *FAMILY_ORDER[] = {
	"hierarchy", "objects", "diagnostics", "metrics", "frame", "simulation"
};

} // namespace

ToqraqDispatcher::ToqraqDispatcher() :
		hierarchy(state),
		objects(state),
		diagnostics(state),
		metrics(state),
		frame(state),
		simulation(state) {}

bool ToqraqDispatcher::submit_text(const String &p_message) {
	ToqraqRpcRequest request;
	const ToqraqRpcDecodeStatus status = toqraq_decode_rpc_request(p_message, request);
	if (status == ToqraqRpcDecodeStatus::FATAL || request.sequence <= highest_sequence) {
		return false;
	}
	highest_sequence = request.sequence;
	if (status == ToqraqRpcDecodeStatus::ACCEPTED && request.method == ToqraqRpcMethod::REQUEST_CANCEL) {
		if (_has_cancel_control()) {
			return false;
		}
		_submit_cancel(request);
		return true;
	}
	if (_ordinary_outstanding() >= ToqraqLimits::MAX_IN_FLIGHT_REQUESTS) {
		return false;
	}
	if (status == ToqraqRpcDecodeStatus::METHOD_NOT_FOUND) {
		_schedule_fixed(request, toqraq_encode_rpc_error(request.id, -32601,
				"bridge.method_not_found", "invalid"));
		return true;
	}
	if (status == ToqraqRpcDecodeStatus::PARAMS_INVALID) {
		_schedule_fixed(request, toqraq_encode_rpc_error(request.id, -32602,
				"bridge.params_invalid", "invalid"));
		return true;
	}
	queued.push_back(request);
	return true;
}

void ToqraqDispatcher::_schedule_fixed(
		const ToqraqRpcRequest &p_request,
		const String &p_text,
		bool p_cancel_control) {
	ReadyResponse response;
	response.request_id = p_request.id;
	response.request_sequence = p_request.sequence;
	response.fixed_text = p_text;
	response.ready_poll = poll_sequence + 1;
	response.cancel_control = p_cancel_control;
	ready.push_back(response);
}

void ToqraqDispatcher::_schedule_cancelled(const String &p_request_id, int64_t p_sequence) {
	ToqraqRpcRequest request;
	request.id = p_request_id;
	request.sequence = p_sequence;
	_schedule_fixed(request, toqraq_encode_rpc_error(p_request_id, -32800,
			"request.cancelled", "conflict"));
}

void ToqraqDispatcher::_schedule_feature(
		const ToqraqRpcRequest &p_request,
		ToqraqFeatureResult &&p_response) {
	ReadyResponse response;
	response.request_id = p_request.id;
	response.request_sequence = p_request.sequence;
	response.response = std::move(p_response);
	response.ready_poll = poll_sequence + 1;
	ready.push_back(std::move(response));
}

void ToqraqDispatcher::_submit_cancel(const ToqraqRpcRequest &p_request) {
	if (!toqraq_has_exact_keys(p_request.params, CANCEL_KEYS, 1)) {
		_schedule_fixed(p_request, toqraq_encode_rpc_error(p_request.id, -32602,
				"bridge.params_invalid", "invalid"), true);
		return;
	}
	const Variant *target = p_request.params.getptr("target_request_id");
	String target_id;
	int64_t target_sequence = 0;
	if (target == nullptr || !toqraq_decode_host_request_id(*target, target_id, target_sequence) ||
			target_id == p_request.id) {
		_schedule_fixed(p_request, toqraq_encode_rpc_error(p_request.id, -32602,
				"bridge.params_invalid", "invalid"), true);
		return;
	}
	Dictionary result;
	result["disposition"] = _cancel_target(target_id, target_sequence);
	ReadyResponse response;
	response.request_id = p_request.id;
	response.request_sequence = p_request.sequence;
	response.response = toqraq_feature_success(result);
	response.ready_poll = poll_sequence + 1;
	response.cancel_control = true;
	ready.push_back(std::move(response));
}

int ToqraqDispatcher::_ordinary_outstanding() const {
	int count = queued.size() + (active_step_id.is_empty() ? 0 : 1);
	for (const ReadyResponse &response : ready) {
		if (!response.cancel_control) {
			count++;
		}
	}
	return count;
}

bool ToqraqDispatcher::_has_cancel_control() const {
	for (const ReadyResponse &response : ready) {
		if (response.cancel_control) {
			return true;
		}
	}
	return false;
}

String ToqraqDispatcher::_cancel_target(const String &p_id, int64_t p_sequence) {
	for (int index = 0; index < queued.size(); index++) {
		if (queued[index].id == p_id) {
			const int64_t sequence = queued[index].sequence;
			queued.remove_at(index);
			_schedule_cancelled(p_id, sequence);
			return "requested";
		}
	}
	for (int index = 0; index < ready.size(); index++) {
		if (ready[index].request_id == p_id) {
			const int64_t sequence = ready[index].request_sequence;
			_mark_dirty(ready[index].response.changed_families);
			ready.write[index].response.binary.fill(0);
			ready.remove_at(index);
			_schedule_cancelled(p_id, sequence);
			return "requested";
		}
	}
	if (active_step_id == p_id) {
		simulation.cancel_step();
		active_step_id.clear();
		active_step_sequence = 0;
		state.mark_hierarchy();
		state.mark_objects();
		state.mark_metrics();
		state.mark_simulation();
		state.mark_frame();
		Array families;
		families.push_back("hierarchy");
		families.push_back("objects");
		families.push_back("metrics");
		families.push_back("frame");
		families.push_back("simulation");
		_mark_dirty(families);
		_schedule_cancelled(p_id, p_sequence);
		return "requested";
	}
	return p_sequence <= highest_sequence ? "already_terminal" : "not_found";
}

Vector<ToqraqOutboundMessage> ToqraqDispatcher::poll() {
	poll_sequence++;
	Vector<ToqraqOutboundMessage> messages;
	if (state.observe_tree()) {
		Array changed;
		changed.push_back("hierarchy");
		changed.push_back("objects");
		_mark_dirty(changed);
	}
	if (diagnostics.synchronize()) {
		Array changed;
		changed.push_back("diagnostics");
		_mark_dirty(changed);
	}
	if (!active_step_id.is_empty()) {
		ToqraqFeatureResult completed;
		if (simulation.tick(completed)) {
			ToqraqRpcRequest request;
			request.id = active_step_id;
			request.sequence = active_step_sequence;
			_schedule_feature(request, std::move(completed));
			active_step_id.clear();
			active_step_sequence = 0;
		}
	}
	_emit_ready(messages);
	_start_next();
	_emit_state_changed(messages);
	return messages;
}

void ToqraqDispatcher::_start_next() {
	if (!active_step_id.is_empty() || queued.is_empty()) {
		return;
	}
	const ToqraqRpcRequest request = queued[0];
	queued.remove_at(0);
	if (request.method == ToqraqRpcMethod::SIMULATION_STEP) {
		ToqraqStepStart start = simulation.start_step(request.params);
		if (start.started) {
			active_step_id = request.id;
			active_step_sequence = request.sequence;
		} else {
			_schedule_feature(request, std::move(start.response));
		}
		return;
	}
	_schedule_feature(request, _execute(request));
}

ToqraqFeatureResult ToqraqDispatcher::_execute(const ToqraqRpcRequest &p_request) {
	switch (p_request.method) {
		case ToqraqRpcMethod::HIERARCHY_READ:
			return hierarchy.read(p_request.params);
		case ToqraqRpcMethod::OBJECT_READ:
			return objects.read(p_request.params);
		case ToqraqRpcMethod::DIAGNOSTICS_READ:
			return diagnostics.read(p_request.params);
		case ToqraqRpcMethod::METRICS_READ:
			return metrics.read(p_request.params);
		case ToqraqRpcMethod::FRAME_CAPTURE:
			return frame.capture(p_request.params);
		case ToqraqRpcMethod::SIMULATION_SET_PAUSED:
			return simulation.set_paused(p_request.params);
		case ToqraqRpcMethod::INPUT_SEMANTIC:
		case ToqraqRpcMethod::INPUT_KEYBOARD:
		case ToqraqRpcMethod::INPUT_POINTER:
		case ToqraqRpcMethod::INPUT_TEXT:
		case ToqraqRpcMethod::INPUT_GAMEPAD: {
			const ToqraqInputDispatchResult input =
					toqraq_dispatch_input(p_request.method_name, p_request.params);
			ToqraqFeatureResult response;
			response.succeeded = input.succeeded;
			response.result = input.result;
			response.error_code = input.error_code;
			response.error_category = input.error_category;
			response.error_details = input.error_details;
			if (input.succeeded) {
				_mark_input_state();
				response.changed_families.push_back("hierarchy");
				response.changed_families.push_back("objects");
				response.changed_families.push_back("metrics");
				response.changed_families.push_back("frame");
			}
			return response;
		}
		case ToqraqRpcMethod::SIMULATION_STEP:
		case ToqraqRpcMethod::REQUEST_CANCEL:
			break;
	}
	return toqraq_feature_error("bridge.remote_internal", "internal");
}

void ToqraqDispatcher::_mark_input_state() {
	state.mark_hierarchy();
	state.mark_objects();
	state.mark_metrics();
	state.mark_frame();
}

String ToqraqDispatcher::_encode_feature(
		const String &p_request_id,
		const ToqraqFeatureResult &p_response,
		bool &r_encoded_success) const {
	r_encoded_success = false;
	String text;
	if (p_response.succeeded) {
		text = toqraq_encode_rpc_success(p_request_id, p_response.result);
	} else if (p_response.error_code == "bridge.params_invalid") {
		text = toqraq_encode_rpc_error(p_request_id, -32602, "bridge.params_invalid", "invalid");
	} else if (p_response.error_category == "internal") {
		text = toqraq_encode_rpc_error(p_request_id, -32603, "bridge.remote_internal", "internal");
	} else {
		text = toqraq_encode_rpc_error(p_request_id, -32000, p_response.error_code,
				p_response.error_category, Dictionary(), p_response.error_details);
	}
	if (text.utf8().length() <= ToqraqLimits::MAX_TEXT_MESSAGE_BYTES) {
		r_encoded_success = p_response.succeeded;
		return text;
	}
	return toqraq_encode_rpc_error(p_request_id, -32000,
			"perception.capability_unavailable", "unavailable");
}

void ToqraqDispatcher::_mark_dirty(const Array &p_families) {
	for (int index = 0; index < p_families.size(); index++) {
		for (int family = 0; family < 6; family++) {
			if (p_families[index] == FAMILY_ORDER[family]) {
				dirty_families[family] = true;
				if (family == 0) {
					hierarchy.invalidate();
				}
			}
		}
	}
}

void ToqraqDispatcher::_emit_ready(Vector<ToqraqOutboundMessage> &r_messages) {
	for (int index = 0; index < ready.size();) {
		if (ready[index].ready_poll > poll_sequence) {
			index++;
			continue;
		}
		ReadyResponse response = std::move(ready.write[index]);
		ready.remove_at(index);
		ToqraqOutboundMessage message;
		bool encoded_success = false;
		message.text = response.fixed_text.is_empty() ?
				_encode_feature(response.request_id, response.response, encoded_success) : response.fixed_text;
		if (encoded_success) {
			message.binary = std::move(response.response.binary);
		} else {
			response.response.binary.fill(0);
		}
		_mark_dirty(response.response.changed_families);
		r_messages.push_back(std::move(message));
	}
}

void ToqraqDispatcher::_emit_state_changed(Vector<ToqraqOutboundMessage> &r_messages) {
	Array families;
	for (int index = 0; index < 6; index++) {
		if (dirty_families[index]) {
			families.push_back(FAMILY_ORDER[index]);
			dirty_families[index] = false;
		}
	}
	if (families.is_empty()) {
		return;
	}
	ToqraqOutboundMessage notification;
	notification.text = toqraq_encode_state_changed(families);
	r_messages.push_back(notification);
}

void ToqraqDispatcher::clear() {
	simulation.cancel_step();
	for (ReadyResponse &response : ready) {
		response.response.binary.fill(0);
	}
	queued.clear();
	ready.clear();
	active_step_id.clear();
	diagnostics.clear();
	hierarchy.invalidate();
	state.clear();
}
