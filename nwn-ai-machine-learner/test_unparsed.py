"""Show samples of unparsed CHAT lines to find missed patterns."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser.event_parser import parse_line

log_file = r"D:\nwn\logs\nwclientLog2.txt"
buckets = collections.Counter()
samples = {}

with open(log_file, encoding='cp1252', errors='replace') as f:
    for line in f:
        line = line.rstrip('\r\n')
        if '[CHAT WINDOW TEXT]' not in line:
            continue
        ev = parse_line(line)
        if ev is None:
            # strip prefix
            content = line.split('] ', 2)[-1].strip() if '] ' in line else line
            # bucket by first word(s)
            key = ' '.join(content.split()[:4])
            buckets[key] += 1
            if key not in samples:
                samples[key] = content

print("Top unparsed line patterns:")
for key, count in buckets.most_common(30):
    print(f"  [{count:4d}x] {samples[key][:90]}")
