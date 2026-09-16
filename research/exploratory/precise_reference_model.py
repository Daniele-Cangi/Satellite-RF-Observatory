"""Reference-only CODE orbit/clock evaluation at observed emission times."""
from datetime import datetime, timedelta
from functools import lru_cache
import numpy as np

from positioning.calibration import C, OMEGA, rotate_z, troposphere
from .reference_conventions import relativity_m


def time_of(fields, day):
    year, month, date, hour, minute = map(int, fields[:5])
    second = float(fields[5])
    if not np.isfinite(second) or not 0 <= second < 60:
        raise ValueError('invalid product epoch')
    epoch = datetime(year, month, date, hour, minute)+timedelta(seconds=second)
    return (epoch-datetime.fromisoformat(day)).total_seconds()


def parse_orbit(text, references, target, day):
    """SP3 positions only: ignore its low-rate clock fields, never interpolate them."""
    if target in references:
        raise ValueError('target in orbit allowlist')
    lines = text.splitlines()
    if not lines or lines[0][:3] != '#dP' or lines[-1] != 'EOF':
        raise ValueError('complete SP3-d position extract required')
    headers = [s for s in lines if s.startswith('%c')]
    if not headers or headers[0][9:12] != 'GPS' or lines[0][46:51] != 'IGc20':
        raise ValueError('expected GPST and IGc20 orbit frame')
    if not any('PCV:IGS20_2425' in s for s in lines if s.startswith('/*')):
        raise ValueError('orbit antenna convention differs')
    epochs, t = {}, None
    for line in lines:
        if line.startswith('*'):
            t = time_of(line[1:].split(), day)
            if not 0 <= t <= 86400 or (epochs and t <= max(epochs)):
                raise ValueError('unordered or out-of-day orbit epoch')
            epochs[t] = {}
        elif line.startswith('P'):
            sv = line[1:4]
            if sv not in references or sv == target:
                raise ValueError('unadmitted orbit satellite')
            if t is None or sv in epochs[t]:
                raise ValueError('missing epoch or duplicate position')
            xyz = np.array([float(line[4+14*j:18+14*j]) for j in range(3)])*1000.
            # Clock events/predictions do not invalidate a measured position.
            flags = line.ljust(80)
            valid = np.isfinite(xyz).all() and np.any(xyz != 0.) and all(flags[i] == ' ' for i in (78, 79))
            epochs[t][sv] = {'status': 'AVAILABLE' if valid else 'INVALID_ORBIT', 'xyz_m': xyz.tolist() if valid else None}
    if len(epochs) != int(lines[0][32:39]):
        raise ValueError('orbit epoch count differs from source header')
    return epochs


def extract_clock(text, references, target, day, start, end):
    """Select satellite IDs before numeric conversion; omit all receiver clocks."""
    if target in references or start > end:
        raise ValueError('invalid clock allowlist or interval')
    lines = text.splitlines()
    if not lines or lines[0][:9].strip() != '2.00':
        raise ValueError('CODE RINEX clock 2.00 required')
    stop = next(i for i, s in enumerate(lines) if s[60:].strip() == 'END OF HEADER')
    allowed = {'RINEX VERSION / TYPE', 'PGM / RUN BY / DATE', 'COMMENT', 'TIME SYSTEM ID',
               'ANALYSIS CENTER', '# OF CLK REF', 'ANALYSIS CLK REF', 'END OF HEADER'}
    result = [s for s in lines[:stop+1] if s[60:].strip() in allowed
              or (s.startswith('G') and s[60:].strip() in ('SYS / PCVS APPLIED', 'SYS / DCBS APPLIED'))]
    for line in lines[stop+1:]:
        if not line.startswith('AS ') or line[3:7].strip() not in references:
            continue
        fields = line.split()
        t = time_of(fields[2:8], day)
        if start <= t <= end:
            result.append(line)
    return '\n'.join(result)+'\n'


def parse_clock(text, references, target, day, start, end):
    if extract_clock(text, references, target, day, start, end) != text:
        raise ValueError('unadmitted data in clock extract')
    lines = text.splitlines()
    stop = next(i for i, s in enumerate(lines) if s[60:].strip() == 'END OF HEADER')
    header = lines[:stop]
    if [s[:60].strip() for s in header if s[60:].strip() == 'TIME SYSTEM ID'] != ['GPS']:
        raise ValueError('explicit GPS clock time system required')
    if not any(s.startswith('G') and 'IGS20_2425' in s[:60] and s[60:].strip() == 'SYS / PCVS APPLIED' for s in header):
        raise ValueError('clock antenna convention differs')
    if not any(s[:3] == 'COD' and s[60:].strip() == 'ANALYSIS CENTER' for s in header):
        raise ValueError('CODE clock required')
    result = {sv: {} for sv in references}
    for line in lines[stop+1:]:
        fields = line.split()
        if len(fields) < 9 or fields[8] not in ('1', '2') or len(fields) != 9+int(fields[8]):
            raise ValueError('only clock bias and optional sigma supported')
        sv, t = fields[1], time_of(fields[2:8], day)
        value = float(fields[9].replace('D', 'E'))
        sigma = float(fields[10].replace('D', 'E')) if fields[8] == '2' else None
        if not np.isfinite(value) or (sigma is not None and (not np.isfinite(sigma) or sigma < 0)):
            raise ValueError('invalid clock value or sigma')
        if result[sv] and t <= max(result[sv]):
            raise ValueError('duplicate/discontinuous or unordered clock epoch')
        if t % 30 != 0:
            raise ValueError('clock epoch off 30-second grid')
        result[sv][t] = {'clock_s': value, 'reported_sigma_s': sigma}
    return result


def polynomial(nodes, positions, x, step):
    """Interpolated position and derivative using centered/scaled abscissae."""
    values = np.asarray(positions, dtype=float)
    anchor = values[len(values)//2]
    coefficients = np.linalg.solve(np.vander(nodes, increasing=True), values-anchor)
    position = anchor+np.polynomial.polynomial.polyval(x, coefficients)
    derivative = np.polynomial.polynomial.polyval(x, coefficients[1:]*np.arange(1, len(nodes))[:, None])/step
    return position, derivative


class PreciseReference:
    def __init__(self, orbits, clocks, offsets, target):
        if target in clocks or target in offsets or any(target in row for row in orbits.values()):
            raise ValueError('target in precise products')
        self.orbits, self.clocks, self.offsets, self.target = orbits, clocks, offsets, target

    @lru_cache(maxsize=4096)
    def coefficients(self, sv, center, count):
        if sv == self.target or sv not in self.offsets or count not in (7, 9):
            raise ValueError('unadmitted satellite or interpolation order')
        nodes = np.arange(-(count//2), count//2+1, dtype=float)
        positions = []
        for n in nodes:
            sample = self.orbits.get(center+300.*n, {}).get(sv)
            if sample is None or sample['status'] != 'AVAILABLE':
                raise ValueError('missing or flagged orbit stencil')
            positions.append(sample['xyz_m'])
        values = np.asarray(positions)
        anchor = values[count//2]
        coefficients = np.linalg.solve(np.vander(nodes, increasing=True), values-anchor)
        return anchor, coefficients

    def orbit(self, sv, t, count=9):
        if not np.isfinite(t):
            raise ValueError('nonfinite interpolation epoch')
        center = 300.*np.floor(t/300.+.5)
        anchor, coefficients = self.coefficients(sv, center, count)
        x = (t-center)/300.
        position = anchor+np.polynomial.polynomial.polyval(x, coefficients)
        velocity = np.polynomial.polynomial.polyval(x, coefficients[1:]*np.arange(1, count)[:, None])/300.
        return position, velocity

    def clock(self, sv, t, step=30):
        if sv == self.target or sv not in self.clocks or step not in (30, 60) or not np.isfinite(t):
            raise ValueError('invalid clock request')
        samples = self.clocks[sv]
        left = step*np.floor(t/step)
        right = left+step
        if t == left and left in samples:
            return samples[left]['clock_s']
        if left not in samples or right not in samples:
            raise ValueError('clock gap or extrapolation')
        fraction = (t-left)/step
        return (1-fraction)*samples[left]['clock_s']+fraction*samples[right]['clock_s']

    @lru_cache(maxsize=32768)
    def emitted_state(self, sv, code_m, tag_s, count=9, clock_step=30):
        if not np.isfinite([code_m, tag_s]).all() or code_m <= 0:
            raise ValueError('positive finite observed code required')
        # Solve in an offset from the tag, avoiding cancellation of ~40000 s
        # absolute epochs in the sub-nanosecond emission closure diagnostic.
        emitted_offset = -code_m/C
        offset = emitted_offset
        for _ in range(10):
            tx = tag_s+offset
            com, velocity = self.orbit(sv, tx, count)
            clock = self.clock(sv, tx, clock_step)+relativity_m(com, velocity)/C
            next_offset = emitted_offset-clock
            if abs(next_offset-offset) <= 1e-14:
                offset = next_offset
                break
            offset = next_offset
        else:
            raise ValueError('emission clock iteration did not converge')
        tx = tag_s+offset
        com, velocity = self.orbit(sv, tx, count)
        clock = self.clock(sv, tx, clock_step)+relativity_m(com, velocity)/C
        closure = (offset+clock-emitted_offset)*C
        if abs(closure) > .001:
            raise ValueError('emission equation did not close')
        pco = self.offsets[sv]['if_pco_body_m']
        radial = com-pco[2]*com/np.linalg.norm(com)
        return tx, clock, com, radial, closure, offset

    def model(self, sv, code_m, tag_s, station, receiver_clock_m, count=9, clock_step=30):
        _, clock, _, satellite, _, offset = self.emitted_state(sv, code_m, tag_s, count, clock_step)
        tau = -receiver_clock_m/C-offset
        if not 0 < tau < 1:
            raise ValueError('invalid reception/emission interval')
        rotated = rotate_z(satellite, -OMEGA*tau)
        trop, elevation = troposphere(station, rotated)
        return float(np.linalg.norm(rotated-station)-C*clock+trop), float(elevation)

    def withheld_node_controls(self, references, start, end):
        rows = []
        for sv in references:
            # Hold out SP3 nodes and predict them from their eight neighbors.
            for t in sorted(self.orbits):
                if not start-300 <= t <= end+300:
                    continue
                row = {'reference': sv, 'time_s': t, 'kind': 'ORBIT_NODE', 'status': 'UNAVAILABLE'}
                nodes = np.array([-4., -3., -2., -1., 1., 2., 3., 4.])
                samples = [self.orbits.get(t+300*n, {}).get(sv) for n in nodes]
                actual = self.orbits[t].get(sv)
                if actual and actual['status'] == 'AVAILABLE' and all(s and s['status'] == 'AVAILABLE' for s in samples):
                    predicted, _ = polynomial(nodes, [s['xyz_m'] for s in samples], 0., 300.)
                    row.update(status='COMPARED', discrepancy_m=float(np.linalg.norm(predicted-actual['xyz_m'])))
                rows.append(row)
            for t in sorted(self.clocks[sv]):
                if start-30 <= t <= end+30 and t % 60 == 30:
                    row = {'reference': sv, 'time_s': t, 'kind': 'CLOCK_NODE', 'status': 'UNAVAILABLE'}
                    try:
                        delta = C*(self.clock(sv, t, 60)-self.clocks[sv][t]['clock_s'])
                        row.update(status='COMPARED', discrepancy_m=float(delta))
                    except ValueError:
                        pass
                    rows.append(row)
        return rows
