@echo off
setlocal
title Pushing to GitHub: Sarveshwaran-V/LID0501
echo ========================================================
echo   Pushing LID0501 Lead Engine to GitHub
echo   Repository: https://github.com/Sarveshwaran-V/LID0501
echo ========================================================
echo.

set PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%

echo Staging all project files...
git add .

echo Committing files...
git commit -m "Initial commit: LID0501 Free B2B Lead Discovery and Qualification Engine" 2>nul

echo Configuring remote...
git remote remove origin 2>nul
git remote add origin https://github.com/Sarveshwaran-V/LID0501.git
git branch -M main

echo.
echo Pushing code to GitHub...
echo (A browser window may open asking to authorize Git Credential Manager - click Authorize!)
echo.

git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   SUCCESS! LID0501 repository pushed to GitHub!
    echo   Link: https://github.com/Sarveshwaran-V/LID0501
    echo ========================================================
    echo.
) else (
    echo.
    echo Note: If GitHub says "Repository not found", please ensure you have
    echo created the empty repository on GitHub first at:
    echo   https://github.com/new (Repository name: LID0501)
    echo Then run this script again!
    echo.
)

pause
