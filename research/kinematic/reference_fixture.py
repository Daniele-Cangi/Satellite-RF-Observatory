"""Invented GPS circular references and an independent inertial RINEX generator.

No target trajectory is generated. G08 payloads are deliberately nonnumeric.
"""
from datetime import datetime, timedelta
import math

import numpy as np
from scipy.optimize import brentq

DAY = '2026-09-10'
BASE_SECOND = 43200
TARGET = 'G08'
REFERENCES = ('G01', 'G02', 'G03', 'G04')
TAGS = np.arange(-300., 1., 30.)
STATION = np.array([6378137., 0., 0.])
CLOCK = np.array([14000., .73])
TYPES = ('C1C', 'L1C', 'D1C', 'S1C', 'C1W', 'L1W', 'D1W', 'S1W',
         'C2W', 'L2W', 'S2W', 'C5Q', 'L5Q', 'D2W')
# Mean anomaly, inertial ascending node at the local base epoch, inclination.
ORBITS = ((-.25, -.4, .95), (.35, .4, .96), (.1, -.6, .97), (-.15, .6, .94))


def independent_code(tag, index):
    """Circular inertial orbit, receiver clock tagging and scalar light-cone root."""
    speed = 299792458.0
    clock_r = CLOCK[0]+CLOCK[1]*tag
    receive = tag-clock_r/speed
    angle_r = 7.2921151467e-5*receive
    receiver = np.array([STATION[0]*math.cos(angle_r), STATION[0]*math.sin(angle_r), 0.])
    anomaly, node, inclination = ORBITS[index]

    def equation(tau):
        t = receive-tau
        phase = anomaly+math.sqrt(3.986005e14/(26560000.**3))*t
        x, y = 26560000.*math.cos(phase), 26560000.*math.sin(phase)
        position = np.array([x*math.cos(node)-y*math.cos(inclination)*math.sin(node),
                             x*math.sin(node)+y*math.cos(inclination)*math.cos(node),
                             y*math.sin(inclination)])
        return speed*tau-np.linalg.norm(position-receiver)

    tau = brentq(equation, 0., 1., xtol=5e-16, rtol=1e-14)
    clock_sv = (index+1)*1e-5+(index+1)*1e-11*(receive-tau)
    return speed*tau+clock_r-speed*clock_sv


def hline(value, label):
    return f'{value:60}'+label


def version_line(kind):
    chars = list(' '*60)
    chars[:9] = f'{3.05:9.2f}'
    chars[20] = kind
    chars[40] = 'G'
    return ''.join(chars)+'RINEX VERSION / TYPE'


def fixture_texts():
    """Deterministic full-file fixtures, with a predecessor and excluded future."""
    first = datetime.fromisoformat(DAY)+timedelta(seconds=BASE_SECOND-330)
    first_text = ''.join(f'{value:6d}' for value in
                         (first.year, first.month, first.day, first.hour, first.minute))
    first_text += f'{float(first.second):13.7f}'+' '*5+'GPS'
    headers = [version_line('O'), hline('SYNTHETIC S2b FIXTURE; NOT RF DATA', 'COMMENT'),
        hline('SYN0', 'MARKER NAME'), hline('GEODETIC', 'MARKER TYPE'),
        hline(f'{"SYNTHETIC-001":20}{"INERTIAL-GENERATOR":20}{"1":20}', 'REC # / TYPE / VERS'),
        hline('SYNTHETIC ANTENNA', 'ANT # / TYPE'),
        hline(''.join(f'{x:14.4f}' for x in STATION), 'APPROX POSITION XYZ'),
        hline(''.join(f'{x:14.4f}' for x in (0., 0., 0.)), 'ANTENNA: DELTA H/E/N'),
        hline(f'G  {len(TYPES):3d} '+''.join(f'{name:4}' for name in TYPES[:13]), 'SYS / # / OBS TYPES'),
        hline(' '*7+''.join(f'{name:4}' for name in TYPES[13:]), 'SYS / # / OBS TYPES'),
        hline(f'{30.:10.3f}', 'INTERVAL'), hline(first_text, 'TIME OF FIRST OBS'),
        hline('     0', 'RCV CLOCK OFFS APPL'), hline('', 'END OF HEADER')]
    rows = list(headers)
    f1, f2, c = 1575.42e6, 1227.60e6, 299792458.0
    for tag in np.r_[-330., TAGS, 30.]:
        epoch = datetime.fromisoformat(DAY)+timedelta(seconds=BASE_SECOND+float(tag))
        rows.append(f'> {epoch.year:04} {epoch.month:02} {epoch.day:02} {epoch.hour:02} {epoch.minute:02} {float(epoch.second):10.7f}  0  5')
        for index, satellite in enumerate(REFERENCES):
            code = independent_code(tag, index)
            h = .1
            rate = (independent_code(tag-2*h, index)-8*independent_code(tag-h, index)
                    +8*independent_code(tag+h, index)-independent_code(tag+2*h, index))/(12*h)
            ionosphere = 40.+.07*tag
            ratio = f1**2/f2**2
            values = {'C1C': code+ionosphere, 'C2W': code+ionosphere*ratio,
                      'D1C': -(rate-.07)*f1/c, 'D2W': -(rate-.07*ratio)*f2/c,
                      'L1C': (code-ionosphere)*f1/c+1000,
                      'L2W': (code-ionosphere*ratio)*f2/c+2000}
            rows.append(satellite+''.join(f'{values[name]:14.3f}0 ' if name in values and name.startswith('L') else
                        f'{values[name]:14.3f}  ' if name in values else ' '*16 for name in TYPES))
        rows.append(TARGET+'TARGET PAYLOAD MUST NEVER BE DECODED')

    days = (datetime.fromisoformat(DAY)-datetime(1980, 1, 6)).days
    week, toe = days//7, (days % 7)*86400+BASE_SECOND
    nav = [version_line('N'), hline('INVENTED CIRCULAR REFERENCE ORBITS', 'COMMENT'), hline('', 'END OF HEADER')]
    for index, (satellite, elements) in enumerate(zip(REFERENCES, ORBITS, strict=True)):
        anomaly, node, inclination = elements
        omega0 = (node+7.2921151467e-5*toe+math.pi) % (2*math.pi)-math.pi
        blocks = [[(index+1)*1e-5, (index+1)*1e-11, 0.],
                  [1., 0., 0., anomaly], [0., 0., 0., math.sqrt(26560000.)],
                  [toe, 0., omega0, 0.], [inclination, 0., 0., 0.],
                  [0., 0., week, 0.], [2.4, 0., 0., 1.], [toe-30., 4., 0., 0.]]
        for j, block in enumerate(blocks):
            prefix = f'{satellite} 2026 09 10 12 00 00' if j == 0 else '    '
            nav.append(prefix+''.join(f'{number:19.12E}'.replace('E', 'D') for number in block))
    nav += [TARGET+' NUMERICAL TARGET NAVIGATION IS EXCLUDED']+['    POISONED TARGET FIELD']*7
    return '\n'.join(rows)+'\n', '\n'.join(nav)+'\n'
