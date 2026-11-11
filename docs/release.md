# 빌드·배포 절차

1. 동영상(무거움, 원본 바뀔 때만): `tools/build_movies.py work/orig.iso work/movie_ko` → `work/movie_ko/manifest.json`
2. 제품 빌드: `tools/build_patch.py work/orig.iso work/build/beta.iso --policy beta`
   - `dev`: 상태 무관(개발용, 배포 안 함) / `beta`: 전 단위 번역 + `reviewed` 이상 / `release`: 전 단위 `distribution_eligible`
   - 원본 SHA1(`f2a8187…`), 동영상 매니페스트의 원본 해시·파일 해시를 확인. 실패하면 멈춤.
   - `<iso>.manifest.json`: 정책, 원본/결과 SHA1, 커밋, 교체 파일, 승인된 예외(D9·D10 등), 단위 수.
3. 패키지: `tools/package_release.py work/build/beta.iso <버전> --decoder <xdelta3decode.exe> --decoder-license <LICENSE>`
   - xdelta 패치를 다시 풀어 결과 SHA1을 재현해야 패키징. `work/dist/<이름>.zip` + `.sha256`.
   - 템플릿: `release/` (적용 스크립트·안내문·배포 조건·서드파티 고지).
4. 확인: zip을 풀어 `sh apply.sh <원본 ISO>` → 결과 SHA1이 매니페스트와 같아야 함. PCSX2 부팅 확인.

필요 도구: Python venv(`pillow`, `keystone-engine`, `opencv-python-headless`, `numpy`, 테스트용 `pytest`·`unicorn`·`capstone`), `ffmpeg`, `xdelta3`.
