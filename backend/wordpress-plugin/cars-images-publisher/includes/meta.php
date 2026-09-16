<?php
/**
 * Registers the post fields the Cars Images API writes, so the REST API accepts them.
 *
 * The keys match the used-cars-search plugin's, so the publisher works with
 * either plugin. A key another plugin has already registered is left to it,
 * which lets the two run side by side.
 */

defined('ABSPATH') || exit;

const CIP_META_FIELDS = [
    '_ucs_seo_title'       => 'string',
    '_ucs_seo_description' => 'string',
    '_ucs_seo_keywords'    => 'string',
    'ucs_year'             => 'integer',
    'ucs_make'             => 'string',
    'ucs_model'            => 'string',
];

/** The post types the plugin manages; filterable with `cip_post_types`. */
function cip_post_types() {
    return (array) apply_filters('cip_post_types', ['post']);
}

function cip_register_meta() {
    foreach (cip_post_types() as $post_type) {
        foreach (CIP_META_FIELDS as $key => $type) {
            if (registered_meta_key_exists('post', $key, $post_type)) {
                continue;
            }
            register_post_meta($post_type, $key, [
                'type'              => $type,
                'single'            => true,
                'show_in_rest'      => true,
                'sanitize_callback' => $type === 'integer' ? 'absint' : 'sanitize_text_field',
                // Underscored keys are protected: without this, REST refuses the whole post update.
                'auth_callback'     => 'cip_can_edit_post_fields',
            ]);
        }
    }
}
// After used-cars-search (priority 10), so its registrations win when both are active.
add_action('init', 'cip_register_meta', 20);

function cip_can_edit_post_fields($allowed, $meta_key, $post_id, $user_id = 0) {
    return $post_id ? user_can($user_id, 'edit_post', $post_id) : false;
}
