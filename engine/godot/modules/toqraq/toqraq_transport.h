// SPDX-License-Identifier: MIT

#pragma once

#include "toqraq_dispatcher.h"
#include "toqraq_launch.h"

#include "modules/websocket/websocket_peer.h"

class ToqraqBridge {
	enum class State {
		WAITING_FOR_SCENE,
		CONNECTING,
		WAITING_FOR_HANDSHAKE,
		AUTHENTICATED,
		CLOSED,
	};

	static constexpr uint64_t CONNECT_TIMEOUT_MSEC = 5000;
	static constexpr uint64_t HANDSHAKE_TIMEOUT_MSEC = 5000;
	ToqraqLaunchData launch;
	Ref<WebSocketPeer> peer;
	ToqraqDispatcher dispatcher;
	State state = State::WAITING_FOR_SCENE;
	uint64_t state_started_msec = 0;

	void _connect();
	void _poll_connecting(uint64_t p_now);
	void _poll_handshake(uint64_t p_now);
	void _poll_authenticated();
	bool _receive_authenticated();
	bool _send_authenticated();
	void _send_handshake(uint64_t p_now);
	void _reject(int p_close_code);

public:
	explicit ToqraqBridge(ToqraqLaunchData &&p_launch);
	~ToqraqBridge();

	void poll();
	void close();
};
