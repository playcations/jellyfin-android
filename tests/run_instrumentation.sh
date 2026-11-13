#!/usr/bin/env bash
set -euo pipefail
# Deliberately requires an explicit local emulator; never enumerates/connects to network devices.
serial=${1:?Usage: tests/run_instrumentation.sh emulator-NNNN [artifacts-dir]}
[[ "$serial" =~ ^emulator-[0-9]+$ ]] || { echo 'Only an explicit local emulator serial is accepted.' >&2; exit 2; }
cd "$(dirname "$0")/.."
artifacts=${2:-build/native-test-artifacts}
mkdir -p "$artifacts"
adb_bin="${ANDROID_HOME:?Set ANDROID_HOME}/platform-tools/adb"
adb_port=${FAMILYFIN_ADB_PORT:-5037}
cleanup() {
    # Release the completed instrumentation's UI-automation connection before another app's smoke checks.
    "$adb_bin" -P "$adb_port" -s "$serial" shell am force-stop com.playcations.familyfin.web.debug >/dev/null 2>&1 || true
    "$adb_bin" -P "$adb_port" -s "$serial" shell am force-stop com.playcations.familyfin.web.debug.test >/dev/null 2>&1 || true
}
trap cleanup EXIT
"$adb_bin" -P "$adb_port" -s "$serial" install -r "$(find app/build/outputs/apk/libreTv/debug -name '*.apk' | sort | tail -1)"
"$adb_bin" -P "$adb_port" -s "$serial" install -r "$(find app/build/outputs/apk/androidTest/libreTv/debug -name '*.apk' | sort | tail -1)"
"$adb_bin" -P "$adb_port" -s "$serial" shell am instrument -w -r -e class org.jellyfin.mobile.PhysicalPlayerTest com.playcations.familyfin.web.debug.test/androidx.test.runner.AndroidJUnitRunner | tee "$artifacts/instrumentation.log"
rg -q '^OK \(1 test\)' "$artifacts/instrumentation.log"
