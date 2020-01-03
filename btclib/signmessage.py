#!/usr/bin/env python3

# Copyright (C) 2019 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

""" Bitcoin (P2PKH) address-based compact signature for messages.

For message signatures, Bitcoin wallets use a P2PKH address-based scheme
with a compact 65 bytes custom signature encoding.
As it is the case for all digital signature scheme, this scheme actually
works with keys, not addresses: it uses a P2PKH address to uniquely
identify a private/public keypair.
This signature proves the control of the private key corresponding to
a given address and, consequently, of the associated bitcoins (if any).
The signature goes along with its address: public key recovery is used
at verification time, i.e. given a message, the public key
that would have created that signature is found and compared with
the provided address.

Note that in the Bitcoin protocol this compact 65 bytes signature
encoding is only used for messages: for transactions DER encoding is used
instead, resulting in 71 bytes average signature.

At signing time a wallet infrastructure is required to access the
private key corresponding to the given address; alternatively
the private key must be provided explicitly.
For a given message, the ECDSA signature operates on the hash of the
*magic* "Bitcoin Signed Message" prefix concatenated to the actual
message; this prefix manipulation avoids the plain signature of a
possibly deceiving message.
The resulting (r, s) signature is serialized as
[1 byte][r][s], where the first byte is a recovery flag used
during signature verification to discriminate among recovered
public keys and to manage address compression.
Explicitly, the recovery flag value is:

    27 + (4 if compressed else 0) + key_id

where:

- 27 identify a P2PKH address (Electrum also supports Segwit P2WPKH-P2SH
  and P2WPKH, but not according to the BIP137 specifications;
  anyway this module and bitcoin core do not support them yet)
- compressed indicates if the address is the hash of the compressed
  public key representation (SegWit is always compressed)
- key_id is the index in the [0, 3] range identifying which of the
  recovered public keys is the one associated to the address;
  it is stored in the least significant 2 bits of the recovery flag

+-----------+--------+--------------------+
| rec. flag | key_id |    address type    |
+===========+========+====================+
|     27    |    0   | P2PKH uncompressed |
+-----------+--------+--------------------+
|     28    |    1   | P2PKH uncompressed |
+-----------+--------+--------------------+
|     29    |    2   | P2PKH uncompressed |
+-----------+--------+--------------------+
|     30    |    3   | P2PKH uncompressed |
+-----------+--------+--------------------+
|     31    |    0   | P2PKH compressed   |
+-----------+--------+--------------------+
|     32    |    1   | P2PKH compressed   |
+-----------+--------+--------------------+
|     33    |    2   | P2PKH compressed   |
+-----------+--------+--------------------+
|     34    |    3   | P2PKH compressed   |
+-----------+--------+--------------------+
|     35    |    0   | P2WPKH-P2SH        |
+-----------+--------+--------------------+
|     36    |    1   | P2WPKH-P2SH        |
+-----------+--------+--------------------+
|     37    |    2   | P2WPKH-P2SH        |
+-----------+--------+--------------------+
|     38    |    3   | P2WPKH-P2SH        |
+-----------+--------+--------------------+
|     39    |    0   | P2WPKH (bech32)    |
+-----------+--------+--------------------+
|     40    |    1   | P2WPKH (bech32)    |
+-----------+--------+--------------------+
|     41    |    2   | P2WPKH (bech32)    |
+-----------+--------+--------------------+
|     42    |    3   | P2WPKH (bech32)    |
+-----------+--------+--------------------+

Finally, the serialized signature can be base64-encoded to transport it
across channels that are designed to deal with textual data.
Base64-encoding uses 10 digits, 26 lowercase characters, 26 uppercase
characters, '+' (plus sign), and '/' (forward slash);
the equal sign '=' is used as end marker of the encoded message.

Warning: one should never sign a vague statement that could be reused
out of the context it was intended for. E.g. always include at least

- your name (nickname, customer id, email, etc.)
- date and time
- who the message is intended for (name, business name, email, etc.)
- specific purpose of the message

https://bitcoin.stackexchange.com/questions/10759/how-does-the-signature-verification-feature-in-bitcoin-qt-work-without-a-public

https://bitcoin.stackexchange.com/questions/12554/why-the-signature-is-always-65-13232-bytes-long

https://bitcoin.stackexchange.com/questions/34135/what-is-the-strmessagemagic-good-for

https://bitcoin.stackexchange.com/questions/36838/why-does-the-standard-bitcoin-message-signature-include-a-message-prefix

https://bitcoin.stackexchange.com/questions/68844/explicit-message-length-in-bitcoin-signed-message

https://github.com/bitcoinjs/bitcoinjs-lib/blob/1079bf95c1095f7fb018f6e4757277d83b7b9d07/src/message.js#L13

https://bitcointalk.org/index.php?topic=6428

https://bitcointalk.org/index.php?topic=6430

https://crypto.stackexchange.com/questions/18105/how-does-recovering-the-public-key-from-an-ecdsa-signature-work/18106?newreg=670c5855241d4340af0cbbc960fd2dc3

https://github.com/bitcoin/bitcoin/pull/524

https://www.reddit.com/r/Bitcoin/comments/bgcgs2/can_bitcoin_core_0171_sign_message_from_segwit/

https://github.com/bitcoin/bips/blob/master/bip-0137.mediawiki

https://github.com/brianddk/bips/blob/legacysignverify/bip-0xyz.mediawiki

"""

import base64
from hashlib import sha256 as hf
from typing import Tuple, Union

from .curve import mult
from .curves import secp256k1
from .wifaddress import p2pkh_address, h160_from_address
from .dsa import sign, pubkey_recovery
from .utils import octets_from_point, h160
from .segwitaddress import decode

# TODO: support msg as bytes
# TODO: add small wallet (address <-> private key) infrastructure
# TODO:                           then also add sign(address, msg)
# TODO: decouple serialization from address-based signature
# TODO: add test vectors from P. Todd's library
# TODO: report Electrum bug
# TODO: generalize to other curves and hash functions
# TODO: test P2WPKH-P2SH and P2WPKH


def _magic_hash(msg: str) -> bytes:
    # Electrum does strip leading and trailing spaces;
    # bitcoin core does not
    # msg = msg.strip()
    m = hf()
    prefix = b'\x18Bitcoin Signed Message:\n'
    m.update(prefix)
    message = chr(len(msg)) + msg
    m.update(message.encode())
    return m.digest()


def msgsign(msg: str, prvkey: int,
            compressed: bool = True,
            network: str = 'mainnet') -> Tuple[bytes, bytes]:
    """Generate the message signature Tuple(P2PKH address, signature)."""

    pubkey = mult(secp256k1, prvkey)
    pk = octets_from_point(secp256k1, pubkey, compressed)
    address = p2pkh_address(pk, network)

    magic_msg = _magic_hash(msg)
    sig = sign(secp256k1, hf, magic_msg, prvkey)

    pubkeys = pubkey_recovery(secp256k1, hf, magic_msg, sig)
    bytes_sig = sig[0].to_bytes(32, 'big') + sig[1].to_bytes(32, 'big')
    for i in range(len(pubkeys)):
        if pubkeys[i] == pubkey:
            rf = 27 + i
            if compressed:
                rf += 4
            return address, base64.b64encode(bytes([rf]) + bytes_sig)

    # hic sunt leones
    # the following line should never be executed
    raise ValueError("Public key not recovered")


def verify(msg: str, addr: Union[str, bytes], sig: Union[str, bytes]) -> bool:
    """Verify message signature for a given P2PKH address."""

    # try/except wrapper for the Errors raised by _verify
    try:
        return _verify(msg, addr, sig)
    except Exception:
        return False


def _verify(msg: str, addr: Union[str, bytes], sig: Union[str, bytes]) -> bool:
    # Private function for test/dev purposes
    # It raises Errors, while verify should always return True or False

    sig = base64.b64decode(sig)
    if len(sig) != 65:
        raise ValueError(f"Wrong encoding length: {len(sig)} instead of 65")

    r = int.from_bytes(sig[1:33], 'big')
    s = int.from_bytes(sig[33:], 'big')
    magic_msg = _magic_hash(msg)
    pubkeys = pubkey_recovery(secp256k1, hf, magic_msg, (r, s))

    # almost any sig/msg pair recovers (a pubkey and) an addr:
    # signature is valid only if the provided addr is matched
    rf = sig[0]
    if rf < 27:
        raise ValueError(f"Invalid recovery flag: {rf}")
    if rf < 31:  # uncompressed key
        i = rf - 27
        pk = octets_from_point(secp256k1, pubkeys[i], False)
    else:  # compressed key
        i = rf - 31
        pk = octets_from_point(secp256k1, pubkeys[i], True)

    if rf < 35:  # P2PKH
        return h160(pk) == h160_from_address(addr)

    # Segwit
    if rf < 38:  # native P2WPKH
        _, wv, wp = decode(addr)
        if wv != 0:
            raise ValueError(f"Invalid witness version: {wv}")
        return h160(pk) == bytes(wp)
    if rf < 42:  # legacy P2WPKH-P2SH
        # scriptPubkey is 0x0014{20-byte key-hash}
        scriptPubkey = b'\x00\x14' + h160(pk)
        return h160(scriptPubkey) == h160_from_address(addr)
    else:
        raise ValueError(f"Invalid recovery flag: {rf}")
