@echo off
cd /d "%~dp0"

echo.
echo Staging all changes...
git add .

echo.
set /p MSG="Commit message (or press ENTER for 'Update'): "
if "%MSG%"=="" set MSG=Update

git commit -m "%MSG%"

echo.
echo Pushing to GitHub...
git push origin main

echo.
echo Done.
pause
