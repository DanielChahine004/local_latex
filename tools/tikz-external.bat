@echo off
rem TikZ externalisation under tectonic, which has no -jobname. The main run
rem calls this via \write18 with cwd = its outdir and %1 = figure name. A
rem driver named after the figure gives the sub-run the right \jobname.
rem Quotes stripped: \write18 quoting varies by engine. The run.xml is
rem suppressed because tectonic would read it and run biber on a sub-run;
rem the stale .dpth goes because tectonic leaves a file it would write empty.
set "fig=%~1"
set "fig=%fig:"=%"
del /q "%fig%.dpth" 2>nul
echo \makeatletter\def\tikzexternalrealjob{main}\AtEndDocument{\let\lrq@writeout\relax}\makeatother\input{main}> "%fig%.tex"
"%~dp0..\.pixi\envs\default\Library\bin\tectonic.exe" --reruns 0 -Z search-path="%~dp0..\src\thesis" "%fig%.tex"
