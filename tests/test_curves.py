#!/usr/bin/env python3

# Copyright (C) 2017-2020 The btclib developers
#
# This file is part of btclib. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution.
#
# No part of btclib including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in the LICENSE file.

import unittest

from btclib.alias import INF, INFJ, Point
from btclib.curve import _jac_from_aff
from btclib.curvemult import Curve
from btclib.curves import (all_curves, ec23_31, low_card_curves, secp112r1,
                           secp160r1, secp256k1, secp256r1, secp384r1)
from btclib.numbertheory import mod_sqrt
from btclib.secpoint import bytes_from_point, point_from_octets


class TestEllipticCurve(unittest.TestCase):
    def test_exceptions(self):
        # good
        Curve(11, 2, 7, (6, 9), 7, 2, 0, False)

        # p not odd
        self.assertRaises(ValueError, Curve, 10, 2, 7,
                          (6, 9),    7, 1, 0, False)

        # p not prime
        self.assertRaises(ValueError, Curve, 15, 2, 7,
                          (6, 9),    7, 1, 0, False)

        # required security level not in the allowed range
        ec = secp112r1
        p = ec._p
        a = ec._a
        b = ec._b
        G = ec.G
        n = ec.n
        t = ec.sec_bits
        h = ec.h
        self.assertRaises(UserWarning, Curve, p, a, b, G, n, h, 273)
        #Curve(p, a, b, G, n, h, 273)

        # not enough bits for required security level
        ec = secp160r1
        p = ec._p
        a = ec._a
        b = ec._b
        G = ec.G
        n = ec.n
        t = ec.sec_bits
        h = ec.h
        self.assertRaises(UserWarning, Curve, p, a, b, G, n, h, 2*t)
        #Curve(p, a, b, G, n, h, 2*t)

        # a > p
        self.assertRaises(ValueError, Curve, 11, 12,
                          7, (6, 9),   13, 1, 0, False)

        # b > p
        self.assertRaises(ValueError, Curve, 11, 2, 12,
                          (6, 9),   13, 1, 0, False)

        # zero discriminant
        self.assertRaises(ValueError, Curve, 11, 7, 7,
                          (6, 9),    7, 1, 0, False)

        # G not Tuple (int, int)
        self.assertRaises(ValueError, Curve, 11, 2, 7,
                          (6, 9, 1), 7, 1, 0, False)

        # G not on curve
        self.assertRaises(ValueError, Curve, 11, 2, 7,
                          (7, 9),    7, 1, 0, False)

        # n not prime
        self.assertRaises(ValueError, Curve, 11, 2, 7,
                          (6, 9),    8, 1, 0, False)

        # n not Hesse
        self.assertRaises(ValueError, Curve, 11, 2,
                          7, (6, 9),   71, 1, 0, True)

        # h not as expected
        self.assertRaises(ValueError, Curve, 11, 2, 7, (6, 9),   7, 1, 0, True)
        #Curve(11, 2, 7, (6, 9), 7, 1, 0, True)

        # n not group order
        self.assertRaises(ValueError, Curve, 11, 2, 7,
                          (6, 9),   13, 1, 0, False)

        # n=p -> weak curve
        # missing

        # weak curve
        self.assertRaises(UserWarning, Curve, 11, 2, 7, (6, 9), 7, 2, 0, True)

        # x-coordinate not in [0, p-1]
        self.assertRaises(ValueError, secp256k1.y, secp256k1._p)
        # secp256k1.y(secp256k1._p)

    def test_all_curves(self):
        for ec in all_curves:
            self.assertEqual(ec.mult(0), INF)
            self.assertEqual(ec.mult(0), INF)

            self.assertEqual(ec.mult(1), ec.G)
            self.assertEqual(ec.mult(1), ec.G)

            Gy_odd = ec.y_odd(ec.G[0], True)
            self.assertEqual(Gy_odd % 2, 1)
            Gy_even = ec.y_odd(ec.G[0], False)
            self.assertEqual(Gy_even % 2, 0)
            self.assertTrue(ec.G[1] in (Gy_odd, Gy_even))

            Gbytes = bytes_from_point(ec.G, True, ec)
            G2 = point_from_octets(Gbytes, ec)
            self.assertEqual(ec.G, G2)

            Gbytes = bytes_from_point(ec.G, False, ec)
            G2 = point_from_octets(Gbytes, ec)
            self.assertEqual(ec.G, G2)

            P = ec.add(INF, ec.G)
            self.assertEqual(P, ec.G)
            P = ec.add(ec.G, INF)
            self.assertEqual(P, ec.G)
            P = ec.add(INF, INF)
            self.assertEqual(P, INF)

            P = ec.add(ec.G, ec.G)
            self.assertEqual(P, ec.mult(2))

            P = ec.mult(ec.n-1)
            self.assertEqual(ec.add(P, ec.G), INF)
            self.assertEqual(ec.mult(ec.n), INF)

            self.assertEqual(ec.mult(0, INF), INF)
            self.assertEqual(ec.mult(1, INF), INF)
            self.assertEqual(ec.mult(25, INF), INF)

            ec_repr = repr(ec)
            if ec in low_card_curves or ec.psize < 24:
                ec_repr = ec_repr[:-1] + ", False)"
            ec2 = eval(ec_repr)
            self.assertEqual(str(ec), str(ec2))

    def test_octets2point(self):
        for ec in all_curves:
            Q = ec.mult(ec._p)  # just a random point, not INF

            Q_bytes = b'\x03' if Q[1] & 1 else b'\x02'
            Q_bytes += Q[0].to_bytes(ec.psize, byteorder='big')
            R = point_from_octets(Q_bytes, ec)
            self.assertEqual(R, Q)
            self.assertEqual(bytes_from_point(R, True, ec), Q_bytes)

            Q_hex_str = Q_bytes.hex()
            R = point_from_octets(Q_hex_str, ec)
            self.assertEqual(R, Q)

            Q_bytes = b'\x04' + Q[0].to_bytes(ec.psize, byteorder='big')
            Q_bytes += Q[1].to_bytes(ec.psize, byteorder='big')
            R = point_from_octets(Q_bytes, ec)
            self.assertEqual(R, Q)
            self.assertEqual(bytes_from_point(R, False, ec), Q_bytes)

            Q_hex_str = Q_bytes.hex()
            R = point_from_octets(Q_hex_str, ec)
            self.assertEqual(R, Q)

            # scalar in point multiplication can be int, str, or bytes
            t = tuple()
            self.assertRaises(TypeError, ec.mult, t)

            # not a compressed point
            Q_bytes = b'\x01' * (ec.psize+1)
            self.assertRaises(ValueError, point_from_octets, Q_bytes, ec)
            # not a point
            Q_bytes += b'\x01'
            self.assertRaises(ValueError, point_from_octets, Q_bytes, ec)
            # not an uncompressed point
            Q_bytes = b'\x01' * 2 * (ec.psize+1)
            self.assertRaises(ValueError, point_from_octets, Q_bytes, ec)

        # invalid x coordinate
        ec = secp256k1
        x = 0xEEFDEA4CDB677750A420FEE807EACF21EB9898AE79B9768766E4FAA04A2D4A34
        xstr = format(x, '32X')
        self.assertRaises(ValueError, point_from_octets, "03" + xstr, ec)
        self.assertRaises(ValueError, point_from_octets, "04" + 2*xstr, ec)
        self.assertRaises(ValueError, bytes_from_point, (x, x), True, ec)
        self.assertRaises(ValueError, bytes_from_point, (x, x), False, ec)

        # Point must be a tuple[int, int]
        P = x, x, x
        self.assertRaises(ValueError, ec.is_on_curve, P)

        # y-coordinate not in (0, p)
        P = x, ec._p+1
        self.assertRaises(ValueError, ec.is_on_curve, P)

    def test_opposite(self):
        for ec in all_curves:
            Q = ec.mult(ec._p)  # just a random point, not INF
            minus_Q = ec.opposite(Q)
            self.assertEqual(ec.add(Q, minus_Q), INF)
            # jacobian coordinates
            Qjac = _jac_from_aff(Q)
            minus_Qjac = _jac_from_aff(minus_Q)
            self.assertEqual(ec._add_jac(Qjac, minus_Qjac)[2], 0)

            # opposite of INF is INF
            minus_Inf = ec.opposite(INF)
            self.assertEqual(minus_Inf, INF)

    def test_symmetry(self):
        """Methods to break simmetry: quadratic residue, odd/even, low/high"""
        for ec in low_card_curves:

            # setup phase
            # compute quadratic residues
            hasRoot = set()
            hasRoot.add(1)

            for i in range(2, ec._p):
                hasRoot.add(i*i % ec._p)

            # test phase
            Q = ec.mult(ec._p)  # just a random point, not INF
            x = Q[0]
            if ec._p % 4 == 3:
                quad_res = ec.y_quadratic_residue(x, True)
                not_quad_res = ec.y_quadratic_residue(x, False)
                # in this case only quad_res is a quadratic residue
                self.assertIn(quad_res, hasRoot)
                root = mod_sqrt(quad_res, ec._p)
                self.assertEqual(quad_res, (root*root) % ec._p)
                root = ec._p - root
                self.assertEqual(quad_res, (root*root) % ec._p)

                self.assertTrue(not_quad_res == ec._p - quad_res)
                self.assertNotIn(not_quad_res, hasRoot)
                self.assertRaises(ValueError, mod_sqrt, not_quad_res, ec._p)

                y_odd = ec.y_odd(x, True)
                self.assertTrue(y_odd in (quad_res, not_quad_res))
                self.assertTrue(y_odd % 2 == 1)
                y_even = ec.y_odd(x, False)
                self.assertTrue(y_even in (quad_res, not_quad_res))
                self.assertTrue(y_even % 2 == 0)

                y_low = ec.y_low(x, True)
                self.assertTrue(y_low in (y_odd, y_even))
                y_high = ec.y_low(x, False)
                self.assertTrue(y_high in (y_odd, y_even))
                self.assertTrue(y_low < y_high)
            else:
                self.assertTrue(ec._p % 4 == 1)
                # cannot use y_quadratic_residue in this case
                self.assertRaises(ValueError, ec.y_quadratic_residue, x, True)
                self.assertRaises(ValueError, ec.y_quadratic_residue, x, False)

                y_odd = ec.y_odd(x, True)
                self.assertTrue(y_odd % 2 == 1)
                y_even = ec.y_odd(x, False)
                self.assertTrue(y_even % 2 == 0)
                # in this case neither or both are quadratic residues
                self.assertTrue((y_odd in hasRoot and y_even in hasRoot) or
                                (y_odd not in hasRoot and y_even not in hasRoot))
                if y_odd in hasRoot:  # both have roots
                    root = mod_sqrt(y_odd, ec._p)
                    self.assertEqual(y_odd, (root*root) % ec._p)
                    root = ec._p - root
                    self.assertEqual(y_odd, (root*root) % ec._p)
                    root = mod_sqrt(y_even, ec._p)
                    self.assertEqual(y_even, (root*root) % ec._p)
                    root = ec._p - root
                    self.assertEqual(y_even, (root*root) % ec._p)
                else:
                    self.assertRaises(ValueError, mod_sqrt, y_odd, ec._p)
                    self.assertRaises(ValueError, mod_sqrt, y_even, ec._p)

                y_low = ec.y_low(x, True)
                self.assertTrue(y_low in (y_odd, y_even))
                y_high = ec.y_low(x, False)
                self.assertTrue(y_high in (y_odd, y_even))
                self.assertTrue(y_low < y_high)

        # with the last curve
        self.assertRaises(ValueError, ec.y_low, x, 2)
        self.assertRaises(ValueError, ec.y_odd, x, 2)
        self.assertRaises(ValueError, ec.y_quadratic_residue, x, 2)

    def test_aff_jac_conversions(self):
        for ec in all_curves:
            Q = ec.mult(ec._p)  # just a random point, not INF
            QJ = _jac_from_aff(Q)
            checkQ = ec._aff_from_jac(QJ)
            self.assertEqual(Q, checkQ)
            x = ec._x_aff_from_jac(QJ)
            self.assertEqual(Q[0], x)

            checkInf = ec._aff_from_jac(_jac_from_aff(INF))
            self.assertEqual(INF, checkInf)
            # relevant for BIP340-Schnorr signature verification
            self.assertFalse(ec.has_square_y(INF))
            self.assertRaises(ValueError, ec._x_aff_from_jac, INFJ)
            self.assertRaises(ValueError, ec.has_square_y, "Not a Point")


    def test_add(self):
        for ec in all_curves:
            Q1 = ec.mult(ec._p)  # just a random point, not INF
            Q1J = _jac_from_aff(Q1)

            # distinct points
            Q3 = ec._add_aff(Q1,  ec.G)
            Q3jac = ec._add_jac(Q1J, ec.GJ)
            self.assertEqual(Q3, ec._aff_from_jac(Q3jac))

            # point at infinity
            Q3 = ec._add_aff(ec.G,  INF)
            Q3jac = ec._add_jac(ec.GJ, INFJ)
            self.assertEqual(Q3, ec._aff_from_jac(Q3jac))
            Q3 = ec._add_aff(INF,  ec.G)
            Q3jac = ec._add_jac(INFJ, ec.GJ)
            self.assertEqual(Q3, ec._aff_from_jac(Q3jac))

            # point doubling
            Q3 = ec._add_aff(Q1,  Q1)
            Q3jac = ec._add_jac(Q1J, Q1J)
            self.assertEqual(Q3, ec._aff_from_jac(Q3jac))

            # opposite points
            Q1opp = ec.opposite(Q1)
            Q3 = ec._add_aff(Q1,  Q1opp)
            Q3jac = ec._add_jac(Q1J, _jac_from_aff(Q1opp))
            self.assertEqual(Q3, ec._aff_from_jac(Q3jac))


if __name__ == "__main__":
    # execute only if run as a script
    unittest.main()
