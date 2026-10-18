# Regenerates every number, table and figure of the draft from results/ and rl/ (no simulation is run).
# Needs the RL extras (requirements-rl.txt) because paper/analysis.py imports the comparison script's statistics.
#   make -C paper all          # numbers -> tables -> figures
#   make -C paper pdf          # also builds the manuscript when a LaTeX toolchain is installed (not available on the drafting machine)
PYTHON ?= python

.PHONY: all numbers tables figures pdf clean
all: numbers tables figures

numbers:
	$(PYTHON) make_numbers.py

tables: numbers
	$(PYTHON) tables.py

figures: numbers
	$(PYTHON) figures.py

pdf: all
	cd manuscript && latexmk -pdf main.tex

clean:
	rm -f generated/*.tex generated/*.pdf generated/*.png generated/*.json
