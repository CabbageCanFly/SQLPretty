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
