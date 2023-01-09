@echo off
if "%1%" == "" powershell Write-Host "Invalid 1-st param, smth like to ..\omd\packages" -ForegroundColor Red && goto usage
if "%2%" == "" powershell Write-Host "Invalid 2-st param, smth like to extlibs" -ForegroundColor Red && goto usage

set omd_path=%1%

set unpacker_exe=7z.exe
set unpacker=%unpacker_exe% x -y
set out_root=%2%
set unpack_cmd=scripts\unpack_package.cmd
if not exist "%unpack_cmd%" powershell Write-Host "%unpack_cmd% not found" -ForegroundColor red  && goto end

rem with internal folder in the tar.gz
set nm=googletest
set vv=-71140c3ca7-patched
set src_dir_name=%omd_path%\..\..\third_party\%nm%
if not exist %src_dir_name% powershell Write-Host "%src_dir_name% is not found" -ForegroundColor Red && goto end
set src_file_name=%nm%%vv%
set out_dir_name=%nm%
powershell Write-Host "%out_dir_name%:" -ForegroundColor blue
call %unpack_cmd% %unpacker_exe% %src_dir_name% %src_file_name% %out_root% %out_dir_name% *

rem with internal folder in the tar.gz
set nm=yaml-cpp
set vv=.9a362420
set src_dir_name=%omd_path%\%nm%
if not exist %src_dir_name% powershell Write-Host "%src_dir_name% is not found" -ForegroundColor Red && goto end
set src_file_name=%nm%%vv%
set out_dir_name=%nm%
powershell Write-Host "%out_dir_name%:" -ForegroundColor blue
call %unpack_cmd% %unpacker_exe% %src_dir_name% %src_file_name% %out_root% %out_dir_name% *

rem without internal folder in the tar.gz
set nm=simpleini
set vv=-2af65fc
set src_dir_name=%omd_path%\%nm%
if not exist %src_dir_name% powershell Write-Host "%src_dir_name% is not found" -ForegroundColor Red && goto end
set src_file_name=%nm%%vv%
set out_dir_name=%nm%
powershell Write-Host "%out_dir_name%:" -ForegroundColor blue
call %unpack_cmd% %unpacker_exe% %src_dir_name% %src_file_name% %out_root% %out_dir_name% %out_dir_name%

goto end
:usage
powershell Write-Host "Usage example:" -ForegroundColor Red
powershell Write-Host "%0% ..\..\..\omd\packages . ..\mypacks" -ForegroundColor DarkGreen
:end
