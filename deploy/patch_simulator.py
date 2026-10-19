#!/usr/bin/env python3
"""Adaptação de cadência do commit fixado; falha em fonte inesperada."""
import hashlib
from pathlib import Path
import sys
ORIGINAL = '5543734484510b82b73cd1ee911492db86082ca1adf041163538954e14528e1d'
UPDATED = '41dc281eb88429af5aa7ec8855bd976924fa7f27d5953444937039b4ff488f07'
CHANGES = [(290, 292, ['def messages(cabine, dt, elapsed, run_id, executor, config_id, temperatura_intervalo=30):\n', "    kinds = ['corrente', 'temperatura'] if elapsed % temperatura_intervalo == 0 else ['corrente']\n"]), (298, 299, ["        interval = 1 if kind == 'corrente' else temperatura_intervalo\n"]), (459, 459, ["    p.add_argument('--temperatura-intervalo', type=int, choices=range(1,61), default=30, help='Cadência da temperatura em segundos (1 no laboratório integrado).')\n"]), (500, 501, ["    if args.destino == 'iot' and args.taxa_envio < args.cabines * (1 + 1 / args.temperatura_intervalo):\n"]), (518, 519, ["        'coleta_s': {'corrente': 1, 'temperatura': args.temperatura_intervalo}, 'argumentos': vars(args),\n"]), (525, 526, ['        expected = args.cabines * (args.duracao + (args.duracao + args.temperatura_intervalo - 1) // args.temperatura_intervalo)\n']), (549, 550, ['                for message in messages(cabine, dt, tick, run_id, args.executor, config_id, args.temperatura_intervalo):\n'])]

def patch(path):
    p=Path(path); data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    if digest==UPDATED:return
    if digest!=ORIGINAL:raise RuntimeError('Simulador difere do commit revisado; adaptação não aplicada.')
    lines=data.decode('utf-8').splitlines(True)
    for start,end,replacement in reversed(CHANGES):lines[start:end]=replacement
    output=''.join(lines).encode('utf-8')
    if hashlib.sha256(output).hexdigest()!=UPDATED:raise RuntimeError('Adaptação inconsistente.')
    p.write_bytes(output)

if __name__=='__main__':patch(sys.argv[1])
