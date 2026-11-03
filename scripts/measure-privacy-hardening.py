#!/usr/bin/env python3
"""Tiny local CPU/byte measurements; no requests, sockets, databases or soak loops."""
import json
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"apps/api"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","haven.settings")
import django
django.setup()
from core.privacy import routing_groups
ids=[uuid.UUID(int=i) for i in range(1,1001)]
results={}
for name,derive in (("raw_group",lambda uid:("user."+str(uid),)),("hmac_group",routing_groups)):
    samples=[]
    for _ in range(5):
        start=time.perf_counter_ns()
        for uid in ids: derive(uid)
        samples.append((time.perf_counter_ns()-start)/1e6)
    results[name]={"batch_size":1000,"batch_ms":samples,"median_batch_ms":statistics.median(samples)}
media=[]
for size in (0,1,4095,4096,65536,65537,1048576,1048577,25*1024*1024):
    step=4096 if size<=65536 else 16384 if size<=1048576 else 65536
    padded=max(4096,((size+step-1)//step)*step)
    old_chunks=max(1,(size+524287)//524288)
    new_chunks=max(1,(padded+524287)//524288)
    media.append({"plaintext":size,"padded":padded,"legacy_wire":size+16*old_chunks,"v2_wire":padded+16*new_chunks,"extra_bytes":padded-size,"chunks":new_chunks})
print(json.dumps({"routing_cpu":results,"attachment_bytes":media,"scope":"5 batches of 1000 local derivations, byte arithmetic cross-checked by actual browser implementation; not TLS overhead, latency SLA or throughput qualification"},indent=2))
