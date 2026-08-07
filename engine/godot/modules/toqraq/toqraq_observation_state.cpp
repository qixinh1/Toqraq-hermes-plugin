// SPDX-License-Identifier: MIT

#include "toqraq_observation_state.h"

#include "core/object/callable_mp.h"
#include "scene/main/node.h"
#include "scene/main/scene_tree.h"

ToqraqObservationState::~ToqraqObservationState() {
	_disconnect_tree();
}

void ToqraqObservationState::_tree_changed() {
	tree_dirty = true;
}

void ToqraqObservationState::_disconnect_tree() {
	SceneTree *tree = Object::cast_to<SceneTree>(ObjectDB::get_instance(observed_tree));
	const Callable callback = callable_mp(this, &ToqraqObservationState::_tree_changed);
	if (tree != nullptr && tree->is_connected(SNAME("tree_changed"), callback)) {
		tree->disconnect(SNAME("tree_changed"), callback);
	}
	observed_tree = ObjectID();
}

String ToqraqObservationState::_revision(const char *p_family, int64_t p_value) const {
	return String(p_family) + "-" + itos(p_value);
}

String ToqraqObservationState::reference_for(Object *p_object) {
	if (p_object == nullptr) {
		return String();
	}
	const ObjectID id = p_object->get_instance_id();
	const String *existing = references_by_id.getptr(id);
	if (existing != nullptr) {
		return *existing;
	}
	const String reference = "object-" + itos(next_reference++);
	references_by_id.insert(id, reference);
	ids_by_reference.insert(reference, id);
	return reference;
}

Object *ToqraqObservationState::resolve(const String &p_reference) {
	const ObjectID *id = ids_by_reference.getptr(p_reference);
	if (id == nullptr) {
		return nullptr;
	}
	Object *object = ObjectDB::get_instance(*id);
	if (object == nullptr) {
		references_by_id.erase(*id);
		ids_by_reference.erase(p_reference);
	}
	return object;
}

bool ToqraqObservationState::observe_tree() {
	SceneTree *tree = SceneTree::get_singleton();
	if (tree == nullptr) {
		return false;
	}
	const ObjectID tree_id = tree->get_instance_id();
	if (tree_id != observed_tree) {
		_disconnect_tree();
		tree->connect(SNAME("tree_changed"), callable_mp(this, &ToqraqObservationState::_tree_changed));
		observed_tree = tree_id;
		tree_dirty = true;
	}
	Node *scene = tree->get_current_scene();
	const ObjectID scene_id = scene != nullptr ? scene->get_instance_id() : ObjectID();
	const int node_count = tree->get_node_count();
	if (!tree_dirty && scene_id == last_scene_root && node_count == last_node_count) {
		return false;
	}
	tree_dirty = false;
	last_scene_root = scene_id;
	last_node_count = node_count;
	mark_hierarchy();
	mark_objects();
	return true;
}

String ToqraqObservationState::hierarchy() const {
	return _revision("hierarchy", hierarchy_revision);
}

String ToqraqObservationState::objects() const {
	return _revision("objects", object_revision);
}

String ToqraqObservationState::diagnostics() const {
	return _revision("diagnostics", diagnostic_revision);
}

String ToqraqObservationState::metrics() const {
	return _revision("metrics", metric_revision);
}

String ToqraqObservationState::frame() const {
	return _revision("frame", frame_revision);
}

String ToqraqObservationState::simulation() const {
	return _revision("simulation", simulation_revision);
}

void ToqraqObservationState::mark_hierarchy() {
	hierarchy_revision++;
}

void ToqraqObservationState::mark_objects() {
	object_revision++;
}

void ToqraqObservationState::mark_diagnostics() {
	diagnostic_revision++;
}

void ToqraqObservationState::mark_metrics() {
	metric_revision++;
}

void ToqraqObservationState::mark_frame() {
	frame_revision++;
}

void ToqraqObservationState::mark_simulation() {
	simulation_revision++;
}

void ToqraqObservationState::clear() {
	_disconnect_tree();
	references_by_id.clear();
	ids_by_reference.clear();
	next_reference = 1;
	last_scene_root = ObjectID();
	last_node_count = -1;
	tree_dirty = true;
}
