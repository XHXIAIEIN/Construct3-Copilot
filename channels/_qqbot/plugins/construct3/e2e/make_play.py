"""A preview plan that plays gomoku on a built project: python plugins/construct3/e2e/make_play.py PIECE STATE OUT.json [COLVAR ROWVAR]"""
import json, sys
piece, state, out = sys.argv[1:4]
vw, vh = (int(sys.argv[7]), int(sys.argv[8])) if len(sys.argv) > 8 else (720, 1280)
col_var, row_var = (sys.argv[4], sys.argv[5]) if len(sys.argv) > 5 else ("col", "row")
label = sys.argv[6] if len(sys.argv) > 6 else "Status"
n = int(sys.argv[9]) if len(sys.argv) > 9 else 15  # crossings on a side
def cell(c, r):
    return {"tap": {"js": f"runtime.objects.Cell.getAllInstances().find(i => i.instVars.{col_var} === {c} && i.instVars.{row_var} === {r})"}, "note": f"cell {c},{r}"}
def look(note):
    return {"js": f"[runtime.globalVars.{state}, runtime.globalVars.turn, runtime.objects.{piece}.getAllInstances().length, runtime.objects.{label}.getFirstInstance().text]", "note": note}
steps = [{"wait": 0.5}]
def play(moves):
    for c, r in moves:
        steps.extend([cell(c, r), {"wait": 0.15}])
# black 3..6 on row 7, white closes the line at 7,7: no win
play([(3, 7), (3, 8), (4, 7), (4, 8), (5, 7), (5, 8), (6, 7), (7, 7)])
steps.append(look("four black and one white in a row: still playing, black to move, 8 pieces"))
play([(6, 7)])
steps.append(look("tap on a taken cell: nothing changes"))
play([(2, 7), (9, 9), (1, 7)])
steps += [look("black 1..6 on row 7 holds five: won"), {"wait": 0.8}, {"shot": "won"}, look("waiting for the restart tap"),
          cell(12, 12), {"wait": 0.5}, look("restarted: empty board, black to move")]
play([(0, n - 1), (10, 2), (1, n - 1), (9, 3), (2, n - 1), (8, 4), (3, n - 2), (7, 5), (5, n - 1), (6, 6)])
steps += [look("white wins on the rising diagonal"), {"wait": 0.7}, {"shot": "white-wins"}]
json.dump({"viewport": [vw, vh], "touch": True, "steps": steps}, open(out, "w"), indent=1)
