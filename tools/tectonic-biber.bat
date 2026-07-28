@echo off
rem Wrapper so tectonic can find biber (tools\biber) when launched from
rem VS Code / LaTeX Workshop, where the pixi environment is not active.
set "PATH=%~dp0biber;%PATH%"
"%~dp0..\.pixi\envs\default\python.exe" "%~dp0count_sentences.py"
"%~dp0..\.pixi\envs\default\python.exe" "%~dp0check_units.py"
"%~dp0..\.pixi\envs\default\Library\bin\tectonic.exe" %*
