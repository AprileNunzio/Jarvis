package com.jarvis.edge.features.server_discovery

import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.TimeUnit

class ServerDiscoveryManager {

    interface DiscoveryCallback {
        fun onServerFound(serverUrl: String)
        fun onDiscoveryFailed(message: String)
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(1500, TimeUnit.MILLISECONDS)
        .readTimeout(1500, TimeUnit.MILLISECONDS)
        .build()

    private val discoveryJob = SupervisorJob()
    private val scope = CoroutineScope(Dispatchers.IO + discoveryJob)

    fun startDiscovery(callback: DiscoveryCallback) {
        scope.launch {
            val udpDiscovered = listenForServerBroadcast()
            if (udpDiscovered != null) {
                withContext(Dispatchers.Main) {
                    callback.onServerFound(udpDiscovered)
                }
                return@launch
            }

            val probedUrl = probeSubnetForJarvis()
            withContext(Dispatchers.Main) {
                if (probedUrl != null) {
                    callback.onServerFound(probedUrl)
                } else {
                    callback.onServerFound("http://192.168.1.100:8443")
                }
            }
        }
    }

    private suspend fun listenForServerBroadcast(): String? = withContext(Dispatchers.IO) {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket(51820)
            socket.soTimeout = 2500
            val buffer = ByteArray(2048)
            val packet = DatagramPacket(buffer, buffer.size)
            socket.receive(packet)
            val rawMsg = String(packet.data, 0, packet.length)
            val json = JSONObject(rawMsg)
            if (json.optString("type") == "JARVIS_SERVER_BEACON") {
                val host = packet.address.hostAddress ?: "127.0.0.1"
                val port = json.optInt("port", 8443)
                return@withContext "http://$host:$port"
            }
        } catch (_: Exception) {
        } finally {
            socket?.close()
        }
        return@withContext null
    }

    private suspend fun probeSubnetForJarvis(): String? = withContext(Dispatchers.IO) {
        val candidateHosts = listOf("127.0.0.1", "10.0.2.2", "192.168.1.100", "192.168.1.50", "192.168.1.10")
        for (host in candidateHosts) {
            val testUrl = "http://$host:8443"
            try {
                val req = Request.Builder().url("$testUrl/health").build()
                httpClient.newCall(req).execute().use { res ->
                    if (res.isSuccessful) {
                        return@withContext testUrl
                    }
                }
            } catch (_: Exception) {
            }
        }
        return@withContext null
    }

    fun stop() {
        discoveryJob.cancel()
    }
}
