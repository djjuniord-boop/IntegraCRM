#!/usr/bin/env bash
# Buduje aplikację Android bez Gradle. Użycie: mobile/build_apk.sh <wyjście.apk>
# Podpis: zmienne KEYSTORE (plik), KEYSTORE_PASS; bez nich – klucz testowy (tylko do prób).
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-/opt/android/sdk}; BT=$SDK/build-tools/35.0.0; JAR=$SDK/platforms/android-34/android.jar
OUT=$(realpath -m "${1:-build/oferty.apk}"); V=$(cat VERSION); CODE=$(echo "$V" | awk -F. '{print $1*10000+$2*100+$3}')
rm -rf build/tmp && mkdir -p build/tmp/{res,classes,dex,assets/www} "$(dirname "$OUT")"
cp www/*.html www/*.js www/*.css www/*.png build/tmp/assets/www/
"$BT/aapt2" compile --dir android/res -o build/tmp/res.zip
"$BT/aapt2" link -o build/tmp/base.apk -I "$JAR" --manifest android/AndroidManifest.xml -A build/tmp/assets \
  --version-name "$V" --version-code "$CODE" --java build/tmp/gen build/tmp/res.zip
javac --release 8 -nowarn -classpath "$JAR" -d build/tmp/classes \
  $(find android/src build/tmp/gen -name "*.java")
"$BT/d8" --release --min-api 24 --lib "$JAR" --output build/tmp/dex $(find build/tmp/classes -name '*.class')
cp build/tmp/base.apk build/tmp/u.apk && (cd build/tmp/dex && zip -q ../u.apk classes.dex)
"$BT/zipalign" -f -p 4 build/tmp/u.apk build/tmp/a.apk
if [ -z "${KEYSTORE:-}" ]; then
  KEYSTORE=build/test.jks; KEYSTORE_PASS=testtest
  [ -f $KEYSTORE ] || keytool -genkeypair -keystore $KEYSTORE -storepass $KEYSTORE_PASS -keypass $KEYSTORE_PASS -alias oferty -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Test" >/dev/null
fi
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass "pass:$KEYSTORE_PASS" --out "$OUT" build/tmp/a.apk
"$BT/apksigner" verify "$OUT" && echo "OK: $OUT (wersja $V)"
