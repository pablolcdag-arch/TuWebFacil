import pyflakes.api
import pyflakes.reporter
import sys

with open("bot_engine.py", "r") as f:
    code = f.read()

reporter = pyflakes.reporter.Reporter(sys.stdout, sys.stderr)
pyflakes.api.check(code, "bot_engine.py", reporter)
