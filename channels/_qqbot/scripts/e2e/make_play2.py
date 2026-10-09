"""A second judge for gomoku, for any board of 7 or more crossings and any state variables:
python specs/make_play2.py PIECE OUT.json COLVAR ROWVAR LABEL VW VH N [CELLS]

It plays: four black blocked by white (no win), a tap on a taken crossing (nothing changes), the fifth black stone
(black wins, the status says so), a second, a tap that restarts (empty board), then white five on a rising
diagonal (white wins). It reads the pieces, the status text and every global, so it needs no state names.
make_play.py, the first judge, also expects the restart to wait until 0.5 s after the win.
"""
import json
import sys

piece, out, col_var, row_var, label = sys.argv[1:6]
vw, vh, n = int(sys.argv[6]), int(sys.argv[7]), int(sys.argv[8])
cells = sys.argv[9] if len(sys.argv) > 9 else "Cell"       # the tap targets' object
r = n // 2


def cell(c, row):
    return {"tap": {"js": f"runtime.objects.{cells}.getAllInstances().find(i => i.instVars.{col_var} === {c} && "
                          f"i.instVars.{row_var} === {row})"}, "note": f"cell {c},{row}"}


def look(note):
    return {"js": f"[runtime.objects.{piece}.getAllInstances().length, runtime.objects.{label}.getFirstInstance().text, "
                  f"JSON.stringify(runtime.globalVars)]", "note": note}


steps = [{"wait": 0.5}]


def play(moves):
    for c, row in moves:
        steps.extend([cell(c, row), {"wait": 0.25}])


play([(1, r), (1, r + 1), (2, r), (2, r + 1), (3, r), (3, r + 1), (4, r), (5, r)])
steps.append(look("blocked"))                      # 8 pieces, no win
play([(4, r)])
steps.append(look("taken"))                        # still 8
play([(0, r)])
steps += [{"wait": 0.3}, look("black-wins")]       # 9 pieces, black wins
# a tap on a crossing, then one below the board: a game may restart on either
steps += [{"wait": 1.2}, cell(n - 1, 0), {"wait": 0.8}, {"tap": {"x": vw / 2, "y": vh * 0.97}}, {"wait": 0.8},
          look("restarted")]   # 0 pieces
play([(0, n - 1), (4, 0), (1, n - 1), (3, 1), (3, n - 1), (2, 2), (5, n - 1), (1, 3), (6, n - 1), (0, 4)])
steps += [{"wait": 0.3}, look("white-wins")]       # 10 pieces, white wins
json.dump({"viewport": [vw, vh], "touch": True, "steps": steps}, open(out, "w", encoding="utf-8"), indent=1)
