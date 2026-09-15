import Head from 'expo-router/head';

/**
 * The browser tab title, and the title a link preview shows, for the web
 * build. Renders nothing on native.
 *
 * A route's react-navigation `title` option cannot do this job: expo-router
 * mounts its NavigationContainer with `documentTitle: { enabled: false }`
 * (ExpoRoot.js), and the static renderer builds each page's <head> from
 * expo-router/head's helmet context alone - the navigation options never
 * reach it. Without a Head, every exported page ships `<title></title>`,
 * which for a deliverable whose whole point is "a link anyone can open"
 * means a blank tab and an empty preview.
 */
export function PageTitle({ title }: { title: string }) {
  return (
    <Head>
      <title>{title}</title>
      <meta property="og:title" content={title} />
    </Head>
  );
}
