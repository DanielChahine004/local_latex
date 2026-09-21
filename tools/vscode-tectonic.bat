@echo off
rem Wrapper so tectonic can find biber (tools\biber) and tikz-external.bat
rem (tools) when launched from VS Code / LaTeX Workshop, where the pixi
rem environment is not active. Not named tectonic-biber*: tectonic would take
rem that for biber. search-path: paper-notes reads the thesis's units.tex and
rem references.bib in place.
rem
rem All three documents build into the one flat build\ (LaTeX Workshop's
rem outDir), so they share main.aux/main.toc. A .toc left by the book-class
rem thesis breaks the article-class notes ("missing \item" at main.toc:3), so
rem when the document changes from the last build, the shared intermediates
rem are removed first. TikZ stamps (main-figure*) are left alone.
set "PATH=%~dp0biber;%~dp0;%PATH%"
set "out=%~dp0..\build"
set "doc="
for %%A in (%*) do set "doc=%%~A"
set "last="
if exist "%out%\.last-doc" set /p last=<"%out%\.last-doc"
if /i not "%doc%"=="%last%" (
	for %%F in (aux toc lof lot out bbl bcf blg run.xml) do if exist "%out%\main.%%F" del "%out%\main.%%F"
	>"%out%\.last-doc" echo %doc%
)
"%~dp0..\.pixi\envs\default\Library\bin\tectonic.exe" -Z search-path="%~dp0..\src\thesis" %*
