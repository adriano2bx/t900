package com.miband3.t900

import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.flow.*
import java.util.UUID

data class Found(val address: String, val name: String?, val rssi: Int)
data class Chr(val service: UUID, val uuid: UUID, val props: Int) {
    val canRead get() = props and BluetoothGattCharacteristic.PROPERTY_READ != 0
    val canWrite get() = props and (BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0
    val canNotify get() = props and (BluetoothGattCharacteristic.PROPERTY_NOTIFY or BluetoothGattCharacteristic.PROPERTY_INDICATE) != 0
    val propsText get() = buildList {
        if (canRead) add("R")
        if (props and BluetoothGattCharacteristic.PROPERTY_WRITE != 0) add("W")
        if (props and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0) add("w")
        if (props and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) add("N")
        if (props and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0) add("I")
    }.joinToString("")
}

enum class Conn { Idle, Connecting, Connected }

/** Cliente BLE genérico: varre, conecta, lista o GATT e faz leitura/escrita/notificação, tudo logado. */
@SuppressLint("MissingPermission")
class BleClient(context: Context) {
    private val app = context.applicationContext
    private val adapter = (app.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private val main = Handler(Looper.getMainLooper())

    val devices = MutableStateFlow<Map<String, Found>>(emptyMap())
    val scanning = MutableStateFlow(false)
    val conn = MutableStateFlow(Conn.Idle)
    val characteristics = MutableStateFlow<List<Chr>>(emptyList())
    val log = MutableStateFlow<List<String>>(emptyList())

    private var gatt: BluetoothGatt? = null
    private val ops = ArrayDeque<() -> Boolean>()
    private var busy = false
    private val opTimeout = Runnable { say("! timeout de operação GATT"); done() }

    val bluetoothOn get() = adapter?.isEnabled == true

    fun say(msg: String) = log.update { (it + "${System.currentTimeMillis() % 100000000} $msg").takeLast(500) }
    fun clearLog() { log.value = emptyList() }

    // ---- varredura (sem filtro: o T900 não anuncia serviços padronizados) ----
    private val scanCb = object : ScanCallback() {
        override fun onScanResult(type: Int, r: ScanResult) {
            val n = r.scanRecord?.deviceName ?: r.device.name
            devices.update { it + (r.device.address to Found(r.device.address, n, r.rssi)) }
        }
        override fun onScanFailed(code: Int) { say("! varredura falhou ($code)"); scanning.value = false }
    }

    fun startScan() {
        val s = adapter?.bluetoothLeScanner ?: return say("! Bluetooth desligado")
        devices.value = emptyMap()
        s.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), scanCb)
        scanning.value = true
        main.postDelayed({ stopScan() }, 20_000)
    }

    fun stopScan() {
        if (!scanning.value) return
        adapter?.bluetoothLeScanner?.stopScan(scanCb)
        scanning.value = false
    }

    // ---- conexão ----
    fun connect(address: String) {
        stopScan()
        disconnect()
        val dev = adapter.getRemoteDevice(address)
        conn.value = Conn.Connecting
        say("conectando a $address")
        gatt = dev.connectGatt(app, false, cb, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect() {
        ops.clear(); busy = false; main.removeCallbacks(opTimeout)
        gatt?.let { it.disconnect(); it.close() }
        gatt = null
        conn.value = Conn.Idle
        characteristics.value = emptyList()
    }

    private val cb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, state: Int) = main.post {
            say("estado=$state status=$status")
            if (state == BluetoothProfile.STATE_CONNECTED) {
                conn.value = Conn.Connected
                g.requestMtu(247) // se falhar/ignorar, seguimos para a descoberta no callback ou no fallback abaixo
                main.postDelayed({ if (characteristics.value.isEmpty()) g.discoverServices() }, 1500)
            } else {
                disconnect()
            }
        }.let {}

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) = main.post {
            say("MTU=$mtu"); g.discoverServices()
        }.let {}

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) = main.post {
            val list = g.services.flatMap { s -> s.characteristics.map { Chr(s.uuid, it.uuid, it.properties) } }
            if (characteristics.value.isNotEmpty()) return@post
            characteristics.value = list
            say("GATT: ${g.services.size} serviços, ${list.size} características")
            g.services.forEach { s ->
                say("S ${s.uuid}")
                s.characteristics.forEach { c ->
                    say("  C ${c.uuid} [${Chr(s.uuid, c.uuid, c.properties).propsText}]")
                }
            }
        }.let {}

        @Deprecated("API < 33")
        override fun onCharacteristicRead(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) =
            readDone(c.uuid, c.value ?: ByteArray(0), status)

        override fun onCharacteristicRead(g: BluetoothGatt, c: BluetoothGattCharacteristic, value: ByteArray, status: Int) =
            readDone(c.uuid, value, status)

        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) {
            main.post { say("WRITE ${c.uuid.short()} status=$status"); done() }
        }

        @Deprecated("API < 33")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) =
            changed(c.uuid, c.value ?: ByteArray(0))

        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic, value: ByteArray) =
            changed(c.uuid, value)

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            main.post { say("CCCD ${d.characteristic.uuid.short()} status=$status"); done() }
        }
    }

    private fun readDone(u: UUID, v: ByteArray, status: Int) {
        main.post {
            say("READ ${u.short()} status=$status ${Hex.encode(v)}${ascii(v)}")
            done()
        }
    }

    private fun changed(u: UUID, v: ByteArray) {
        main.post {
            val hr = if (u == HR_MEASUREMENT) Hex.heartRate(v)?.let { "  (FC=$it bpm)" } ?: "" else ""
            say("NOTIFY ${u.short()} ${Hex.encode(v)}$hr${ascii(v)}")
        }
    }

    // ---- operações em fila (o Android aceita uma por vez) ----
    private fun find(c: Chr) = gatt?.getService(c.service)?.getCharacteristic(c.uuid)

    private fun enqueue(op: () -> Boolean) { ops.addLast(op); if (!busy) next() }

    private fun next() {
        val op = ops.removeFirstOrNull() ?: return
        busy = true
        val ok = try { op() } catch (e: Exception) { say("! ${e.message}"); false }
        if (ok) main.postDelayed(opTimeout, 5000) else { busy = false; next() }
    }

    private fun done() { main.removeCallbacks(opTimeout); busy = false; next() }

    fun read(c: Chr) = enqueue { find(c)?.let { gatt?.readCharacteristic(it) } ?: false }

    fun write(c: Chr, data: ByteArray, noResponse: Boolean) = enqueue {
        val ch = find(c) ?: return@enqueue false
        say("-> ${c.uuid.short()} ${Hex.encode(data)}${if (noResponse) " (sem resposta)" else ""}")
        val type = if (noResponse) BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE else BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        val g = gatt ?: return@enqueue false
        val started = if (Build.VERSION.SDK_INT >= 33) {
            g.writeCharacteristic(ch, data, type) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION") run { ch.writeType = type; ch.value = data; g.writeCharacteristic(ch) }
        }
        // WRITE_NO_RESPONSE também chama o callback, mas por segurança não travamos a fila.
        if (started && noResponse) main.postDelayed({ if (busy) done() }, 150)
        started
    }

    fun notify(c: Chr, enable: Boolean) = enqueue {
        val g = gatt ?: return@enqueue false
        val ch = find(c) ?: return@enqueue false
        g.setCharacteristicNotification(ch, enable)
        val d = ch.getDescriptor(CCCD) ?: run { say("! sem CCCD em ${c.uuid.short()}"); return@enqueue false }
        val value = when {
            !enable -> BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE
            ch.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0 -> BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            else -> BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
        }
        say("${if (enable) "assinando" else "cancelando"} ${c.uuid.short()}")
        if (Build.VERSION.SDK_INT >= 33) g.writeDescriptor(d, value) == BluetoothStatusCodes.SUCCESS
        else @Suppress("DEPRECATION") run { d.value = value; g.writeDescriptor(d) }
    }

    companion object {
        val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        val HR_MEASUREMENT: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
        val BATTERY_LEVEL: UUID = UUID.fromString("00002a19-0000-1000-8000-00805f9b34fb")
    }
}

fun UUID.short(): String {
    val s = toString()
    return if (s.endsWith("-0000-1000-8000-00805f9b34fb") && s.startsWith("0000")) s.substring(4, 8) else s
}

private fun ascii(v: ByteArray): String =
    if (v.isNotEmpty() && v.all { it in 32..126 }) "  \"${String(v)}\"" else ""
