# SPDX-License-Identifier: MIT
# Copyright (c) 2026 KB2UKA
# Copyright (c) 2026 Kazuhide Takahashi
# J715 (AID38) variant of audio/j713/owner-fir/src; the math is unchanged.
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess

FRAMES = 73728
assert hashlib.sha256(Path('/System/Library/Components/AudioDSP.component/Contents/MacOS/AudioDSP').read_bytes()).hexdigest() == json.loads(Path('owner-inputs.json').read_text())['AudioDSP']
# The presets depend on the speaker ID; the generator passes the pinned hashes.
for name, sha in json.loads(Path('owner-inputs.json').read_text())['presets'].items():
    assert hashlib.sha256(Path('decoded',name+'.aupreset').read_bytes()).hexdigest() == sha
rows=[]
def run(name, preset, lane=0, amplitude='0.0001', source='impulse', subset='none'):
    output=Path('output',name+'.f32')
    args=['./measure-memory-j715','decoded/'+preset+'.aupreset',str(output),str(lane),amplitude,'0',source,subset]
    proc=subprocess.run(args,capture_output=True,text=True,timeout=30)
    Path('output',name+'.stdout').write_text(proc.stdout)
    Path('output',name+'.stderr').write_text(proc.stderr)
    if proc.returncode: raise RuntimeError((name,proc.returncode,proc.stderr))
    row=json.loads(proc.stdout)
    row.update(name=name,argv=args,file=output.name,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),bytes=output.stat().st_size)
    rows.append(row)
    print(json.dumps(row),flush=True)
    return output
SUBSETS = {'hp70': ('Tone1', 'keep:0:4:70'), 'hpq50': ('Tone2', 'keep:7:14:50')}
for label,(preset,subset) in SUBSETS.items():
    for amp in ['0.0001','0.0002']:
        for lane in [0,1]: run(label+'-amp'+amp+'-lane'+str(lane),preset,lane,amp,subset=subset)
for amplitude in [0.0001,0.125]:
    rng=random.Random(715)
    data=[]
    for lane in range(4):
        data.extend([0.]*4096+[amplitude*(2*rng.random()-1) for _ in range(8192)]+[0.]*(FRAMES-12288))
    path=Path('output','noise-'+str(amplitude)+'.f32')
    path.write_bytes(struct.pack('<'+'f'*len(data),*data))
    run('anal-noise-'+str(amplitude),'analytical',source=str(path))
source='output/noise-0.125.f32'
hp70=run('chain-hp70','Tone1',source=source,subset=SUBSETS['hp70'][1])
hpq50=run('chain-hpq50','Tone2',source=str(hp70),subset=SUBSETS['hpq50'][1])
data=list(struct.unpack('<'+'f'*(4*FRAMES),hpq50.read_bytes()))
data[2*FRAMES:3*FRAMES]=data[:FRAMES]
data[3*FRAMES:]=data[FRAMES:2*FRAMES]
split=Path('output/chain-split.f32')
split.write_bytes(struct.pack('<'+'f'*len(data),*data))
run('chain-anal','analytical',source=str(split))
Path('output/memory-runs.json').write_text(json.dumps(rows,indent=2)+'\n')
Path('output/files.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(Path('output').glob('*.f32'))))
