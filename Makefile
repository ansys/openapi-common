# Simple makefile to simplify repetitive build env management tasks under posix

SRC_DIRS ?= ./src
TEST_DIRS ?= ./tests
CODESPELL_SKIP ?= "*.pyc,*.xml,*.txt,*.gif,*.png,*.jpg,*.js,*.html,*.doctree,*.ttf,*.woff,*.woff2,*.eot,*.mp4,*.inv,*.pickle,*.ipynb,flycheck*,./.git/*,./.hypothesis/*,*.yml,./docs/build/*,./docs/images/*,./dist/*,*~,.hypothesis*,./docs/source/examples/*,*cover,*.dat,*.mac,\#*,PKG-INFO,*.mypy_cache/*,*.xml,*.aedt,*.svg"
CODESPELL_IGNORE ?= "ignore_words.txt"

all: doctest

doctest: codespell black

codespell:
	@echo "Running codespell"
	@codespell $(SRC_DIRS) -S $(CODESPELL_SKIP) # -I $(CODESPELL_IGNORE)

black:
	@echo "Running black"
	@black $(SRC_DIRS) $(TEST_DIRS)