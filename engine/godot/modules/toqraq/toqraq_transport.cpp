// SPDX-License-Identifier: MIT

#include "toqraq_transport.h"

#include "toqraq_limits.h"
#include "toqraq_protocol.h"

#include "core/os/os.h"
#include "scene/main/scene_tree.h"

#include <utility>

namespace {

constexpr int POLICY_CLOSE_CODE = 1008;
constexpr int OWNER_CLOSE_CODE = 1001;

} // namespace

ToqraqBridge::ToqraqBridge(ToqraqLaunchData &&p_launch) :
		launch(std::move(p_launch)) {
	p_launch.clear();
}

ToqraqBridge::~ToqraqBridge() {
	close();
}

void ToqraqBridge::poll() {
	if (state == State::CLOSED) {
		return;
	}
	if (state == State::WAITING_FOR_SCENE) {
		if (SceneTree::get_singleton() == nullptr) {
			return;
		}
		_connect();
		if (state == State::CLOSED) {
			return;
		}
	}

	peer->poll();
	const uint64_t now = OS::get_singleton()->get_ticks_msec();
	switch (state) {
		case State::CONNECTING:
			_poll_connecting(now);
			break;
		case State::WAITING_FOR_HANDSHAKE:
			_poll_handshake(now);
			break;
		case State::AUTHENTICATED:
			_poll_authenticated();
			break;
		case State::WAITING_FOR_SCENE:
		case State::CLOSED:
			break;
	}
}

void ToqraqBridge::_connect() {
	peer = Ref<WebSocketPeer>(WebSocketPeer::create());
	if (peer.is_null()) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	peer->set_inbound_buffer_size(ToqraqLimits::MAX_TEXT_MESSAGE_BYTES);
	peer->set_outbound_buffer_size(
			ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES + ToqraqLimits::TRANSFER_PREFIX_BYTES);
	peer->set_max_queued_packets(ToqraqLimits::MAX_QUEUED_PACKETS);
	const Error connect_error = peer->connect_to_url(launch.endpoint);
	if (connect_error != OK) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	state = State::CONNECTING;
	state_started_msec = OS::get_singleton()->get_ticks_msec();
}

void ToqraqBridge::_poll_connecting(uint64_t p_now) {
	const WebSocketPeer::State ready = peer->get_ready_state();
	if (ready == WebSocketPeer::STATE_OPEN) {
		_send_handshake(p_now);
		return;
	}
	if (ready != WebSocketPeer::STATE_CONNECTING || p_now - state_started_msec >= CONNECT_TIMEOUT_MSEC) {
		_reject(POLICY_CLOSE_CODE);
	}
}

void ToqraqBridge::_send_handshake(uint64_t p_now) {
	String request = toqraq_encode_handshake_request(launch);
	const int encoded_bytes = request.utf8().length();
	const Error send_error = encoded_bytes > 0 && encoded_bytes <= ToqraqLimits::MAX_TEXT_MESSAGE_BYTES ? peer->send_text(request) : ERR_INVALID_DATA;
	launch.clear_credential();
	request.clear();
	if (send_error != OK) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	state = State::WAITING_FOR_HANDSHAKE;
	state_started_msec = p_now;
}

void ToqraqBridge::_poll_handshake(uint64_t p_now) {
	if (peer->get_ready_state() != WebSocketPeer::STATE_OPEN) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	if (p_now - state_started_msec >= HANDSHAKE_TIMEOUT_MSEC) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	const int packet_count = peer->get_available_packet_count();
	if (packet_count == 0) {
		return;
	}
	Vector<uint8_t> packet;
	if (peer->get_packet_buffer(packet) != OK || !peer->was_string_packet() || packet.is_empty() ||
			packet.size() > ToqraqLimits::MAX_TEXT_MESSAGE_BYTES) {
		packet.fill(0);
		packet.clear();
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	String response;
	const Error decode_error = response.append_utf8((const char *)packet.ptr(), packet.size());
	packet.fill(0);
	packet.clear();
	if (decode_error != OK) {
		response.clear();
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	const ToqraqHandshakeDecision decision = toqraq_decode_handshake_response(response, launch);
	response.clear();
	launch.session_id.clear();
	launch.run_revision = 0;
	if (decision != ToqraqHandshakeDecision::ACCEPTED) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	state = State::AUTHENTICATED;
	state_started_msec = 0;
}

void ToqraqBridge::_poll_authenticated() {
	if (peer->get_ready_state() != WebSocketPeer::STATE_OPEN) {
		_reject(POLICY_CLOSE_CODE);
		return;
	}
	if (!_receive_authenticated() || !_send_authenticated()) {
		_reject(POLICY_CLOSE_CODE);
	}
}

bool ToqraqBridge::_receive_authenticated() {
	const int available = peer->get_available_packet_count();
	if (available > ToqraqLimits::MAX_IN_FLIGHT_REQUESTS + 1) {
		return false;
	}
	for (int index = 0; index < available; index++) {
		Vector<uint8_t> packet;
		if (peer->get_packet_buffer(packet) != OK || !peer->was_string_packet() || packet.is_empty() ||
				packet.size() > ToqraqLimits::MAX_TEXT_MESSAGE_BYTES) {
			packet.fill(0);
			return false;
		}
		String message;
		const Error decode_error = message.append_utf8((const char *)packet.ptr(), packet.size());
		packet.fill(0);
		packet.clear();
		if (decode_error != OK || !dispatcher.submit_text(message)) {
			message.clear();
			return false;
		}
		message.clear();
	}
	return true;
}

bool ToqraqBridge::_send_authenticated() {
	Vector<ToqraqOutboundMessage> messages = dispatcher.poll();
	for (ToqraqOutboundMessage &message : messages) {
		if (message.text.is_empty() || message.text.utf8().length() > ToqraqLimits::MAX_TEXT_MESSAGE_BYTES ||
				peer->send_text(message.text) != OK) {
			message.binary.fill(0);
			return false;
		}
		message.text.clear();
		if (!message.binary.is_empty()) {
			if (message.binary.size() > ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES + ToqraqLimits::TRANSFER_PREFIX_BYTES ||
					peer->send(message.binary.ptr(), message.binary.size(), WebSocketPeer::WRITE_MODE_BINARY) != OK) {
				message.binary.fill(0);
				return false;
			}
			message.binary.fill(0);
			message.binary.clear();
		}
	}
	return true;
}

void ToqraqBridge::_reject(int p_close_code) {
	launch.clear();
	dispatcher.clear();
	if (peer.is_valid()) {
		const WebSocketPeer::State ready = peer->get_ready_state();
		if (ready == WebSocketPeer::STATE_OPEN || ready == WebSocketPeer::STATE_CLOSING) {
			peer->close(p_close_code);
		}
		peer.unref();
	}
	state = State::CLOSED;
	state_started_msec = 0;
}

void ToqraqBridge::close() {
	if (state == State::CLOSED) {
		return;
	}
	_reject(OWNER_CLOSE_CODE);
}
