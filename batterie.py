#!/usr/bin/env python3
"""Batterie : l'état réel de la batterie de ton MacBook, en clair.

Usage :
  python3 batterie.py           santé, cycles, charge, consommation, chargeur, évolution
  python3 batterie.py --direct  consommation en temps réel (Ctrl+C pour quitter)
  python3 batterie.py --json    données brutes, pour tes scripts
"""

import argparse
import csv
import json
import os
import plistlib
import subprocess
import sys
import time

HISTORY = os.path.expanduser('~/Library/Application Support/Batterie/historique.csv')
NA = 65535  # valeur utilisée par macOS pour « inconnu »

TTY = sys.stdout.isatty()
def color(code, s): return '\033[%sm%s\033[0m' % (code, s) if TTY else s
bold = lambda s: color('1', s)
dim = lambda s: color('2', s)
GREEN, YELLOW, RED = '32', '33', '31'


def num(x, digits=1):
    return ('%.*f' % (digits, x)).replace('.', ',')


def bar(fraction, width=20, code=GREEN):
    fraction = max(0.0, min(1.0, fraction))
    full = round(fraction * width)
    return color(code, '█' * full) + dim('░' * (width - full))


def read_battery():
    out = subprocess.run(['ioreg', '-rn', 'AppleSmartBattery', '-a'], capture_output=True).stdout
    if not out.strip():
        return None
    raw = plistlib.loads(out)
    if not raw:
        return None
    d = raw[0]
    bd = d.get('BatteryData', {})
    pick = lambda *keys: next((src[k] for k in keys for src in (d, bd) if isinstance(src.get(k), int)), None)

    design = pick('DesignCapacity')
    full = pick('NominalChargeCapacity', 'AppleRawMaxCapacity', 'FullChargeCapacity')
    temp = pick('Temperature', 'VirtualTemperature')
    volts = (d.get('Voltage') or 0) / 1000
    amps = (d.get('InstantAmperage') or d.get('Amperage') or 0)
    amps = (amps - (1 << 64) if amps >= 1 << 63 else amps) / 1000  # valeur signée stockée en non signé
    power = d.get('PowerTelemetryData', {}).get('SystemLoad')
    adapter = d.get('AdapterDetails') or {}

    plugged = bool(d.get('ExternalConnected'))
    return {
        'charge': d.get('CurrentCapacity'),
        'charging': bool(d.get('IsCharging')),
        'plugged': plugged,
        'full': bool(d.get('FullyCharged')),
        'health': round(full / design * 100, 1) if design and full else None,
        'capacity_mah': full,
        'design_mah': design,
        'cycles': d.get('CycleCount'),
        'cycles_max': d.get('DesignCycleCount9C') or 1000,
        'temperature': round(temp / 100, 1) if temp else None,
        'watts': round(power / 1000, 1) if plugged and power else round(abs(volts * amps), 1),
        'voltage': round(volts, 2),
        'adapter_watts': adapter.get('Watts') if plugged else None,
        'adapter_volts': (adapter.get('AdapterVoltage') or 0) / 1000 if plugged else None,
        'minutes_left': d.get('AvgTimeToEmpty') if not plugged and d.get('AvgTimeToEmpty', NA) < NA else None,
        'minutes_to_full': d.get('AvgTimeToFull') if d.get('IsCharging') and d.get('AvgTimeToFull', NA) < NA else None,
    }


def duration(minutes):
    return '%d h %02d' % divmod(minutes, 60) if minutes >= 60 else '%d min' % minutes


def record(b):
    """Garde au plus une mesure par jour pour suivre l'usure dans le temps."""
    if b['health'] is None:
        return []
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    rows = []
    if os.path.exists(HISTORY):
        with open(HISTORY, newline='') as f:
            rows = list(csv.reader(f))[1:]
    today = time.strftime('%Y-%m-%d')
    if not rows or rows[-1][0] != today:
        rows.append([today, str(b['health']), str(b['cycles'])])
        with open(HISTORY, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'sante', 'cycles'])
            w.writerows(rows)
    return rows


def report(b, rows):
    label = lambda s: '  ' + s.ljust(14)
    print()
    print(bold('  Batterie'))
    print()

    # Charge
    if b['charging']:
        state = 'En charge' + (' · pleine dans ' + duration(b['minutes_to_full']) if b['minutes_to_full'] else '')
    elif b['plugged'] and (b['full'] or b['charge'] == 100):
        state = 'Branché · chargée'
    elif b['plugged']:
        state = 'Branché · charge en pause (recharge optimisée)'
    else:
        state = 'Sur batterie' + (' · environ ' + duration(b['minutes_left']) + ' restantes' if b['minutes_left'] else '')
    c = b['charge'] or 0
    print(label('Charge') + bar(c / 100, code=GREEN if c > 20 else RED) + '  %3d %%  ' % c + dim(state))

    # Santé
    h = b['health']
    if h is not None:
        verdict, code = (('Excellente', GREEN) if h >= 90 else ('Bonne', GREEN) if h >= 80
                         else ('Usée', YELLOW) if h >= 70 else ('À remplacer', RED))
        print(label('Santé') + bar(h / 100, code=code) + '  %s %%  ' % num(h) + color(code, verdict)
              + dim('  (%d sur %d mAh d\'origine)' % (b['capacity_mah'], b['design_mah'])))

    # Cycles
    cy, cmax = b['cycles'], b['cycles_max']
    if cy is not None:
        f = cy / cmax
        print(label('Cycles') + bar(f, code=GREEN if f < .7 else YELLOW if f < .9 else RED)
              + '  %d / %d  ' % (cy, cmax) + dim('%d %% de la durée de vie prévue par Apple' % round(f * 100)))

    if b['temperature'] is not None:
        t = b['temperature']
        print(label('Température') + '%s °C  ' % num(t) + (color(RED, 'Chaude') if t > 40 else dim('Normale')))
    if b['watts']:
        print(label('Consommation') + '%s W' % num(b['watts']) + dim('  (tout le Mac, en ce moment)'))
    if b['adapter_watts']:
        print(label('Chargeur') + '%d W' % b['adapter_watts'] + dim('  (%s V)' % num(b['adapter_volts'], 0)))

    # Évolution
    if len(rows) >= 2:
        first = rows[0]
        delta = h - float(first[1])
        days = (time.mktime(time.strptime(rows[-1][0], '%Y-%m-%d')) - time.mktime(time.strptime(first[0], '%Y-%m-%d'))) / 86400
        print(label('Évolution') + '%s%s points' % ('+' if delta >= 0 else '', num(delta))
              + dim(' de santé et %d cycles en %d jours (depuis le %s)' % (int(rows[-1][2]) - int(first[2]), days, first[0])))
    else:
        print(label('Évolution') + dim('relance Batterie dans quelques jours pour suivre l\'usure'))

    # Conseils
    tips = []
    if h is not None and h < 80:
        tips.append("Santé sous 80 % : Apple considère qu'une révision de la batterie est recommandée.")
    if cy is not None and cy >= cmax * 0.9:
        tips.append('La batterie approche du nombre de cycles prévu : son autonomie va continuer de baisser.')
    if b['temperature'] and b['temperature'] > 40:
        tips.append('La chaleur use la batterie : évite de charger le Mac au soleil ou sur un lit.')
    if b['adapter_watts'] and b['adapter_watts'] < 30 and b['charging']:
        tips.append('Chargeur peu puissant (%d W) : la charge sera lente.' % b['adapter_watts'])
    if not tips:
        tips.append('Tout va bien. Garde la « recharge optimisée » activée pour ménager la batterie.')
    print()
    for t in tips:
        print('  ' + dim('→ ') + t)
    print()


def live():
    try:
        while True:
            b = read_battery()
            line = '  %s  %s W  · charge %d %%  · %s' % (
                time.strftime('%H:%M:%S'), num(b['watts']).rjust(5), b['charge'],
                'en charge' if b['charging'] else 'branché' if b['plugged'] else 'sur batterie')
            print('\r' + line + ' ' * 6, end='', flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        print()


def main():
    ap = argparse.ArgumentParser(description="Affiche l'état réel de la batterie du Mac.")
    ap.add_argument('--direct', action='store_true', help='consommation en temps réel')
    ap.add_argument('--json', action='store_true', help='sortie JSON')
    args = ap.parse_args()

    b = read_battery()
    if b is None:
        sys.exit("Ce Mac n'a pas de batterie.")
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=2))
    elif args.direct:
        live()
    else:
        report(b, record(b))


if __name__ == '__main__':
    main()
