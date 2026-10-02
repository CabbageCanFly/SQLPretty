# SQLPretty

A small Sublime Text plugin that formats SQL using the external [`sql-formatter`] command-line tool.

The goal is intentionally simple:

- Format the entire SQL document from the Command Palette.
- Format only the selected SQL when text is selected.
- Run formatting asynchronously so Sublime Text does not freeze while the formatter is running.
- Uppercase SQL keywords.
- Avoid opening a terminal window on Windows.
- Keep the plugin small and understandable.

## Current Status

This is currently a personal/experimental Sublime Text plugin.

It works locally, but it has not yet been packaged or submitted to Package Control.

The current implementation assumes:

- Sublime Text 4
- Python support provided by Sublime Text
- Node.js/npm installed on the user's system
- `sql-formatter` installed globally and available on `PATH`

## What It Does

Given SQL such as:

```sql
select id,name,total from customers where total > 20 order by total desc;
```

the plugin invokes `sql-formatter` and replaces the editor contents with formatted SQL, for example:

```sql
SELECT
    id,
    name,
    total
FROM
    customers
WHERE
    total > 20
ORDER BY
    total DESC;
```

If text is selected, only the selection is formatted.

If nothing is selected, the entire document is formatted.

## Requirements

### Sublime Text

The plugin is intended for Sublime Text 4.

### Node.js and npm

The current implementation depends on the external `sql-formatter` CLI.

Node.js/npm must therefore be installed.

### sql-formatter

Install the formatter globally:

```bash
npm install -g sql-formatter
```

Verify that it is available:

```bash
sql-formatter --version
```

The command must be visible on the system `PATH` used by Sublime Text.

## Manual Installation

Until this plugin is published through Package Control, it can be installed manually.

In Sublime Text:

```text
Preferences → Browse Packages...
```

Create a folder such as:

```text
SQLPretty
```

Place the plugin files inside that directory:

```text
SQLPretty/
├── format_sql.py
└── Default.sublime-commands
```

Restarting Sublime Text should normally not be necessary because Sublime reloads Python plugins automatically.

## Usage

Open the Sublime Text Command Palette:

```text
Ctrl + Shift + P
```

Search for:

```text
SQL: Format Document / Selection
```

Run the command.

### No selection

The entire document is formatted.

### Selection present

Only the selected SQL is formatted.

Multiple selections are also supported.

## Command Palette Entry

`Default.sublime-commands`:

```json
[
    {
        "caption": "SQL: Format Document / Selection",
        "command": "format_sql"
    }
]
```

Sublime converts the Python class:

```python
FormatSqlCommand
```

into the command name:

```text
format_sql
```

## Current Formatter Configuration

The formatter is currently configured inside `format_sql.py` with:

```python
config = json.dumps({
    "language": "sqlite",
    "keywordCase": "upper",
    "tabWidth": 4
})
```

This means the current defaults are:

- SQL dialect: SQLite
- SQL keywords: uppercase
- indentation width: 4 spaces

Example:

```sql
select name from customers where id = 10;
```

becomes:

```sql
SELECT
    name
FROM
    customers
WHERE
    id = 10;
```

## Supported SQL Dialects

The underlying `sql-formatter` project supports multiple SQL dialects.

The plugin currently hardcodes:

```text
sqlite
```

Future versions should expose the dialect through Sublime settings instead.

Potential dialects include:

```text
sql
sqlite
postgresql
mysql
mariadb
bigquery
duckdb
snowflake
spark
tsql
transactsql
plsql
redshift
trino
```

Always check the current `sql-formatter` documentation for the authoritative list.

## How It Works

The plugin follows this basic flow:

```text
User chooses command from Command Palette
                ↓
Plugin reads current selection/document
                ↓
Plugin finds sql-formatter on PATH
                ↓
Formatting runs on Sublime's async worker thread
                ↓
SQL is sent to sql-formatter through stdin
                ↓
Formatted SQL is read from stdout
                ↓
Plugin returns to Sublime's main thread
                ↓
Original text is replaced
```

The plugin does not implement SQL formatting itself.

It acts as a bridge between Sublime Text and the external `sql-formatter` CLI.

## Why Formatting Runs Asynchronously

Starting an external Node.js command can take noticeable time.

Running:

```python
subprocess.run(...)
```

directly inside a Sublime command would block Sublime's UI until the formatter exits.

Instead, formatting is dispatched using:

```python
sublime.set_timeout_async(...)
```

This prevents the editor interface from hanging while the external formatter is running.

## Protection Against Editing During Formatting

Before starting the formatter, the plugin records:

```python
self.view.change_count()
```

When formatting finishes, it checks whether the document changed in the meantime.

If the user edited the document while formatting was running, the formatted output is discarded instead of overwriting newer edits.

The status bar displays:

```text
SQL formatting cancelled: file changed.
```

## Windows Terminal Window Suppression

On Windows, launching an external process can otherwise briefly display a console window.

The plugin uses:

```python
subprocess.CREATE_NO_WINDOW
```

when running on Windows.

Other operating systems receive:

```python
creationflags=0
```

This keeps the formatter process invisible to the user.

## Troubleshooting

### `sql-formatter not found`

The plugin uses:

```python
shutil.which("sql-formatter")
```

to locate the formatter.

First confirm that this works in a terminal:

```bash
sql-formatter --version
```

If it works in the terminal but not from Sublime Text, Sublime may have a different `PATH` environment.

A future version of the plugin should support manually configuring the full path to the formatter.

For example:

```json
{
    "formatter_path": "C:\\Users\\username\\AppData\\Roaming\\npm\\sql-formatter.cmd"
}
```

This is not implemented yet.

### Formatting is slow

The plugin launches an external Node.js process every time formatting is requested.

There is therefore some startup overhead:

```text
Sublime
→ operating system process creation
→ Node.js startup
→ sql-formatter startup
→ SQL parsing
→ formatting
→ output returned
```

The formatting itself is asynchronous, so Sublime should remain responsive.

Future versions could investigate ways to reduce process startup overhead.

### SQL syntax formats strangely

Make sure the configured SQL dialect matches the SQL being written.

The plugin currently uses SQLite:

```python
"language": "sqlite"
```

A PostgreSQL, MySQL, T-SQL, Snowflake, etc. file may produce better results when the matching formatter dialect is selected.

## Known Limitations

Current limitations include:

- Requires Node.js.
- Requires a separate global installation of `sql-formatter`.
- Requires `sql-formatter` to be available on Sublime's `PATH`.
- SQL dialect is currently hardcoded to SQLite.
- Formatting configuration is currently hardcoded.
- No Sublime settings file yet.
- No automatic dialect detection.
- No format-on-save support.
- No Package Control release yet.
- External process startup can introduce a short delay.
- This is a formatter, not a SQL linter.

## Formatter vs Linter

This plugin formats SQL.

It handles things such as:

- indentation
- whitespace
- line breaks
- keyword capitalization

It does not attempt to detect semantic SQL problems or enforce a large set of SQL style rules.

A tool such as SQLFluff serves a different purpose and may be worth integrating separately in the future.

## Planned Improvements

Possible future improvements:

- Add `SQLPretty.sublime-settings`.
- Allow selecting the SQL dialect.
- Allow configuring keyword capitalization.
- Allow changing indentation width.
- Allow setting an explicit `sql-formatter` executable path.
- Detect `.sql-formatter.json`.
- Detect common SQL syntaxes automatically.
- Improve error reporting.
- Add format-on-save as an optional feature.
- Add automated tests.
- Test Windows, macOS, and Linux.
- Package for Package Control.
- Investigate removing or reducing the Node.js dependency.

## Repository Structure

Planned repository structure:

```text
SQLPretty/
├── format_sql.py
├── Default.sublime-commands
├── README.md
├── DEVELOPMENT.md
├── LICENSE
└── .gitignore
```

Possible future files:

```text
SQLPretty.sublime-settings
messages.json
messages/
tests/
```

## License

A permissive open-source license such as MIT would be appropriate if this project is published publicly.

The license of this plugin and the license of the external `sql-formatter` project are separate.

Review dependency licensing before bundling any third-party source code or binaries directly into this repository.

## Credits

Formatting is performed by the external `sql-formatter` project.

This Sublime Text plugin is only an editor integration around that formatter.
