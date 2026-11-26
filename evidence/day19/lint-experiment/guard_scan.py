"""Candidate lint: GDScript guard branches that return a value without push_error/push_warning/assert.
Reads one file's text on stdin; prints line numbers of silent guard returns."""
import re,sys
LOG=re.compile(r'push_error|push_warning|printerr|assert\(|_report|_fail|error\(')
lines=sys.stdin.read().split('\n')
hits=[]
for i,l in enumerate(lines):
    m=re.match(r'^(\s*)(if|elif)\b.*:\s*(return\b.*)?$',l)
    if not m: continue
    ind=len(m.group(1))
    if m.group(3):  # one-line guard
        if m.group(3).strip()!='return': hits.append(i+1)
        continue
    body=[]
    for j in range(i+1,min(i+8,len(lines))):
        s=lines[j]
        if s.strip()=='' : continue
        if len(s)-len(s.lstrip())<=ind: break
        body.append(s)
    if body and re.match(r'^\s*return\b\s*\S',body[-1]) and len(body)<=3 and not any(LOG.search(b) for b in body):
        hits.append(i+1)
print(' '.join(map(str,hits)))
