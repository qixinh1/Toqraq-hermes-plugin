// SPDX-License-Identifier: MIT

#pragma once

#include "core/object/object.h"
#include "core/templates/hash_map.h"

class ToqraqObservationState : public Object {
	HashMap<ObjectID, String> references_by_id;
	HashMap<String, ObjectID> ids_by_reference;
	int64_t next_reference = 1;
	int64_t hierarchy_revision = 1;
	int64_t object_revision = 1;
	int64_t diagnostic_revision = 1;
	int64_t metric_revision = 1;
	int64_t frame_revision = 1;
	int64_t simulation_revision = 1;
	ObjectID last_scene_root;
	ObjectID observed_tree;
	int last_node_count = -1;
	bool tree_dirty = true;

	String _revision(const char *p_family, int64_t p_value) const;
	void _tree_changed();
	void _disconnect_tree();

public:
	~ToqraqObservationState();
	String reference_for(Object *p_object);
	Object *resolve(const String &p_reference);
	bool observe_tree();

	String hierarchy() const;
	String objects() const;
	String diagnostics() const;
	String metrics() const;
	String frame() const;
	String simulation() const;

	void mark_hierarchy();
	void mark_objects();
	void mark_diagnostics();
	void mark_metrics();
	void mark_frame();
	void mark_simulation();
	void clear();
};
