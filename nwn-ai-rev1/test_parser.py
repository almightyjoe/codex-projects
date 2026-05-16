"""Quick parser smoke test against real NWN logs."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser.event_parser import parse_line

log_file = r"D:\nwn\logs\nwclientLog2.txt"
counts = collections.Counter()
parsed = 0
total  = 0
samples = collections.defaultdict(list)

with open(log_file, encoding='cp1252', errors='replace') as f:
    for line in f:
        line = line.rstrip('\r\n')
        if '[CHAT WINDOW TEXT]' not in line:
            continue
        total += 1
        ev = parse_line(line)
        if ev:
            parsed += 1
            counts[ev['type']] += 1
            if len(samples[ev['type']]) < 2:
                samples[ev['type']].append(ev)

print(f"\nParsed {parsed}/{total} CHAT lines ({100*parsed//total if total else 0}%)")
print("\nEvent counts:")
for k, v in counts.most_common():
    print(f"  {k:15s} {v}")
print("\nSample events:")
for t, evs in list(samples.items())[:5]:
    for ev in evs:
        print(f"  [{t}] {ev}")
