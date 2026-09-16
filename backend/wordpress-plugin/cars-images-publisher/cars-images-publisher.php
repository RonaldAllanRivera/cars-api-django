<?php
/**
 * Plugin Name:       Cars Images Publisher
 * Plugin URI:        https://github.com/RonaldAllanRivera/cars-api-django
 * Description:       Receives SEO-ready draft posts from the Cars Images API: exposes the fields it writes to the REST API, copies SEO fields to Yoast SEO or Rank Math, and prints the meta title and description itself when neither is active.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Ronald Allan Rivera
 * Author URI:        https://github.com/RonaldAllanRivera
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       cars-images-publisher
 */

defined('ABSPATH') || exit;

define('CIP_VERSION', '1.0.0');

require_once __DIR__ . '/includes/meta.php';
require_once __DIR__ . '/includes/seo-mirror.php';
require_once __DIR__ . '/includes/head.php';
