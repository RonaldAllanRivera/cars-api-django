# Building an installable Android APK with EAS Build

Not done yet — deliberately. Write this down now, do it when the app stops
changing, because every feature you add means another build.

## Why bother

The Expo client already runs three ways: `npx expo start` + Expo Go, the web
build on Netlify, and the dev server. An APK adds one thing those cannot do —
**someone else installs the real app on their own phone from a link**, with no
Expo Go, no QR code, and no laptop of yours involved.

It also proves the native path compiles, which Expo Go does not: Expo Go runs
your JavaScript inside *its* binary, so a native module misconfiguration can
stay hidden until the first real build.

**Android only.** An iOS build needs a paid Apple Developer account
($99/year) and TestFlight for distribution. Nothing below applies to iOS.

## Before you start

- An Expo account (free) — <https://expo.dev/signup>
- `mobile/app.json` already has what a build needs: `android.package` is
  `com.carsimages.app`, and `newArchEnabled` is on. Changing the package name
  after people have installed the app means a separate app on their phone, so
  leave it alone.
- Decide the API the build will talk to. `EXPO_PUBLIC_API_URL` is **baked in at
  build time**; an APK cannot be re-pointed afterwards.

## One-time setup

```bash
npm install --global eas-cli
cd mobile
eas login
eas init          # links the project, writes the projectId into app.json
```

`eas init` writes `extra.eas.projectId` into `app.json`. Commit that.

Then create `mobile/eas.json`:

```json
{
  "cli": { "version": ">= 16.0.0", "appVersionSource": "remote" },
  "build": {
    "development": { "developmentClient": true, "distribution": "internal" },
    "preview": {
      "distribution": "internal",
      "android": { "buildType": "apk" },
      "env": { "EXPO_PUBLIC_API_URL": "https://cars-images-api.onrender.com" }
    },
    "production": {
      "autoIncrement": true,
      "android": { "buildType": "app-bundle" },
      "env": { "EXPO_PUBLIC_API_URL": "https://cars-images-api.onrender.com" }
    }
  },
  "submit": { "production": {} }
}
```

Two details that matter:

- **`buildType: "apk"`** on the `preview` profile. The default is
  `app-bundle` (AAB), which the Play Store wants but a phone cannot install.
  Use `production` (AAB) only if you ever publish to the Play Store.
- **`env`** per profile, because EAS builds on its own machines and never sees
  `mobile/.env`. Leave it out and the app ships pointed at `localhost:8000` —
  the same trap that shipped a broken web bundle once already (see the
  `--no-build` note in `.github/workflows/web.yml`).

## Building

```bash
cd mobile
eas build --platform android --profile preview
```

First run asks to generate an Android keystore — say yes and let EAS keep it.
The build runs in Expo's cloud; the free tier queues, so expect roughly
10–30 minutes. It ends with a download URL, also listed under **Builds** at
<https://expo.dev>.

## Installing it

Send the URL. On the phone: open it in Chrome, download, tap the file, and
allow "install from unknown sources" when prompted. That warning is normal for
any app not from the Play Store; say so up front if you are sending it to
someone.

Sanity-check before sharing: install it yourself, sign in, run one search, and
confirm the images load. That proves the baked-in `EXPO_PUBLIC_API_URL` is the
Render one, not localhost.

## Optional: build on a version tag

Only worth wiring once the app is stable. Add an `EXPO_TOKEN` repository secret
(Expo dashboard → **Access tokens**), then a workflow that mirrors
`.github/workflows/mobile.yml` but triggers on tags:

```yaml
on:
  push:
    tags: ["v*"]

jobs:
  android:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mobile
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with: { node-version: 22, cache: npm, cache-dependency-path: mobile/package-lock.json }
      - run: npm ci
      - uses: expo/expo-github-action@v8
        with: { eas-version: latest, token: "${{ secrets.EXPO_TOKEN }}" }
      - run: eas build --platform android --profile preview --non-interactive --no-wait
```

`--no-wait` returns as soon as the build is queued, so the job does not burn
Actions minutes waiting on Expo's queue. Collect the artifact from the Expo
dashboard.

## Gotchas

| Problem | Cause and fix |
|---|---|
| App loads but every request fails | `EXPO_PUBLIC_API_URL` missing from the profile's `env`; it fell back to localhost. Rebuild. |
| "App not installed" on the phone | An older build with the same package name and a different signing key is installed. Uninstall it first. |
| Build fails on a native module | Expo Go hid it. Check the module supports the installed SDK, then read the failing step's log on expo.dev. |
| Free-tier queue is long | Builds are first-come; start it well before you need the link. |
| First launch is slow to log in | Render's free instance is asleep. Open `/up` first. |

## What this does not change

The app itself. Same code, same screens, same API — only the packaging. If an
interview is imminent and the APK is not built yet, demo the web build plus
Expo Go on your own phone; that already shows React Native running against the
Django API.
