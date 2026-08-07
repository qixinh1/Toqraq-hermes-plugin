// SPDX-License-Identifier: MIT

#pragma once

#include "core/io/logger.h"
#include "core/os/mutex.h"
#include "core/string/ustring.h"
#include "core/templates/list.h"
#include "core/templates/vector.h"

struct ToqraqDiagnosticRecord {
	int64_t sequence = 0;
	int64_t occurred_at_unix_ms = 0;
	String source_id;
	String severity;
	String code;
	String summary;
	String resource;
	int line = 0;
};

class ToqraqDiagnosticLog final : public Logger {
	static ToqraqDiagnosticLog *singleton;

	mutable BinaryMutex mutex;
	List<ToqraqDiagnosticRecord> records;
	int64_t next_sequence = 1;
	uint64_t current_generation = 0;
	bool active = false;

	ToqraqDiagnosticLog();
	void _begin_run();
	void _end_run();
	void _append(
			const String &p_source_id,
			const String &p_severity,
			const String &p_code,
			const String &p_summary,
			const String &p_resource = String(),
			int p_line = 0);

public:
	static bool activate();
	static void deactivate();
	static uint64_t generation();
	static Vector<ToqraqDiagnosticRecord> snapshot(uint64_t &r_generation);

	void logv(const char *p_format, va_list p_list, bool p_err) override _PRINTF_FORMAT_ATTRIBUTE_2_0;
	void log_error(
			const char *p_function,
			const char *p_file,
			int p_line,
			const char *p_code,
			const char *p_rationale,
			bool p_editor_notify,
			ErrorType p_type,
			const Vector<Ref<ScriptBacktrace>> &p_script_backtraces) override;
	~ToqraqDiagnosticLog() override;
};
