package com.miband3.t900

import org.junit.Assert.*
import org.junit.Test

class HexTest {
    @Test fun roundTrip() {
        assertEquals("01 0A FF", Hex.encode(Hex.decode("0x01,0a ff")!!))
    }
    @Test fun invalid() {
        assertNull(Hex.decode("abc"))
        assertNull(Hex.decode("zz"))
        assertNull(Hex.decode(""))
    }
    @Test fun heartRate8and16() {
        assertEquals(72, Hex.heartRate(byteArrayOf(0x00, 72)))
        assertEquals(300, Hex.heartRate(byteArrayOf(0x01, 0x2C, 0x01)))
        assertNull(Hex.heartRate(byteArrayOf(0x00)))
    }
}
