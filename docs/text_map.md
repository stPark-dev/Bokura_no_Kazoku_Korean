# 텍스트 지도 (2026-11-11)

| 모집단 | 추출 기준 | 단위 | 번역 | 상태 |
|---|---|---:|---:|---|
| 대사 `EVENT.XAP/*.mes` (1,517파일) | `text/event_src.jsonl` | 4,478블록 | 4,478 | 초벌(needs_review) |
| 시스템 메시지 `GAMEMES.XAP/gamemes.mes` | `text/gamemes_src.jsonl` | 60블록 | 60 | 초벌 |
| 줄 단위 시스템 텍스트 `*/*.txt`, `*/*/*.txt` | `text/sys_src.jsonl` | 2,461줄 | 2,172 | 초벌, 퀴즈 289줄(D8 새 출제) 진행 중 |

## 제외 (근거)
- `FONT.XAP/vcode.txt`: 세로쓰기 문장부호 치환표, 표시 텍스트 아님(D5).
- `MENU.XAP/kanji.txt`: 이름 입력 한자 후보 → 자모판으로 대체(D6, `build_poc2`).
- `GAMEDB.XAP/readme.txt`: 실행 파일 문자열·데이터 목록 어디에도 이름이 없어 로드되지 않음.
- `MAP.XAP`/`CHR.XAP` 안쪽 XAP의 txt: 개발 주석만(조사 당시 확인, 주석은 `#` 이후라 소비되지 않음).
- `.scb` 바이트코드: 일본어 문자열 없음.

## 아직 범위 밖 / 미조사
- 실행 파일 안 문자열(가나 색인 표 등 이름 입력 관련은 PoC2에서 처리, 그 밖 미조사).
- 그림 글자(tm2), 동영상(PSS) 자막·크레딧.
