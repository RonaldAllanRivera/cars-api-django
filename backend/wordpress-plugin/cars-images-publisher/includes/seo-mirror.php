<?php
/**
 * Copies the SEO fields onto Yoast SEO and Rank Math.
 *
 * The API writes only the _ucs_seo_* keys, because Yoast's and Rank Math's are
 * not writable over REST. Hooked on the meta actions, so writes from the REST
 * API, wp-admin and WP-CLI are all copied alike. No target key is a source key,
 * so copying can never trigger itself.
 */

defined('ABSPATH') || exit;

const CIP_SEO_MIRROR_MAP = [
    '_ucs_seo_title'       => ['_yoast_wpseo_title', 'rank_math_title'],
    '_ucs_seo_description' => ['_yoast_wpseo_metadesc', 'rank_math_description'],
    '_ucs_seo_keywords'    => ['_yoast_wpseo_focuskw', 'rank_math_focus_keyword'],
];

function cip_register_mirror_hooks() {
    // used-cars-search 1.6.13+ copies the same fields; one copy is enough.
    if (function_exists('ucs_seo_mirror')) {
        return;
    }
    add_action('added_post_meta', 'cip_mirror_seo_field', 10, 4);
    add_action('updated_post_meta', 'cip_mirror_seo_field', 10, 4);
    add_action('deleted_post_meta', 'cip_delete_mirrored_seo_field', 10, 4);
}
// After every plugin's own plugins_loaded work, so the check above sees used-cars-search.
add_action('plugins_loaded', 'cip_register_mirror_hooks', 20);

function cip_mirrors($post_id, $meta_key) {
    return isset(CIP_SEO_MIRROR_MAP[$meta_key]) && in_array(get_post_type($post_id), cip_post_types(), true);
}

function cip_mirror_seo_field($meta_id, $post_id, $meta_key, $meta_value) {
    if (!cip_mirrors($post_id, $meta_key)) {
        return;
    }
    $value = is_scalar($meta_value) ? wp_strip_all_tags((string) $meta_value) : '';
    if ($meta_key === '_ucs_seo_keywords') {
        // Both SEO plugins take one focus keyword: the first.
        $keywords = array_values(array_filter(array_map('trim', explode(',', $value)), 'strlen'));
        $value = $keywords ? $keywords[0] : '';
    }
    foreach (CIP_SEO_MIRROR_MAP[$meta_key] as $target) {
        if ($value === '') {
            // No override, so the SEO plugin's own template applies.
            delete_post_meta($post_id, $target);
        } else {
            update_post_meta($post_id, $target, $value);
        }
    }
}

function cip_delete_mirrored_seo_field($meta_ids, $post_id, $meta_key, $meta_value) {
    if (!cip_mirrors($post_id, $meta_key)) {
        return;
    }
    foreach (CIP_SEO_MIRROR_MAP[$meta_key] as $target) {
        delete_post_meta($post_id, $target);
    }
}
