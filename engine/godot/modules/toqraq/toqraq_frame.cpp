// SPDX-License-Identifier: MIT

#include "toqraq_frame.h"

#include "toqraq_json.h"
#include "toqraq_limits.h"
#include "toqraq_observation_state.h"
#include "toqraq_rpc.h"

#include "core/crypto/crypto.h"
#include "core/crypto/hashing_context.h"
#include "core/io/image.h"
#include "core/os/memory.h"
#include "scene/main/scene_tree.h"
#include "scene/main/viewport.h"
#include "scene/main/window.h"

#include <cstring>

namespace {

constexpr int MAX_DIMENSION = 16384;
constexpr int64_t MAX_PIXELS = 67108864;
constexpr const char *PARAM_KEYS[] = { "maximum_size", "scaling", "maximum_bytes" };
constexpr const char *SIZE_KEYS[] = { "width", "height" };

struct CaptureQuery {
	int maximum_width = 0;
	int maximum_height = 0;
	bool contain = false;
	int maximum_bytes = 0;
};

bool _read_query(const Dictionary &p_params, CaptureQuery &r_query) {
	if (!toqraq_has_exact_keys(p_params, PARAM_KEYS, 3)) {
		return false;
	}
	const Variant *maximum_size = p_params.getptr("maximum_size");
	const Variant *scaling = p_params.getptr("scaling");
	const Variant *maximum_bytes = p_params.getptr("maximum_bytes");
	if (maximum_size == nullptr || scaling == nullptr || maximum_bytes == nullptr ||
			maximum_size->get_type() != Variant::DICTIONARY || scaling->get_type() != Variant::STRING) {
		return false;
	}
	const Dictionary size = *maximum_size;
	if (!toqraq_has_exact_keys(size, SIZE_KEYS, 2)) {
		return false;
	}
	const Variant *width = size.getptr("width");
	const Variant *height = size.getptr("height");
	int64_t width_value = 0;
	int64_t height_value = 0;
	int64_t byte_value = 0;
	if (width == nullptr || height == nullptr || !toqraq_read_json_integer(*width, width_value) ||
			!toqraq_read_json_integer(*height, height_value) || width_value < 1 || height_value < 1 ||
			width_value > MAX_DIMENSION || height_value > MAX_DIMENSION ||
			width_value * height_value > MAX_PIXELS || !toqraq_read_json_integer(*maximum_bytes, byte_value) ||
			byte_value < 1 || byte_value > ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES) {
		return false;
	}
	const String scaling_value = *scaling;
	if (scaling_value != "native" && scaling_value != "contain") {
		return false;
	}
	r_query.maximum_width = width_value;
	r_query.maximum_height = height_value;
	r_query.maximum_bytes = byte_value;
	r_query.contain = scaling_value == "contain";
	return true;
}

bool _target_size(const CaptureQuery &p_query, int p_width, int p_height, int &r_width, int &r_height) {
	if (p_width < 1 || p_height < 1 || p_width > 32768 || p_height > 32768) {
		return false;
	}
	const bool fits = p_width <= p_query.maximum_width && p_height <= p_query.maximum_height;
	if (!p_query.contain) {
		if (!fits) {
			return false;
		}
		r_width = p_width;
		r_height = p_height;
		return true;
	}
	if (fits) {
		r_width = p_width;
		r_height = p_height;
		return true;
	}
	const bool width_limited = (int64_t)p_query.maximum_width * p_height <=
			(int64_t)p_query.maximum_height * p_width;
	if (width_limited) {
		r_width = p_query.maximum_width;
		r_height = MAX(1, (int)((int64_t)p_height * p_query.maximum_width / p_width));
	} else {
		r_width = MAX(1, (int)((int64_t)p_width * p_query.maximum_height / p_height));
		r_height = p_query.maximum_height;
	}
	return true;
}

bool _random_transfer_id(Vector<uint8_t> &r_bytes, String &r_hex) {
	Crypto *crypto = Crypto::create();
	if (crypto == nullptr) {
		return false;
	}
	r_bytes = crypto->generate_random_bytes(ToqraqLimits::TRANSFER_PREFIX_BYTES);
	memdelete(crypto);
	if (r_bytes.size() != ToqraqLimits::TRANSFER_PREFIX_BYTES) {
		r_bytes.clear();
		return false;
	}
	r_hex = String::hex_encode_buffer(r_bytes.ptr(), r_bytes.size());
	return r_hex.length() == 32;
}

String _sha256(const Vector<uint8_t> &p_bytes) {
	Ref<HashingContext> context;
	context.instantiate();
	if (context->start(HashingContext::HASH_SHA256) != OK || context->update(p_bytes) != OK) {
		return String();
	}
	const PackedByteArray digest = context->finish();
	return digest.size() == 32 ? String::hex_encode_buffer(digest.ptr(), digest.size()) : String();
}

} // namespace

ToqraqFrameCapture::ToqraqFrameCapture(ToqraqObservationState &p_state) :
		state(p_state) {}

ToqraqFeatureResult ToqraqFrameCapture::capture(const Dictionary &p_params) {
	CaptureQuery query;
	if (!_read_query(p_params, query)) {
		return toqraq_feature_error("bridge.params_invalid", "invalid");
	}
	SceneTree *tree = SceneTree::get_singleton();
	Window *root = tree != nullptr ? tree->get_root() : nullptr;
	if (root == nullptr) {
		return toqraq_feature_error("perception.frame_unavailable", "unavailable");
	}
	const Ref<ViewportTexture> texture = root->get_texture();
	const Ref<Image> image = texture.is_valid() ? texture->get_image() : Ref<Image>();
	if (image.is_null() || image->is_empty()) {
		return toqraq_feature_error("perception.frame_unavailable", "unavailable");
	}
	const int viewport_width = image->get_width();
	const int viewport_height = image->get_height();
	int encoded_width = 0;
	int encoded_height = 0;
	if (!_target_size(query, viewport_width, viewport_height, encoded_width, encoded_height)) {
		return toqraq_feature_error("perception.frame_unavailable", "unavailable");
	}
	if (encoded_width != viewport_width || encoded_height != viewport_height) {
		image->resize(encoded_width, encoded_height, Image::INTERPOLATE_LANCZOS);
	}
	Vector<uint8_t> png = image->save_png_to_buffer();
	if (png.is_empty() || png.size() > query.maximum_bytes ||
			png.size() > ToqraqLimits::MAX_BINARY_PAYLOAD_BYTES) {
		png.clear();
		return toqraq_feature_error("perception.frame_unavailable", "unavailable");
	}
	Vector<uint8_t> transfer_id;
	String transfer_hex;
	const String digest = _sha256(png);
	if (digest.is_empty() || !_random_transfer_id(transfer_id, transfer_hex)) {
		png.clear();
		return toqraq_feature_error("bridge.remote_internal", "internal");
	}
	state.mark_frame();
	Dictionary viewport_size;
	viewport_size["width"] = viewport_width;
	viewport_size["height"] = viewport_height;
	Dictionary encoded_size;
	encoded_size["width"] = encoded_width;
	encoded_size["height"] = encoded_height;
	Dictionary transfer;
	transfer["transfer_id"] = transfer_hex;
	transfer["mime_type"] = "image/png";
	transfer["size"] = encoded_size;
	transfer["byte_length"] = png.size();
	transfer["sha256"] = digest;
	transfer["frame_revision"] = state.frame();
	Dictionary result;
	result["viewport_size"] = viewport_size;
	result["captured_at_unix_ms"] = toqraq_observed_at_unix_ms();
	result["transfer"] = transfer;
	ToqraqFeatureResult response = toqraq_feature_success(result);
	response.binary.resize(transfer_id.size() + png.size());
	memcpy(response.binary.ptrw(), transfer_id.ptr(), transfer_id.size());
	memcpy(response.binary.ptrw() + transfer_id.size(), png.ptr(), png.size());
	response.changed_families.push_back("frame");
	transfer_id.fill(0);
	png.clear();
	return response;
}
