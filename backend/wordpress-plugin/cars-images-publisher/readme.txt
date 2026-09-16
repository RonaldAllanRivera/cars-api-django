=== Cars Images Publisher ===
Contributors: ronaldallanrivera
Tags: seo, rest api, yoast, rank math, automotive
Requires at least: 6.0
Tested up to: 6.8
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Receives SEO-ready draft posts from the Cars Images API.

== Description ==

The Cars Images API writes one illustrated draft post per vehicle to this site over the WordPress REST API. This plugin is the WordPress side of that:

* **REST fields.** Registers the SEO title, description and keywords, and the vehicle's year, make and model, so the REST API accepts them.
* **Yoast SEO and Rank Math.** Copies the SEO title, description and first keyword to whichever is active, whether they were written over REST, in wp-admin or by WP-CLI.
* **No SEO plugin?** Prints the meta title and description itself. It stays silent when Yoast SEO, Rank Math or Used Cars Search already does.

It has no settings and stores nothing of its own. It works alongside the Used Cars Search plugin, which uses the same field names.

== Installation ==

1. In the Cars Images web app, open **Pipeline → WordPress plugin → Download zip**.
2. In WordPress, go to **Plugins → Add New → Upload Plugin**, choose the zip and activate it.
3. Create a user who can post unfiltered HTML (an Administrator or Editor on a single site), then under **Users → Profile → Application Passwords** create one for the API.
4. Give the API the site URL, that username and the Application Password.

== Frequently Asked Questions ==

= The API gets 401 with the right password =

Apache is probably dropping the Authorization header. Add `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1` to the site's .htaccess.

= What happens to posts if I deactivate it? =

Nothing. Posts and their fields stay; only the REST registration, the SEO copying and the head tags stop.

== Changelog ==

= 1.0.0 =
* First release: REST fields, Yoast SEO and Rank Math copying, and a meta title and description fallback.
