#!/usr/bin/env python3

# Copyright (C) 2017-2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

"""Varint encoding and decoding functions.

A varint (variable integer) is variable-length quantity that uses an
arbitrary number of binary octets (eight-bit bytes) to represent an
arbitrarily large integer.
It is usually a base-128 (7 bits) representation of an unsigned integer
with the addition of the eighth bit to mark continuation of bytes;
it is used to save additional space for a resource constrained system.

This is the slightly different Bitcoin implementation, used in transaction
data to indicate the number of upcoming fields or the length of the
upcoming field.

Up to 0xfc, a varint is just 1 byte; however, if the integer is greater than
0xfc, then it is expanded as [1 byte prefix][number]:

* prefix 0xfd markes the next two bytes as the number;
* prefix 0xfe markes the next four bytes as the number;
* prefix 0xff markes the next eight bytes as the number.
"""

from io import BytesIO
from typing import BinaryIO, Union

from .alias import Octets
from .utils import bytes_from_octets


def decode(stream: Union[BinaryIO, Octets]) -> int:
    '''Return the variable-length integer read from a stream.'''

    if isinstance(stream, str):
        stream = bytes_from_octets(stream)

    if isinstance(stream, bytes):
        stream = BytesIO(stream)

    i = stream.read(1)[0]
    if i == 0xfd:
        # 0xfd marks the next two bytes as the number
        return int.from_bytes(stream.read(2), byteorder='little')
    elif i == 0xfe:
        # 0xfe marks the next four bytes as the number
        return int.from_bytes(stream.read(4), byteorder='little')
    elif i == 0xff:
        # 0xff marks the next eight bytes as the number
        return int.from_bytes(stream.read(8), byteorder='little')
    else:
        # anything else is just the integer
        return i


def encode(i: int) -> bytes:
    '''Return the varint bytes encoding of an integer.'''

    if i <= 0xfc:                  # 1 byte
        return bytes([i])
    elif i <= 0xffff:              # 2 bytes
        return b'\xfd' + i.to_bytes(2, byteorder='little')
    elif i <= 0xffffffff:          # 4 bytes
        return b'\xfe' + i.to_bytes(4, byteorder='little')
    elif i <= 0xffffffffffffffff:  # 8 bytes
        return b'\xff' + i.to_bytes(8, byteorder='little')
    else:
        raise ValueError(f'integer too large ({hex(i)}) for varint encoding')
