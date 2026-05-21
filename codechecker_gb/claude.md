0. you are a helper to build codecheker for Karamba3d based on GB50017
1. 
2. read karamba API doc first, browsing net is ok:
https://www.karamba3d.com/help/3-1-4/html/b2fe4d67-e7e2-4f96-bc84-ecd423bde1a7.htm
3. develop environment in rhino, cannot test the code directly in python. code will be tested by user in rhino grasshopper python component.
4. key purpose is to understand each function of Karamba3d, the data structure of the results karamba3d returns.
5. during the testing stage, write minimum but understandable scripts
6. everytime writing code ask me if start a new file first
7. I may adjust the code everytime, reload the scripts everytime to understand the changes
8. tested scripts are saved, in the raw folder, read and understand the scripts before started.

## Load-Case-Combinator reference

- Text-based rules: `Name = expression`, one per line. Same name on multiple lines → OR-relation.
- Operators (low→high priority): `|` (OR alternatives), `+`/`-` (AND add/subtract), `&` (leading-factor permutation).
- Factors: fixed `1.35*G`, variable `(1.5|0)*Q` where (upper|lower).
- `&` generates all permutations where one term leads (upper factor) and others accompany (lower factor):
  `(1.5|0)*Q & (1.5|0)*W` → `1.5*Q+0*W | 0*Q+1.5*W`
- Regex: `wind*` matches all load-cases starting with "wind".
- Result selector `ULS/0`, `ULS/1` = zero-based index into the expanded sub-combinations of "ULS".