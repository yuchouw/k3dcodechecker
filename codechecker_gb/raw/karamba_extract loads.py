# --- extract forces & moments per loadcase:  lc[element[position]] -------------
#   forces & moments separated as Vecto3  →  ready for GB50017 member checks
#   n_pts = 3 (beam start, mid, end) by default; adjust for more refinement
# --------------------------------------------------------------------------------
import Karamba.Models
import Karamba.Loads
import Karamba.Results
from System.Collections.Generic import List
from System import String

model = Model_in.Clone()
nPts = 10  # positions per beam: start, mid, end

# --- collect element ids & load combination names --------------------------------
elemIds = List[String]([el.id for el in model.Elements()])
combNames = ['ULS']
success, lcs = model.lcActivation.TryGetLoadCaseCombination(combNames[0])


print(f"Elements: {len(elemIds)}")
print(f"Combinations: {len(combNames)}  {combNames}\n")


# --- extract:  result[lcName][elemIdx][posIdx] = (force, moment) -----------------
#   BeamForces.solve() signature:
#     forces, moments, govLC, govLCInd, eInds = BeamForces.solve(
#         model, elemIds, lcName, nPoints, maxGovResults
#     )
#   forces[i][j][k]  →  element i, position j, state k  (k=0 for single-LC query)
# --------------------------------------------------------------------------------
results = {}  # dict: lcName → list_of_elements → list_of_positions → {f, m}

for lc in lcs.LoadCases:
    lcName = lc.Name
    forces, moments, govLC, govLCInd, eInds = Karamba.Results.BeamForces.solve(
        model, elemIds, lcName, 0.5, nPts
    )

    print(forces[0][0][0])
    lcResults = []  # per-element list for this LC

    for ei in range(len(forces)):
        posList = []
        for pi in range(len(forces[ei])):
            fv = forces[ei][pi][0]   # Vector3: (X,Y,Z) = global forces at node
            mv = moments[ei][pi][0]  # Vector3: (X,Y,Z) = global moments at node
            posList.append({"f": fv, "m": mv})
        lcResults.append(posList)

    results[lcName] = lcResults
    print(f"  {lcName}: {len(lcResults)} elements × {nPts} pts  →  done")