// SPDX-License-Identifier: MIT

#include "toqraq_diagnostic_log.h"

#include "toqraq_json.h"
#include "toqraq_limits.h"

#include "core/math/math_funcs.h"
#include "core/os/memory.h"
#include "core/os/os.h"

#include <cstdio>
#include <cstring>

namespace {

constexpr int MAX_RECORDS = 512;
constexpr int MAX_SUMMARY_BYTES = 512;
constexpr int MAX_RESOURCE_BYTES = 1024;
constexpr int FORMAT_BUFFER_BYTES = 2048;

int _utf8_prefix(const char *p_text, int p_length, int p_limit) {
	const int limit = MIN(p_length, p_limit);
	int index = 0;
	int valid = 0;
	while (index < limit) {
		const uint8_t first = (uint8_t)p_text[index];
		int width = 0;
		if (first >= 0x01 && first <= 0x7f) {
			width = 1;
		} else if (first >= 0xc2 && first <= 0xdf) {
			width = 2;
		} else if (first >= 0xe0 && first <= 0xef) {
			width = 3;
		} else if (first >= 0xf0 && first <= 0xf4) {
			width = 4;
		} else {
			break;
		}
		if (index + width > limit) {
			break;
		}
		bool continuation_valid = true;
		for (int offset = 1; offset < width; offset++) {
			continuation_valid = continuation_valid &&
					(((uint8_t)p_text[index + offset] & 0xc0) == 0x80);
		}
		if (!continuation_valid) {
			break;
		}
		const uint8_t second = width > 1 ? (uint8_t)p_text[index + 1] : 0;
		if ((first == 0xe0 && second < 0xa0) || (first == 0xed && second > 0x9f) ||
				(first == 0xf0 && second < 0x90) || (first == 0xf4 && second > 0x8f)) {
			break;
		}
		index += width;
		valid = index;
	}
	return valid;
}

String _formatted_summary(const char *p_format, va_list p_list) {
	if (p_format == nullptr) {
		return "Godot emitted an empty diagnostic.";
	}
	char buffer[FORMAT_BUFFER_BYTES + 1] = {};
	va_list copy;
	va_copy(copy, p_list);
	const int written = vsnprintf(buffer, FORMAT_BUFFER_BYTES + 1, p_format, copy);
	va_end(copy);
	if (written <= 0) {
		return "Godot emitted an empty diagnostic.";
	}
	const bool truncated = written > MAX_SUMMARY_BYTES;
	const int byte_limit = truncated ? MAX_SUMMARY_BYTES - 3 : MAX_SUMMARY_BYTES;
	const int valid = _utf8_prefix(buffer, MIN(written, FORMAT_BUFFER_BYTES), byte_limit);
	String result = valid > 0 ? String::utf8(buffer, valid) : String("Godot emitted an invalid diagnostic.");
	return truncated ? result + "..." : result;
}

String _bounded_text(const char *p_text, int p_maximum_bytes, const char *p_fallback) {
	if (p_text == nullptr || p_text[0] == '\0') {
		return p_fallback;
	}
	const int length = (int)strnlen(p_text, p_maximum_bytes + 1);
	const int valid = _utf8_prefix(p_text, length, p_maximum_bytes);
	return valid > 0 ? String::utf8(p_text, valid) : String(p_fallback);
}

String _bounded_resource(const char *p_text) {
	if (p_text == nullptr || strnlen(p_text, MAX_RESOURCE_BYTES + 1) > MAX_RESOURCE_BYTES) {
		return String();
	}
	const String value = _bounded_text(p_text, MAX_RESOURCE_BYTES, "");
	return toqraq_is_observation_label(value, MAX_RESOURCE_BYTES) ? value : String();
}

int64_t _unix_milliseconds() {
	const double milliseconds = OS::get_singleton()->get_unix_time() * 1000.0;
	return CLAMP((int64_t)milliseconds, (int64_t)0, ToqraqLimits::MAX_SAFE_INTEGER);
}

} // namespace

ToqraqDiagnosticLog *ToqraqDiagnosticLog::singleton = nullptr;

ToqraqDiagnosticLog::ToqraqDiagnosticLog() {
	singleton = this;
}

bool ToqraqDiagnosticLog::activate() {
	OS *os = OS::get_singleton();
	if (os == nullptr) {
		return false;
	}
	if (singleton == nullptr) {
		os->add_logger(memnew(ToqraqDiagnosticLog));
	}
	if (singleton == nullptr) {
		return false;
	}
	singleton->_begin_run();
	return true;
}

void ToqraqDiagnosticLog::deactivate() {
	if (singleton != nullptr) {
		singleton->_end_run();
	}
}

uint64_t ToqraqDiagnosticLog::generation() {
	if (singleton == nullptr) {
		return 0;
	}
	MutexLock lock(singleton->mutex);
	return singleton->current_generation;
}

Vector<ToqraqDiagnosticRecord> ToqraqDiagnosticLog::snapshot(uint64_t &r_generation) {
	Vector<ToqraqDiagnosticRecord> values;
	if (singleton == nullptr) {
		r_generation = 0;
		return values;
	}
	MutexLock lock(singleton->mutex);
	r_generation = singleton->current_generation;
	values.reserve(singleton->records.size());
	for (const ToqraqDiagnosticRecord &record : singleton->records) {
		values.push_back(record);
	}
	return values;
}

void ToqraqDiagnosticLog::_begin_run() {
	{
		MutexLock lock(mutex);
		records.clear();
		next_sequence = 1;
		current_generation++;
		active = true;
	}
	_append("toqraq.bridge", "info", "toqraq.bridge.ready", "Toqraq native bridge is ready.");
}

void ToqraqDiagnosticLog::_end_run() {
	MutexLock lock(mutex);
	active = false;
	records.clear();
	current_generation++;
}

void ToqraqDiagnosticLog::_append(
		const String &p_source_id,
		const String &p_severity,
		const String &p_code,
		const String &p_summary,
		const String &p_resource,
		int p_line) {
	MutexLock lock(mutex);
	if (!active || next_sequence > ToqraqLimits::MAX_SAFE_INTEGER) {
		return;
	}
	ToqraqDiagnosticRecord record;
	record.sequence = next_sequence++;
	record.occurred_at_unix_ms = _unix_milliseconds();
	record.source_id = p_source_id;
	record.severity = p_severity;
	record.code = p_code;
	record.summary = p_summary;
	record.resource = p_resource;
	record.line = p_line;
	records.push_back(record);
	while (records.size() > MAX_RECORDS) {
		records.pop_front();
	}
	current_generation++;
}

void ToqraqDiagnosticLog::logv(const char *p_format, va_list p_list, bool p_err) {
	if (!should_log(p_err)) {
		return;
	}
	_append("godot.output", p_err ? "error" : "info",
			p_err ? "godot.output.error" : "godot.output.message",
			_formatted_summary(p_format, p_list));
}

void ToqraqDiagnosticLog::log_error(
		const char *p_function,
		const char *p_file,
		int p_line,
		const char *p_code,
		const char *p_rationale,
		bool p_editor_notify,
		ErrorType p_type,
		const Vector<Ref<ScriptBacktrace>> &p_script_backtraces) {
	(void)p_function;
	(void)p_editor_notify;
	(void)p_script_backtraces;
	const String source = p_type == ERR_SCRIPT ? "godot.script" :
			p_type == ERR_SHADER ? "godot.shader" : "godot.runtime";
	const String severity = p_type == ERR_WARNING ? "warning" : "error";
	const String code = p_type == ERR_WARNING ? "godot.warning" :
			p_type == ERR_SCRIPT ? "godot.script.error" :
			p_type == ERR_SHADER ? "godot.shader.error" : "godot.error";
	const char *summary = p_rationale != nullptr && p_rationale[0] != '\0' ? p_rationale : p_code;
	_append(source, severity, code,
			_bounded_text(summary, MAX_SUMMARY_BYTES, "Godot emitted an empty diagnostic."),
			_bounded_resource(p_file), MAX(p_line, 0));
}

ToqraqDiagnosticLog::~ToqraqDiagnosticLog() {
	if (singleton == this) {
		singleton = nullptr;
	}
}
