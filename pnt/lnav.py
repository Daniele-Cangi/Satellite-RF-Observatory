"""Recover data from transmitted GPS L1 C/A LNAV words, including parity.

This is distinct from u-blox/GNSS-SDR output already de-inverted by a receiver.
IS-GPS-200N 20.3.5.2 and table 20-XIV define the parity and D30* inversion.
Parity detects malformed words; it does not authenticate their RF origin.
"""

from numbers import Integral


# Source data bit numbers d1..d24 and previous-word parity bit (D29*=1,
# D30*=0), in order of transmitted parity bits D25..D30.
_PARITY = (
    (1, (1, 2, 3, 5, 6, 10, 11, 12, 13, 14, 17, 18, 20, 23)),
    (0, (2, 3, 4, 6, 7, 11, 12, 13, 14, 15, 18, 19, 21, 24)),
    (1, (1, 3, 4, 5, 7, 8, 12, 13, 14, 15, 16, 19, 20, 22)),
    (0, (2, 4, 5, 6, 8, 9, 13, 14, 15, 16, 17, 20, 21, 23)),
    (0, (1, 3, 5, 6, 7, 9, 10, 14, 15, 16, 17, 18, 21, 22, 24)),
    (1, (3, 5, 6, 8, 9, 10, 11, 13, 15, 19, 22, 23, 24)),
)
_MASKS = tuple((previous_bit, sum(1 << (24 - bit) for bit in data_bits))
               for previous_bit, data_bits in _PARITY)


def decode_lnav_words(words):
    """Return 240 recovered data bits from one complete transmitted subframe.

    Ten unsigned 30-bit words are required. The preceding subframe's word 10
    ends with D29/D30=0; word 2 and word 10 must also end in zero (20.3.3.2).
    Check every word after de-inversion, without repair or alternate polarity.
    Do not apply this to receiver output whose data bits are already recovered.
    """
    words = tuple(words)
    if len(words) != 10 or any(isinstance(word, bool) or not isinstance(word, Integral)
                               or not 0 <= word < 1 << 30 for word in words):
        raise ValueError('LNAV needs ten unsigned 30-bit integer words')
    if words[1] & 3 or words[9] & 3:
        raise ValueError('LNAV word 2/10 must end with D29/D30 zero')
    previous, recovered = 0, []
    for index, word in enumerate(words):
        word = int(word)
        data = (word >> 6) ^ (0xffffff if previous & 1 else 0)
        parity = 0
        for previous_bit, mask in _MASKS:
            parity = (parity << 1) | (((data & mask).bit_count() & 1)
                                      ^ ((previous >> previous_bit) & 1))
        if parity != word & 63:
            raise ValueError(f'LNAV parity failure in word {index + 1}')
        recovered.append(data.to_bytes(3, 'big'))
        previous = word & 3
    return b''.join(recovered)
