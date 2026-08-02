# notes

Mini gestore di note a comandi. Convenzione: un modulo per comando in
`commands/` (NAME, HELP, run), registrato via `registry.register` all'import
e importato in `commands/__init__.py`.
