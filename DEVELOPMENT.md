# SQLPretty Development Notes

This document records the current implementation, design decisions, known problems, and potential publishing process for the SQLPretty Sublime Text plugin.

It is mainly intended as notes for future development.

# Current Goal

Provide a very small Sublime Text 4 integration for the modern `sql-formatter` CLI.

The desired UX is:

```text
Ctrl + Shift + P
→ SQL: Format Document / Selection
→ SQL formatted in place
```

No custom keyboard shortcut is required.

The Command Palette is intentionally the primary interface.

# Current Repository Layout

```text
SQLPretty/
├── format_sql.py
├── Default.sublime-commands
├── README.md
├── DEVELOPMENT.md
├── LICENSE
└── .gitignore
```

# Current Plugin Implementation

`format_sql.py`:

```python
import json
import os
import shutil
import subprocess

import sublime
import sublime_plugin


CREATE_FLAGS = (
    subprocess.CREATE_NO_WINDOW
    if os.name == "nt"
    else 0
)


class FormatSqlCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        formatter = shutil.which("sql-formatter")

        if not formatter:
            sublime.error_message(
                "sql-formatter not found.\n"
                "Install with: npm install -g sql-formatter"
            )
            return

        # Format selection(s), or entire file if nothing selected
        selections = [r for r in self.view.sel() if not r.empty()]

        if selections:
            regions = [[r.begin(), r.end()] for r in selections]
        else:
            regions = [[0, self.view.size()]]

        sql_chunks = [
            self.view.substr(sublime.Region(start, end))
            for start, end in regions
        ]

        change_count = self.view.change_count()

        sublime.status_message("Formatting SQL...")

        # Run outside Sublime's UI thread
        sublime.set_timeout_async(
            lambda: self.format_async(
                formatter,
                regions,
                sql_chunks,
                change_count
            ),
            0
        )

    def format_async(self, formatter, regions, sql_chunks, change_count):
        config = json.dumps({
            "language": "sqlite",
            "keywordCase": "upper",
            "tabWidth": 4
        })

        results = []

        for sql in sql_chunks:
            result = subprocess.run(
                [
                    formatter,
                    "--config",
                    config
                ],
                input=sql,
                text=True,
                capture_output=True,
                creationflags=CREATE_FLAGS
            )

            if result.returncode != 0:
                error_message = result.stderr

                sublime.set_timeout(
                    lambda error_message=error_message:
                        sublime.error_message(error_message),
                    0
                )
                return

            results.append(result.stdout)

        sublime.set_timeout(
            lambda: self.apply_results(
                regions,
                results,
                change_count
            ),
            0
        )

    def apply_results(self, regions, results, change_count):
        # Don't overwrite text if user edited it while formatter was running
        if self.view.change_count() != change_count:
            sublime.status_message(
                "SQL formatting cancelled: file changed."
            )
            return

        self.view.run_command(
            "apply_formatted_sql",
            {
                "regions": regions,
                "results": results
            }
        )


class ApplyFormattedSqlCommand(sublime_plugin.TextCommand):
    def run(self, edit, regions, results):
        # Reverse so replacing earlier text doesn't shift later regions
        for region, result in reversed(list(zip(regions, results))):
            start, end = region

            self.view.replace(
                edit,
                sublime.Region(start, end),
                result
            )

        sublime.status_message("SQL formatted.")
```

# Command Palette Entry

`Default.sublime-commands`:

```json
[
    {
        "caption": "SQL: Format Document / Selection",
        "command": "format_sql"
    }
]
```

No default key binding is currently planned.

Users can create their own Sublime key binding if they want one.

# Why There Are Two TextCommands

The formatting command starts asynchronous work.

The actual buffer modification eventually needs to happen through a Sublime `TextCommand`, because Sublime provides the `edit` object to that command.

Therefore:

```text
FormatSqlCommand
```

handles:

- gathering text
- starting asynchronous formatting
- running the external formatter
- checking whether the document changed

while:

```text
ApplyFormattedSqlCommand
```

handles:

- replacing text inside the Sublime buffer

# External Dependency

The current architecture is:

```text
Sublime Text Python plugin
        ↓
subprocess
        ↓
sql-formatter CLI
        ↓
Node.js
```

The plugin itself does not parse SQL.

This keeps the plugin implementation very small but requires users to install Node.js and `sql-formatter`.

Current installation:

```bash
npm install -g sql-formatter
```

# Why `shutil.which()` Is Used

The plugin currently locates the executable using:

```python
shutil.which("sql-formatter")
```

Benefits:

- works across operating systems
- respects `PATH`
- avoids hardcoding npm installation directories
- naturally finds `.cmd` launchers on Windows

Problem:

GUI applications sometimes inherit a different environment from the user's terminal.

Therefore a future version should support:

```json
{
    "formatter_path": ""
}
```

If empty, use:

```python
shutil.which("sql-formatter")
```

If explicitly configured, use that path instead.

# Why Formatting Is Async

The original implementation called:

```python
subprocess.run(...)
```

directly inside the command.

This caused Sublime Text to appear frozen while Node.js and `sql-formatter` started.

The current implementation instead uses:

```python
sublime.set_timeout_async(...)
```

The external formatter still takes the same amount of real time, but Sublime's UI remains responsive.

# Race Condition Protection

Asynchronous formatting creates an important problem:

1. User starts formatting.
2. Formatter runs.
3. User edits document.
4. Old formatter output returns.
5. Plugin overwrites the user's newer work.

To prevent this, the plugin records:

```python
change_count = self.view.change_count()
```

before formatting.

Before applying results:

```python
if self.view.change_count() != change_count:
```

the operation is cancelled.

This behavior should be retained.

# Windows Console Suppression

On Windows, external process creation may briefly open a console window.

The current implementation uses:

```python
subprocess.CREATE_NO_WINDOW
```

when:

```python
os.name == "nt"
```

Other systems use:

```python
0
```

This should remain platform-specific.

# Current Formatting Configuration

Configuration is currently hardcoded:

```python
{
    "language": "sqlite",
    "keywordCase": "upper",
    "tabWidth": 4
}
```

This was acceptable for the first personal version but should probably be configurable before a public release.

# Recommended Settings Design

Add:

```text
SQLPretty.sublime-settings
```

with defaults such as:

```json
{
    "formatter_path": "",
    "language": "sqlite",
    "keyword_case": "upper",
    "tab_width": 4
}
```

Potential later version:

```json
{
    "formatter_path": "",
    "language": "sqlite",
    "keyword_case": "upper",
    "data_type_case": "preserve",
    "function_case": "preserve",
    "tab_width": 4,
    "use_tabs": false,
    "lines_between_queries": 1
}
```

The plugin could then build the `sql-formatter` JSON configuration dynamically.

# Potential Config Precedence

A future implementation should decide explicitly how configuration sources interact.

One possible order:

```text
project .sql-formatter.json
        ↓
Sublime package settings
        ↓
plugin defaults
```

Alternatively, avoid trying to merge configurations and let users choose whether to use the external config file.

This should be documented clearly before publishing.

# Potential Dialect Handling

Current behavior:

```text
Always SQLite
```

Possible future approaches:

## Option A: User Setting

Simple and predictable:

```json
{
    "language": "postgresql"
}
```

## Option B: Syntax Detection

Inspect Sublime syntax names such as:

```text
SQL
PostgreSQL
MySQL
```

and map them to `sql-formatter` dialects.

This may be convenient but could also produce incorrect guesses.

## Option C: Project Configuration

Prefer `.sql-formatter.json` from the project.

This may be the most natural behavior for developers already using `sql-formatter`.

# Error Handling Improvements

Current error handling displays formatter stderr using:

```python
sublime.error_message(...)
```

Potential improvements:

- Include formatter exit code.
- Detect executable-not-found separately.
- Detect invalid SQL/dialect errors.
- Log full diagnostics to the Sublime console.
- Show concise messages to users.
- Avoid giant stderr dialogs.
- Provide a command to show formatter diagnostics.

# Performance Notes

The primary remaining delay comes from process startup.

Each formatting operation currently performs:

```text
create process
↓
launch Node.js
↓
load sql-formatter
↓
parse SQL
↓
format
↓
exit process
```

Possible future performance investigations:

- Benchmark CLI startup independently.
- Compare global CLI vs `npx`.
- Avoid `npx` because it generally adds additional startup work.
- Investigate a persistent Node process.
- Investigate another formatter with a native executable.
- Investigate embedding a formatter.
- Decide whether additional complexity is justified.

The current async implementation is probably sufficient unless formatting latency becomes genuinely annoying.

# Possible Node-Free Future

There are several possible architectures.

## Current

```text
Sublime plugin
→ system Node.js
→ globally installed sql-formatter
```

Simplest for the maintainer.

## Bundle JavaScript Only

```text
Sublime plugin
→ bundled sql-formatter JavaScript
→ system Node.js
```

Removes the npm installation requirement but still requires Node.

This would also require careful dependency licensing and update management.

## Bundle Node and Formatter

```text
Sublime plugin
→ bundled runtime
→ bundled formatter
```

Best installation experience but substantially increases:

- repository/release size
- operating-system-specific packaging
- architecture handling
- security maintenance
- dependency updates
- release complexity

Probably unnecessary for an early version.

## Native Formatter

Use or build a standalone formatter executable.

Could avoid Node but introduces a different external dependency or build process.

# Selection Behavior

Current logic:

```python
selections = [r for r in self.view.sel() if not r.empty()]
```

If at least one non-empty selection exists:

```text
format selections
```

Otherwise:

```text
format entire document
```

Multiple selections are formatted independently.

Regions are applied in reverse order:

```python
reversed(list(zip(regions, results)))
```

This prevents replacement of earlier text from shifting the coordinates of later selections.

# Potential Selection Edge Cases

Test:

- one normal selection
- several selections
- selections in reverse order
- overlapping selections
- empty cursor plus one non-empty selection
- entire document selected
- no selection
- Unicode SQL text
- CRLF files
- LF files
- very large SQL files

Overlapping selections may deserve explicit handling before publishing.

# Testing Checklist

Before public release, test at minimum:

## Windows

- formatter found on PATH
- formatter missing
- no terminal popup
- full-document formatting
- selection formatting
- multiple selections
- formatting failure
- edit document while formatter runs
- SQLite
- PostgreSQL or another dialect

## macOS

- formatter found when Sublime is launched from Finder
- formatter found when launched from terminal
- full-document formatting
- selection formatting

macOS GUI environment/PATH behavior may differ from terminal behavior.

## Linux

- formatter found on PATH
- full-document formatting
- selection formatting
- multiple desktop environments if possible

# Automated Tests

No automated tests currently exist.

Possible test areas:

- config generation
- executable path resolution
- dialect mapping
- handling formatter success/failure
- selection-region bookkeeping

Direct testing of Sublime APIs is less straightforward than testing pure helper functions.

A useful refactor would move non-Sublime logic into normal Python functions that can be unit-tested separately.

# Package Control Preparation

Before submitting to Package Control:

1. Choose a final package name.
2. Search Package Control for similar packages.
3. Make sure the repository contains only this Sublime package.
4. Make sure the repository root is the package root.
5. Add a license.
6. Remove development junk and generated files.
7. Verify installation from a clean Sublime profile.
8. Verify Windows/macOS/Linux behavior where possible.
9. Create a semantic-version release tag.
10. Follow the current Package Control submission instructions.
11. Submit the repository to the default Package Control channel.
12. Respond to review feedback.
13. After acceptance, verify installation through Package Control.

Always re-read the current Package Control submission documentation before actually publishing because packaging rules may change.

# Versioning

Use semantic versions.

Suggested first release:

```text
1.0.0
```

Before reaching that point, GitHub development tags/releases could use:

```text
0.1.0
0.2.0
0.3.0
```

Possible interpretation:

```text
0.1.0
personal working version

0.2.0
settings and dialect selection

0.3.0
cross-platform cleanup and better errors

1.0.0
stable Package Control release
```

# Suggested Git Ignore

`.gitignore`:

```gitignore
__pycache__/
*.pyc
*.pyo
.DS_Store
Thumbs.db
```

Do not commit Sublime/Package Control generated package metadata.

# License

MIT would be a reasonable default for a tiny permissive open-source editor integration.

Before publishing:

- add the actual `LICENSE` file
- include the correct copyright holder/year
- verify compatibility with anything directly bundled into the repository

The current design invokes `sql-formatter` externally rather than copying its source into this repository.

That keeps the projects clearly separate.

# Naming Ideas

Potential package/repository names:

```text
SQLPretty
SimpleSQLFormatter
SQLFormatterBridge
PrettySQL
SQLFormatCommand
```

Avoid names that imply this repository contains or owns the upstream `sql-formatter` implementation.

Also avoid putting `Sublime` in the actual Package Control package name unless there is a compelling reason.

# GitHub Setup

Basic initial repository process:

```bash
git init
git add .
git commit -m "Initial SQL formatter plugin"
git branch -M main
git remote add origin <repository>
git push -u origin main
```

A possible first development commit history:

```text
Initial SQL formatter plugin
Add Command Palette integration
Run formatter asynchronously
Uppercase SQL keywords
Suppress formatter console on Windows
Add README and development notes
```

There is no need to manufacture this history retroactively; a single initial commit is also perfectly fine.

# Suggested Pre-Publication Roadmap

## Phase 1 — Save Current Working Version

- Commit current plugin.
- Commit Command Palette entry.
- Add README.
- Add DEVELOPMENT.md.
- Add LICENSE.
- Stop here if this is only a personal project.

## Phase 2 — Polish

- Add Sublime settings.
- Add configurable executable path.
- Add configurable SQL dialect.
- Improve error messages.
- Test other operating systems.
- Handle edge cases.

## Phase 3 — Release

- Search existing Package Control packages.
- Pick final project name.
- Clean repository.
- Tag a release.
- Follow current Package Control submission procedure.
- Submit package.

# Current Priority List

If development resumes later, a reasonable order is:

```text
1. Save current working code to GitHub
2. Add settings file
3. Add configurable formatter path
4. Add configurable SQL dialect
5. Test macOS/Linux
6. Improve errors
7. Decide whether performance is acceptable
8. Consider Package Control publication
```

# Things Not Worth Solving Yet

Avoid overengineering the first version.

Probably do not spend time yet on:

- bundling Node.js
- maintaining binaries for every platform
- persistent formatter daemons
- full SQL linting
- automatic formatter installation
- complicated syntax detection
- format-on-save
- GUI configuration panels

The current small plugin already solves the original problem:

```text
Command Palette
→ format SQL
→ replace text
```

Keep that working before adding complexity.
