@echo off
rem Wrapper so tectonic can find biber (tools\biber) when launched from
rem VS Code / LaTeX Workshop, where the pixi environment is not active.
rem search-path: paper-notes reads the thesis's units.tex and references.bib.
set "PATH=%~dp0biber;%PATH%"
"%~dp0..\.pixi\envs\default\Library\bin\tectonic.exe" -Z search-path="%~dp0..\src\thesis" %*
