package com.miband3.t900

object Hex {
    fun encode(b: ByteArray): String = b.joinToString(" ") { "%02X".format(it) }

    /** Aceita "01 0A ff", "0x01,0x0a" ou "010Aff". Retorna null se inválido. */
    fun decode(s: String): ByteArray? {
        val clean = s.replace(Regex("0x|[\\s,:-]", RegexOption.IGNORE_CASE), "")
        if (clean.isEmpty() || clean.length % 2 != 0 || !clean.all { it.isDigit() || it.lowercaseChar() in 'a'..'f' }) return null
        return ByteArray(clean.length / 2) { clean.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    }

    /** Heart Rate Measurement (0x2A37), perfil padrão BLE. */
    fun heartRate(b: ByteArray): Int? {
        if (b.size < 2) return null
        val sixteen = b[0].toInt() and 0x01 != 0
        return if (sixteen) {
            if (b.size < 3) null else (b[1].toInt() and 0xFF) or ((b[2].toInt() and 0xFF) shl 8)
        } else b[1].toInt() and 0xFF
    }
}
