import re, json, collections

src = open("Quest.java", encoding="utf-8").read()

# Match enum constant lines only:  NAME( <args...>, "Display" ),
# - constant name: uppercase identifier at line start (after whitespace) directly before '('
# - display name: the final double-quoted string literal argument (allows escaped chars)
pat = re.compile(
    r'^\s*([A-Z][A-Z0-9_]*)\s*\(\s*[^,()]+,\s*"((?:[^"\\]|\\.)*)"\s*\)\s*,?\s*$',
    re.M,
)

mapping = collections.OrderedDict()
constants = []
dup_display = []
for m in pat.finditer(src):
    const = m.group(1)
    disp = m.group(2).encode().decode("unicode_escape")  # unescape any \" \\ etc.
    constants.append(const)
    if disp in mapping and mapping[disp] != const:
        dup_display.append((disp, mapping[disp], const))
    mapping[disp] = const

# Cross-check: every line that *looks* like an enum constant should be captured.
loose = re.findall(r'^\s*([A-Z][A-Z0-9_]*)\s*\(', src, re.M)
missed = [c for c in loose if c not in constants]

print("Parsed constants   :", len(constants))
print("Unique displaynames:", len(mapping))
print("Duplicate displays :", dup_display)
print("Loose const-lines  :", len(loose))
print("Missed lines       :", missed)

json.dump(mapping, open("quest_names.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print("WROTE", len(mapping), "entries -> quest_names.json")
