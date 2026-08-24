@echo off
rem Wrapper so tectonic can find biber (tools\biber) and tikz-external.bat
rem (tools) when launched from VS Code / LaTeX Workshop, where the pixi
rem environment is not active. Not named tectonic-biber*: tectonic would take
rem that for biber. search-path: paper-notes reads the thesis's units.tex and
rem references.bib in place.
set "PATH=%~dp0biber;%~dp0;%PATH%"
"%~dp0..\.pixi\envs\default\Library\bin\tectonic.exe" -Z search-path="%~dp0..\src\thesis" %*
