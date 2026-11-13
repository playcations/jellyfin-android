# Familyfin Web prototype verification

The app keeps the server's current mobile layout and Jellyfin Android's mobile
player. `librePhoneDebug` disables physical navigation; `libreTvDebug` enables
`BuildConfig.PHYSICAL_NAVIGATION` and adds a Leanback launcher, optional touch
and Wi-Fi features, and banner. Both use `com.playcations.familyfin.web.debug`.
They upgrade/replace one another on an emulator. Namespace and licenses remain
upstream's. Release builds use `com.playcations.familyfin.web`.

## Builds

With JDK 21 and Android SDK 37 available:

```sh
JELLYFIN_VERSION=0.1.0-familyfin.1 ./gradlew \
  assembleDebug assembleLibreTvDebugAndroidTest
```

APKs are under `app/build/outputs/apk/librePhone/debug`,
`app/build/outputs/apk/libreTv/debug`, and
`app/build/outputs/apk/androidTest/libreTv/debug`. The signing configuration is
upstream's existing debug signing setup; these scripts never create or overwrite
keys explicitly. `verify_apks.py` copies outputs, checks package/version/launcher,
verifies signatures, compares signer certificates and source/copy SHA-256 values,
and writes JSON and command evidence:

```sh
python3 tests/verify_apks.py --artifacts build/verified-apks
```

`assembleDebug` also builds proprietary phone/TV variants with the upstream
Google Cast support. Verify all four with `--flavor librePhone --flavor libreTv
--flavor proprietaryPhone --flavor proprietaryTv`. The default fork version is
`0.1.0-familyfin.1`; `JELLYFIN_VERSION` overrides it for subsequent releases.

## Browser input regression suite

```sh
python3 -m venv tests/.venv
tests/.venv/bin/pip install -r tests/requirements.txt
tests/.venv/bin/python -m playwright install chromium
tests/.venv/bin/python tests/test_navigation.py
```

Optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE` selects an existing Chromium. Optional
`--web-source /path/to/jellyfin-web` tests a different source checkout; otherwise
the suite uses the attributed, unmodified upstream dispatcher/focus modules in
`fixtures/jellyfin-web-12.2`. `--artifacts PATH` selects the evidence directory.
The fixture is fulfilled inside Playwright, with no HTTP server or real Jellyfin
instance. It covers representative modern buttons/roles and legacy card markup,
not a full authenticated server UI. See `navigation-tests.json` for the actual
scenarios and results.

All commands route through the injected `inputManager`. Existing target-level
command handlers retain first refusal. The APK adapter handles fallback spatial
movement for current mobile markup, visible focus, scrolling, route/scope memory,
and modern/legacy overlay dismissal. It does not set `layoutManager.tv` or inspect
device/user-agent strings. Native buttons, forms, Tab, text editing, modifiers,
composition and media keys keep their normal input paths. Pointer input suspends
automatic focus restoration until physical navigation resumes.

## Native mobile player instrumentation

`PhysicalPlayerTest` seeds an isolated local download with generated H.264,
two AAC audio tracks and two embedded subtitle tracks. A non-exported **debug
only** activity hosts the real `PlayerFragment`, `PlayerViewModel`, `PlayerMenus`,
Media3 controller, and media session. No household server is used; incidental
settings requests fail against emulator loopback port 9. The test is intended
for an isolated emulator with a fresh app profile.

Build the TV app and instrumentation APK, then supply the explicit local serial:

```sh
ANDROID_HOME=/path/to/sdk FAMILYFIN_ADB_PORT=5037 \
  tests/run_instrumentation.sh emulator-5554 build/native-test-artifacts
```

The runner rejects non-emulator serials and does not discover or connect to
network devices. Assertions cover actual decode readiness, wake without an
unintended toggle, physical focus traversal, timebar seek, audio/subtitle menus,
popup focus return, controller timeout, TV PiP guard, media-session pause and
lock-screen Back. A compiled test APK is not evidence that these assertions ran;
only a successful instrumentation log is.

The final suite passed on a disposable Android TV API28 x86 emulator, including
actual decoder-selected French audio and renderer-selected English subtitles.
Menu selection navigates by visible labels because initial popup selection
differs between Android versions. The short timeout used to verify auto-hide is
restored before testing remote wake. No physical-device results are claimed.

The media fixture is synthetic. Its video is a navy 320x180 frame at 10 fps;
audio is 440 Hz/880 Hz, and subtitles come from `media/*.srt`. Regenerate it with
`tests/media/generate.sh` (requires ffmpeg). No third-party media is included.
