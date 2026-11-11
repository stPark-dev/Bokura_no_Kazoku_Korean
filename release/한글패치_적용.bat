@echo off
chcp 65001 >nul
setlocal
rem 우리들의 가족(ぼくらの家族) 한글패치 v{{VERSION}} - Windows 적용
rem 사용법: 원본 ISO를 이 파일 위에 끌어다 놓거나, 원본 ISO를 이 폴더에 넣고 더블클릭
set "HERE=%~dp0"
set "DECODER=%HERE%tools\xdelta3decode.exe"
set "PAYLOAD=%HERE%patch\{{PATCH_FILE}}"
set "OUT=%HERE%{{OUT_NAME}}"
set "SRC=%~1"

echo 우리들의 가족(ぼくらの家族) 한글패치 v{{VERSION}}
echo.
if not exist "%DECODER%" goto nozip
if not exist "%PAYLOAD%" goto nozip
if defined SRC goto havesrc
pushd "%HERE%"
for %%F in (*.iso) do if /i not "%%~nxF"=="{{OUT_NAME}}" set "SRC=%%~fF"
popd
if not defined SRC goto nosrc
:havesrc
if not exist "%SRC%" goto nosrc
if exist "%OUT%" goto exists

echo 원본: %SRC%
echo 패치를 적용하는 중입니다. 몇 분 걸릴 수 있습니다...
"%DECODER%" -d -s "%SRC%" "%PAYLOAD%" "%OUT%"
if errorlevel 1 goto failed
echo.
echo 완료: %OUT%
echo 에뮬레이터 PCSX2 등에서 이 ISO를 여세요.
goto end

:nozip
echo 오류: tools 또는 patch 폴더가 없습니다. 받은 zip을 완전히 푼 다음 실행해 주세요.
goto end
:nosrc
echo 오류: 원본 ISO를 찾지 못했습니다.
echo 원본 ISO를 이 파일 위에 끌어다 놓거나, 원본 ISO를 이 폴더에 넣고 다시 실행해 주세요.
goto end
:exists
echo 오류: 이미 한글판 ISO가 있습니다: %OUT%
echo 지우거나 다른 폴더로 옮긴 뒤 다시 실행해 주세요.
goto end
:failed
if exist "%OUT%" del "%OUT%"
echo.
echo 오류: 패치 적용에 실패했습니다.
echo 일본판 ぼくらの家族 SCPS-15088 원본 ISO가 맞는지 확인해 주세요.
echo 필요한 원본 SHA1: {{SRC_SHA1}}
:end
echo.
pause
