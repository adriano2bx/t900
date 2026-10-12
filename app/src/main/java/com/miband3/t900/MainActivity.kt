package com.miband3.t900

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

class MainActivity : ComponentActivity() {
    private lateinit var ble: BleClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ble = BleClient(this)
        setContent { MaterialTheme { Surface(Modifier.fillMaxSize()) { App(ble, ::share) } } }
    }

    override fun onDestroy() { ble.disconnect(); super.onDestroy() }

    private fun share(text: String) = startActivity(
        Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text), "Exportar log")
    )
}

private val perms = if (Build.VERSION.SDK_INT >= 31)
    arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

@Composable
private fun App(ble: BleClient, share: (String) -> Unit) {
    val ctx = LocalContext.current
    val conn by ble.conn.collectAsState()
    val scanning by ble.scanning.collectAsState()
    val devices by ble.devices.collectAsState()
    val chars by ble.characteristics.collectAsState()
    val log by ble.log.collectAsState()
    var granted by remember { mutableStateOf(perms.all { ctx.checkSelfPermission(it) == android.content.pm.PackageManager.PERMISSION_GRANTED }) }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r -> granted = r.values.all { it } }
    var selected by remember { mutableStateOf<Chr?>(null) }

    Column(Modifier.fillMaxSize().systemBarsPadding().padding(12.dp)) {
        Text("T900 Ultra · explorador BLE", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))

        if (!granted) {
            Button({ ask.launch(perms) }) { Text("Conceder permissões de Bluetooth") }
        } else if (conn == Conn.Idle) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Button({ if (ble.bluetoothOn) ble.startScan() else ble.say("! ligue o Bluetooth") }, enabled = !scanning) {
                    Text(if (scanning) "Procurando…" else "Procurar relógio")
                }
                Spacer(Modifier.width(12.dp))
                Text("Mantenha o relógio fora do app oficial (ele só aceita uma conexão).", fontSize = 12.sp, modifier = Modifier.weight(1f))
            }
            LazyColumn(Modifier.weight(1f)) {
                items(devices.values.sortedWith(compareByDescending<Found> { it.name != null }.thenByDescending { it.rssi }), key = { it.address }) { d ->
                    ListItem(
                        headlineContent = { Text(d.name ?: "(sem nome)") },
                        supportingContent = { Text("${d.address} · ${d.rssi} dBm") },
                        modifier = Modifier.clickable { ble.connect(d.address) },
                    )
                }
            }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (conn == Conn.Connecting) "Conectando…" else "Conectado", Modifier.weight(1f))
                OutlinedButton({ selected = null; ble.disconnect() }) { Text("Desconectar") }
            }
            LazyColumn(Modifier.weight(1f)) {
                items(chars, key = { it.service.toString() + it.uuid }) { c ->
                    ListItem(
                        overlineContent = { Text("serviço ${c.service.short()}", fontSize = 11.sp) },
                        headlineContent = { Text(c.uuid.short(), fontFamily = FontFamily.Monospace) },
                        trailingContent = { Text(c.propsText, fontFamily = FontFamily.Monospace) },
                        colors = if (c == selected) ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.secondaryContainer) else ListItemDefaults.colors(),
                        modifier = Modifier.clickable { selected = c },
                    )
                }
            }
            selected?.let { Actions(ble, it) }
        }

        HorizontalDivider(Modifier.padding(vertical = 6.dp))
        Row {
            TextButton({ share(log.joinToString("\n")) }) { Text("Exportar log") }
            TextButton({ ble.clearLog() }) { Text("Limpar") }
        }
        val state = rememberLazyListState()
        LaunchedEffect(log.size) { if (log.isNotEmpty()) state.scrollToItem(log.lastIndex) }
        SelectionContainer(Modifier.height(180.dp)) {
            LazyColumn(state = state) {
                items(log) { Text(it, fontFamily = FontFamily.Monospace, fontSize = 11.sp) }
            }
        }
    }
}

@Composable
private fun Actions(ble: BleClient, c: Chr) {
    var hex by remember(c) { mutableStateOf("") }
    var subscribed by remember(c) { mutableStateOf(false) }
    Column {
        Row {
            if (c.canRead) OutlinedButton({ ble.read(c) }) { Text("Ler") }
            if (c.canNotify) {
                Spacer(Modifier.width(8.dp))
                OutlinedButton({ subscribed = !subscribed; ble.notify(c, subscribed) }) { Text(if (subscribed) "Parar notif." else "Assinar") }
            }
        }
        if (c.canWrite) {
            OutlinedTextField(hex, { hex = it }, label = { Text("Hex a enviar (ex: 01 0A FF)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            val data = Hex.decode(hex)
            Row {
                Button({ data?.let { ble.write(c, it, noResponse = false) } }, enabled = data != null) { Text("Escrever") }
                Spacer(Modifier.width(8.dp))
                OutlinedButton({ data?.let { ble.write(c, it, noResponse = true) } }, enabled = data != null) { Text("Sem resposta") }
            }
        }
    }
}
