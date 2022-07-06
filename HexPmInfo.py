import sublime
import sublime_plugin
import sys
import re
import urllib
import os
import tempfile
import json
import urllib.request
import urllib.parse
# from urllib.request import urlopen
import webbrowser
import subprocess
from pathlib import Path

# from .format_text import format_text

# Clear module cache to force reloading all modules of this package.
# See https://github.com/emmetio/sublime-text-plugin/issues/35
prefix = __package__ + "."  # don't clear the base package
for module_name in [
    module_name
    for module_name in sys.modules
    if module_name.startswith(prefix) and module_name != __name__
]:
    del sys.modules[module_name]


def settings(key):
    return sublime.load_settings("HexPmInfo.sublime-settings").get(key)


def debug(*args):
    if settings("debug"):
        print("[hex.pm]", *args)


def cache_path(hex_name):
    return os.path.join(tempfile.gettempdir(), hex_name + ".hexpm-info")


def has_cache(hex_name):
    return os.path.isfile(cache_path(hex_name))


def read_cache(hex_name):
    with open(cache_path(hex_name)) as file:
        return json.load(file)


def write_cache(hex_name, info):
    with open(cache_path(hex_name), "w") as file:
        file.writelines(json.dumps(info))


def fetch_hex_info(hex_name):
    url = "https://hex.pm/api/packages/%s" % (hex_name)
    res = urllib.request.urlopen(url)
    return json.loads(res.read().decode('utf-8'))


def get_hex_info(hex_name):
    if has_cache(hex_name):
        info = read_cache(hex_name)
    else:
        info = fetch_hex_info(hex_name)

        if info:
            write_cache(hex_name, info)

    return info


class HexPmBumpCommand(sublime_plugin.TextCommand):
    def run(self, edit, row=None, version=None):
        # view = sublime.active_window().active_view()
        view = self.view
        point = view.text_point(row, 0)
        current_line = view.substr(view.line(point))
        current_line = re.sub(r"\r?\n", " ", current_line)
        semverRegex = r"(0|(?:[1-9]\d*))(?:\.(0|(?:[1-9]\d*))(?:\.(0|(?:[1-9]\d*)))?(?:\-([\w][\w\.\-_]*))?)+"
        new_line = re.sub(semverRegex, version, current_line)
        view.replace(edit, view.line(point), new_line)


class HexPmShowInfoCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view

        if not view.file_name().endswith("mix.exs"):
            return

        point = view.sel()[0].begin()
        row, col = view.rowcol(point)
        line_text = view.substr(view.line(point)).strip()
        regex = r"{:([a-z_0-9]+),\s?\"(>|>=|,|<=|==|~>|)?\s?(.+)\""
        matches = re.match(regex, line_text)

        if not matches:
            debug("No matches, skip.")
            return

        hex_name = matches.group(1)
        debug("Getting info for", hex_name)
        debug("Cache path is", cache_path(hex_name))

        hex_info = get_hex_info(hex_name)

        if not hex_info:
            debug("Unable to fetch hex info")
            return

        html = '''
            <body class="popup">
                <style>
                    .info {{
                        border-width: 0;
                        background-color: color(var(--bluish) alpha(0.25));
                        color: var(--foreground);
                        padding: 0.5rem;
                    }}
                    .popup {{
                        margin: 0.5rem;
                        font-family: system;
                    }}
                    .actions {{
                        font-family: system;
                        border-width: 0;
                        background-color: color(var(--foreground) alpha(0.1));
                        color: var(--foreground);
                        padding: 0.5rem;
                    }}
                    p {{
                        margin: 0;
                        margin-bottom: 0.7rem;
                    }}
                </style>
                <p>{description}</p>
                <hr>
                <p><strong>Latest version:</strong> {latest_version}</p>
                <p><strong>Latest stable version:</strong> {latest_stable_version}</p>
                <div class="actions">
                    <a href="bump:{hex_name}:{row}">Bump version</a> |
                    <a href="docs:{hex_name}:{row}">Docs</a>
                </p>
            </body>
        '''.format(
            hex_name=hex_name,
            row=row,
            description=hex_info["meta"]["description"],
            latest_version=hex_info["latest_version"],
            latest_stable_version=hex_info["latest_stable_version"]
        )

        view.show_popup(html,
                        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                        location=point,
                        on_navigate=self.handle_navigate,
                        max_width=700,
                        max_height=500)

    def handle_navigate(self, path):
        action, hex_name, row = path.split(":")
        hex_info = get_hex_info(hex_name)
        row = int(row)

        point = sublime.active_window().active_view().text_point(row, 0)

        debug(hex_info)

        if action == "docs":
            webbrowser.open_new_tab(hex_info["docs_html_url"])
        elif action == "bump":
            sublime.active_window().active_view().run_command(
                "hex_pm_bump", {"row": row, "version": hex_info["latest_stable_version"]})
