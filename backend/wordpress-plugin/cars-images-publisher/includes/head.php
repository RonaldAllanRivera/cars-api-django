<?php
/**
 * Prints the SEO title and meta description when no SEO plugin will.
 *
 * Yoast SEO, Rank Math and used-cars-search each print their own, so this
 * stays silent when any of them is active rather than printing duplicates.
 */

defined('ABSPATH') || exit;

function cip_another_plugin_prints_seo_tags() {
    return defined('WPSEO_VERSION') || defined('RANK_MATH_VERSION') || function_exists('ucs_seo_get_post_types');
}

function cip_current_post_field($key) {
    if (!is_singular(cip_post_types())) {
        return '';
    }
    $post_id = get_queried_object_id();
    return $post_id ? trim((string) get_post_meta($post_id, $key, true)) : '';
}

function cip_document_title($title) {
    if (cip_another_plugin_prints_seo_tags()) {
        return $title;
    }
    $seo_title = cip_current_post_field('_ucs_seo_title');
    // Core prints a pre_get_document_title result unescaped.
    return $seo_title === '' ? $title : esc_html($seo_title);
}
add_filter('pre_get_document_title', 'cip_document_title', 20);

function cip_print_meta_description() {
    if (cip_another_plugin_prints_seo_tags()) {
        return;
    }
    $description = cip_current_post_field('_ucs_seo_description');
    if ($description !== '') {
        printf('<meta name="description" content="%s" />' . "\n", esc_attr($description));
    }
}
add_action('wp_head', 'cip_print_meta_description', 1);
