#!/bin/sh
# 우리들의 가족(ぼくらの家族) 한글패치 v{{VERSION}} - Linux/macOS 적용 스크립트
#
#   sh apply.sh "Bokura no Kazoku (Japan).iso"
#
# 원본 ISO는 그대로 두고, 이 폴더에 {{OUT_NAME}}을 새로 만듭니다.
# xdelta3가 필요합니다 (Debian·Ubuntu: sudo apt install xdelta3, macOS: brew install xdelta).
set -eu

SRC_SHA1='{{SRC_SHA1}}'
OUT_SHA1='{{OUT_SHA1}}'
HERE=$(cd "$(dirname "$0")" && pwd)
PAYLOAD="$HERE/patch/{{PATCH_FILE}}"
OUT="$HERE/{{OUT_NAME}}"

die() { echo "오류: $*" >&2; exit 1; }
sha1() {
    if command -v sha1sum >/dev/null 2>&1; then sha1sum "$1" | cut -d' ' -f1
    else shasum -a 1 "$1" | cut -d' ' -f1; fi
}

[ $# -eq 1 ] || die "원본 ISO 경로를 하나 지정해 주세요. 예: sh apply.sh \"Bokura no Kazoku (Japan).iso\""
SRC=$1
[ -f "$SRC" ] || die "파일이 없습니다: $SRC"
[ -f "$PAYLOAD" ] || die "patch 폴더의 패치 파일이 없습니다. 받은 zip을 완전히 풀어 주세요."
command -v xdelta3 >/dev/null 2>&1 || die "xdelta3가 필요합니다 (예: sudo apt install xdelta3, brew install xdelta)."
[ ! -e "$OUT" ] || die "이미 있습니다: $OUT (지우거나 옮긴 뒤 다시 실행해 주세요)"

echo "원본 확인 중 (SHA1)..."
[ "$(sha1 "$SRC")" = "$SRC_SHA1" ] ||
    die "일본판 ぼくらの家族 (SCPS-15088) 원본 ISO가 아닙니다. SHA1이 $SRC_SHA1 인 ISO가 필요합니다."
echo "패치 적용 중..."
xdelta3 -d -s "$SRC" "$PAYLOAD" "$OUT" || { rm -f "$OUT"; die "패치 적용에 실패했습니다."; }
echo "결과 확인 중 (SHA1)..."
[ "$(sha1 "$OUT")" = "$OUT_SHA1" ] || { rm -f "$OUT"; die "결과가 예상과 다릅니다. 받은 zip이 손상되었을 수 있습니다."; }
echo "완료: $OUT"
echo "에뮬레이터(PCSX2 등)에서 이 ISO를 여세요."
