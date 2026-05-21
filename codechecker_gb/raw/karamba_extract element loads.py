# --- extract forces & moments per loadcase:  lc[element[position]] -------------
#   forces & moments separated as Vecto3  →  ready for GB50017 member checks
#   BeamForces.solve(model, elemIds, lcName, maxDist, nIntervals)
#     → out forces, moments, govLC, govLCInd, eInds
# --------------------------------------------------------------------------------
import Karamba.Models
import Karamba.Loads
import Karamba.Results
from System.Collections.Generic import List
from System import String

model = Model_in.Clone()
maxDist = 10000.0   # max distance between result points (large → uniform spacing)
nIntervals = 10     # min intervals along beam → 11 positions

# --- collect element ids --------------------------------------------------------
elemIds = List[String]([el.id for el in model.Elements()])
combNames = ['ULS']  # combination group names from Load-Case-Combinator

# --- expand combination groups → sub-LC selector strings (ULS → ULS/0, ULS/1…) ---
subLcNames = []

for cn in combNames:
    success, lcc = model.lcActivation.TryGetLoadCaseCombination(cn)
    if success and lcc is not None:
      subLCs = lcc.LoadCases
      for subLC in subLCs:
          subLcNames.append(f"{subLC.Name}")
          # format factors as "1.35*G + 1.5*Q"
          parts = []
          facs = subLC.factors
          for key in facs.Keys:
              val = facs[key]
              if abs(val) < 1e-12:
                  continue
              term = f"{val:.2f}*{key}" if abs(abs(val) - 1.0) > 1e-6 else (f"-{key}" if val < 0 else key)
              parts.append(term)
          print(f"  = {' + '.join(parts)}")

print(f"\nElements: {len(elemIds)}")
print(f"Sub-LCs to extract: {subLcNames}\n")


# --- extract:  result[lcName][elemIdx][posIdx] = {"f": Vector3, "m": Vector3} ---
results = {}

for lcName in subLcNames:
    forces, moments, govLC, govLCInd, eInds = Karamba.Results.BeamForces.solve(
        model, elemIds, lcName, maxDist, nIntervals
    )

    lcResults = []
    for ei in range(len(forces)):
        posList = []
        for pi in range(len(forces[ei])):
            fv = forces[ei][pi][0]   # single state (no envelope for one sub-LC)
            mv = moments[ei][pi][0]
            posList.append({"f": fv, "m": mv})
        lcResults.append(posList)

    results[lcName] = lcResults
    nPos = len(forces[0]) if len(forces) > 0 else 0
    print(f"  {lcName}: {len(lcResults)} elem × {nPos} pos")


# --- helpers for GB50017 member checks ------------------------------------------
def N(lc, ei, pi):   return results[lc][ei][pi]["f"].X   # axial (kN)
def Vy(lc, ei, pi):  return results[lc][ei][pi]["f"].Y
def Vz(lc, ei, pi):  return results[lc][ei][pi]["f"].Z
def Mx(lc, ei, pi):  return results[lc][ei][pi]["m"].X   # torsion (kNm)
def My(lc, ei, pi):  return results[lc][ei][pi]["m"].Y   # strong-axis bending
def Mz(lc, ei, pi):  return results[lc][ei][pi]["m"].Z   # weak-axis bending


# --- print sample ---------------------------------------------------------------
if subLcNames:
    lc0 = subLcNames[0]
    nPos = len(results[lc0][0])
    print(f"\n--- Sample: {lc0}, element[0] '{elemIds[0]}' ---")
    for pi in range(nPos):
        fv = results[lc0][0][pi]["f"]
        mv = results[lc0][0][pi]["m"]
        print(f"  pos[{pi:2d}]  "
              f"N={fv.X:10.3f}  Vy={fv.Y:10.3f}  Vz={fv.Z:10.3f}  "
              f"Mx={mv.X:10.3f}  My={mv.Y:10.3f}  Mz={mv.Z:10.3f}")

print("\nDone — results[lc][elem][pos]['f'|'m']")
