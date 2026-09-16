<?php
/**
 * Tests for Cars Images Publisher. No WordPress install needed: the core
 * functions the plugin calls are stubbed below. Run: php tests/run-tests.php
 *
 * Not shipped: the download zip excludes this directory.
 */

define('ABSPATH', __DIR__);

// --- WordPress stubs ----------------------------------------------------------
$GLOBALS['hooks'] = [];
$GLOBALS['meta'] = [];
$GLOBALS['registered_meta'] = [];
$GLOBALS['post_types'] = [1 => 'post', 2 => 'page'];
$GLOBALS['singular'] = null;
$GLOBALS['capabilities'] = [];

function add_action($hook, $callback, $priority = 10, $accepted_args = 1) {
    $GLOBALS['hooks'][$hook][$priority][] = $callback;
}
function add_filter($hook, $callback, $priority = 10, $accepted_args = 1) {
    add_action($hook, $callback, $priority, $accepted_args);
}
function do_action($hook, ...$args) {
    $by_priority = $GLOBALS['hooks'][$hook] ?? [];
    ksort($by_priority);
    foreach ($by_priority as $callbacks) {
        foreach ($callbacks as $callback) {
            $callback(...$args);
        }
    }
}
function apply_filters($hook, $value, ...$args) {
    $by_priority = $GLOBALS['hooks'][$hook] ?? [];
    ksort($by_priority);
    foreach ($by_priority as $callbacks) {
        foreach ($callbacks as $callback) {
            $value = $callback($value, ...$args);
        }
    }
    return $value;
}
function has_hook($hook) {
    return !empty($GLOBALS['hooks'][$hook]);
}
function registered_meta_key_exists($object_type, $key, $subtype) {
    return isset($GLOBALS['registered_meta'][$subtype][$key]);
}
function register_post_meta($post_type, $key, $args) {
    $GLOBALS['registered_meta'][$post_type][$key] = $args;
    return true;
}
function user_can($user_id, $capability, $post_id) {
    return in_array("{$user_id}:{$capability}:{$post_id}", $GLOBALS['capabilities'], true);
}
function get_post_type($post_id) {
    return $GLOBALS['post_types'][$post_id] ?? false;
}
function get_post_meta($post_id, $key, $single) {
    return $GLOBALS['meta'][$post_id][$key] ?? '';
}
function update_post_meta($post_id, $key, $value) {
    $existed = isset($GLOBALS['meta'][$post_id][$key]);
    $GLOBALS['meta'][$post_id][$key] = $value;
    do_action($existed ? 'updated_post_meta' : 'added_post_meta', 1, $post_id, $key, $value);
    return true;
}
function delete_post_meta($post_id, $key) {
    $old = $GLOBALS['meta'][$post_id][$key] ?? '';
    unset($GLOBALS['meta'][$post_id][$key]);
    do_action('deleted_post_meta', [1], $post_id, $key, $old);
    return true;
}
function is_singular($post_types) {
    return $GLOBALS['singular'] !== null && in_array(get_post_type($GLOBALS['singular']), (array) $post_types, true);
}
function get_queried_object_id() {
    return (int) $GLOBALS['singular'];
}
function wp_strip_all_tags($text) {
    return trim(strip_tags((string) $text));
}
function esc_attr($text) {
    return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8');
}
function esc_html($text) {
    return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8');
}
function sanitize_text_field($text) {
    return trim(preg_replace('/\s+/', ' ', strip_tags((string) $text)));
}
function absint($value) {
    return abs((int) $value);
}

// --- harness --------------------------------------------------------------------
$failures = 0;
function check($name, $actual, $expected) {
    global $failures;
    if ($actual === $expected) {
        echo "  ok    {$name}\n";
        return;
    }
    $failures++;
    echo "  FAIL  {$name}\n        expected " . var_export($expected, true) . "\n        got      " . var_export($actual, true) . "\n";
}
function reset_site() {
    $GLOBALS['meta'] = [];
    $GLOBALS['registered_meta'] = [];
    $GLOBALS['singular'] = null;
    $GLOBALS['capabilities'] = [];
}
function meta($post_id, $key) {
    return $GLOBALS['meta'][$post_id][$key] ?? null;
}
function capture(callable $fn) {
    ob_start();
    $fn();
    return ob_get_clean();
}

require __DIR__ . '/../cars-images-publisher.php';
do_action('plugins_loaded');

echo "plugin\n";
check('the version constant matches the plugin header', CIP_VERSION, get_header_version());

echo "\nREST fields\n";
reset_site();
do_action('init');
$registered = $GLOBALS['registered_meta']['post'] ?? [];
check(
    'the six fields the publisher writes are registered for posts',
    array_keys($registered),
    ['_ucs_seo_title', '_ucs_seo_description', '_ucs_seo_keywords', 'ucs_year', 'ucs_make', 'ucs_model']
);
check('they are exposed to the REST API', $registered['_ucs_seo_title']['show_in_rest'] ?? null, true);
check('the year is an integer', $registered['ucs_year']['type'] ?? null, 'integer');

reset_site();
$GLOBALS['registered_meta']['post']['_ucs_seo_title'] = ['owner' => 'used-cars-search'];
do_action('init');
check(
    'a field another plugin already registered is left to it, so both can run together',
    $GLOBALS['registered_meta']['post']['_ucs_seo_title'],
    ['owner' => 'used-cars-search']
);

reset_site();
do_action('init');
$auth = $GLOBALS['registered_meta']['post']['_ucs_seo_title']['auth_callback'];
$GLOBALS['capabilities'] = ['5:edit_post:1'];
check('a user who can edit the post may write its fields', $auth(false, '_ucs_seo_title', 1, 5), true);
check('a user who cannot edit the post may not', $auth(true, '_ucs_seo_title', 1, 6), false);
check('nothing is writable without a post', $auth(true, '_ucs_seo_title', 0, 5), false);

echo "\nSEO mirror\n";
reset_site();
update_post_meta(1, '_ucs_seo_title', '1997 Toyota RAV4 Review');
check('the SEO title reaches Yoast', meta(1, '_yoast_wpseo_title'), '1997 Toyota RAV4 Review');
check('the SEO title reaches Rank Math', meta(1, 'rank_math_title'), '1997 Toyota RAV4 Review');

reset_site();
update_post_meta(1, '_ucs_seo_description', 'A reliable compact SUV.');
check('the description reaches Yoast', meta(1, '_yoast_wpseo_metadesc'), 'A reliable compact SUV.');
check('the description reaches Rank Math', meta(1, 'rank_math_description'), 'A reliable compact SUV.');

reset_site();
update_post_meta(1, '_ucs_seo_keywords', 'used toyota rav4, 1997 rav4');
check('Yoast gets the first keyword as its focus keyphrase', meta(1, '_yoast_wpseo_focuskw'), 'used toyota rav4');
check('Rank Math gets the same focus keyword', meta(1, 'rank_math_focus_keyword'), 'used toyota rav4');

reset_site();
update_post_meta(1, '_ucs_seo_title', 'Something');
update_post_meta(1, '_ucs_seo_title', '');
check('an emptied value removes the override so the SEO plugin template applies', meta(1, '_yoast_wpseo_title'), null);

reset_site();
update_post_meta(1, '_ucs_seo_description', 'Something');
delete_post_meta(1, '_ucs_seo_description');
check('a deleted value is deleted from both SEO plugins', meta(1, 'rank_math_description'), null);

reset_site();
update_post_meta(2, '_ucs_seo_title', 'A page');
check('post types the plugin does not manage are left alone', meta(2, '_yoast_wpseo_title'), null);

reset_site();
update_post_meta(1, '_ucs_seo_title', '<b>Bold</b> title');
check('markup is stripped before it reaches an SEO plugin', meta(1, '_yoast_wpseo_title'), 'Bold title');

echo "\nHead tags without an SEO plugin\n";
reset_site();
$GLOBALS['singular'] = 1;
$GLOBALS['meta'][1]['_ucs_seo_description'] = 'Fast, "reliable" & <cheap>';
check(
    'the meta description is printed, escaped',
    capture(function () { do_action('wp_head'); }),
    '<meta name="description" content="Fast, &quot;reliable&quot; &amp; &lt;cheap&gt;" />' . "\n"
);

reset_site();
$GLOBALS['singular'] = 1;
$GLOBALS['meta'][1]['_ucs_seo_title'] = 'Title <script>';
check('the document title uses the SEO title, escaped', apply_filters('pre_get_document_title', ''), 'Title &lt;script&gt;');

reset_site();
$GLOBALS['singular'] = 1;
check('without an SEO title the theme title is kept', apply_filters('pre_get_document_title', ''), '');
check('without a description nothing is printed', capture(function () { do_action('wp_head'); }), '');

reset_site();
$GLOBALS['singular'] = 2;
$GLOBALS['meta'][2]['_ucs_seo_description'] = 'A page';
check('pages the plugin does not manage get no tags', capture(function () { do_action('wp_head'); }), '');

echo "\nAlongside other plugins (last: constants and functions cannot be undefined)\n";
reset_site();
$GLOBALS['singular'] = 1;
$GLOBALS['meta'][1]['_ucs_seo_description'] = 'Described';
$GLOBALS['meta'][1]['_ucs_seo_title'] = 'Titled';
define('WPSEO_VERSION', '99.0');
check('with Yoast active no head tags are printed, so there are no duplicates', capture(function () { do_action('wp_head'); }), '');
check('with Yoast active the title is left to Yoast', apply_filters('pre_get_document_title', ''), '');

$GLOBALS['hooks'] = [];
// Inside a block: PHP hoists a top-level function declaration to the start of the file.
if (true) {
    function ucs_seo_mirror() {}
}
cip_register_mirror_hooks();
check('when used-cars-search already mirrors, no second set of hooks is added', has_hook('updated_post_meta'), false);

echo $failures ? "\n{$failures} failure(s)\n" : "\nall passed\n";
exit($failures ? 1 : 0);

function get_header_version() {
    preg_match('/^\s*\*\s*Version:\s*(\S+)/m', file_get_contents(__DIR__ . '/../cars-images-publisher.php'), $match);
    return $match[1] ?? null;
}
