# Pitstop

A small, open-source command-line toolkit for keeping a Windows PC healthy. Routine maintenance and troubleshooting usually means jumping between Settings, Control Panel, Task Manager and a terminal, and remembering which command does what. Pitstop brings those tasks into one interactive menu you navigate with the arrow keys.

> **Status:** early development. The set of available tools will grow over time.

## Two ways to use it

**Scan.** Pitstop inspects the machine, never changing anything, and reports what needs attention. Each finding comes with a suggestion and, when Pitstop can help, a fix you can apply right from the report.

**Manual control.** Pick a category, then pick exactly the action you want to run. Nothing runs unless you choose it.

Settings (language, action log) live in a third tab.

## Principles

- **Safe by default.** Anything that changes the system shows a preview of what will happen and asks for confirmation first. On the command line, actions are a dry run unless you pass `--apply`.
- **Transparent.** Every change is written to a plain-text log you can read.
- **Small and modular.** Few dependencies, small functions, easy to read and extend.
- **Localizable.** English first, with support for other languages.

## Non-goals

Pitstop is not a one-click "optimizer", makes no performance miracle claims, collects no telemetry, and does not replace enterprise device management.

## Requirements

- Windows 10 or 11
- Python 3.12 or newer
- An elevated (administrator) terminal for actions that need it. Pitstop tells you when that is the case.

## Installation

```powershell
git clone https://github.com/djDARKWAY/pitstop.git
cd pitstop
pip install .
```

## Usage

Start the interactive menu:

```powershell
pitstop
```

Or use it from scripts:

```powershell
pitstop list                    # show available actions and their ids
pitstop scan                    # report issues without changing anything
pitstop run <action>            # dry run: preview only
pitstop run <action> --apply    # preview, then execute
```

`python -m pitstop` works too.

## Languages

The interface language is chosen in **Settings** and remembered between runs. Translations are plain JSON files in `src/pitstop/locales/`.

To add a language, copy `en.json`, translate the values (keep the keys and the `{placeholders}` unchanged) and set `language.name`. The test suite checks that every translation has the same keys and placeholders as English.

## Data and logs

Pitstop stores its settings and action log in `%LOCALAPPDATA%\Pitstop`. The log can also be viewed from **Settings**.

## Project layout

```
src/pitstop/
  actions/      one module per category; each action has a preview and an apply step
  locales/      translations
  scan.py       read-only checks that produce findings
  runner.py     applies an action, handles errors and logging
  ui.py         interactive menus
  cli.py        command-line entry point
tests/
```

Adding a tool means defining an `Action`, registering it in its category module and adding its texts to the locale files.

## Development

```powershell
pip install -e ".[dev]"
ruff check .
pytest
```

## Contributing

Issues and pull requests are welcome. Keep changes small and focused, avoid new dependencies unless they clearly pay for themselves, and include tests for new behavior.

## Disclaimer

Pitstop modifies system files and settings when you ask it to. Read each preview before confirming, and use it at your own risk.

## License

[MIT](LICENSE)
