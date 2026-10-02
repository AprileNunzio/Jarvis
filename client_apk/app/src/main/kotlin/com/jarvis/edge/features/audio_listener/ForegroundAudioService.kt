package com.jarvis.edge.features.audio_listener

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.jarvis.edge.core.JarvisApplication
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class ForegroundAudioService : Service(), WakeWordDetector.WakeWordCallback {

    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    private val wakeDetector = WakeWordDetector()
    private val biometricMatcher = VoiceBiometricMatcher()
    private val httpClient = OkHttpClient()

    private var audioRecord: AudioRecord? = null
    private var isRecording = false

    private val sampleRate = 16000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
    private var serverUrl = "http://192.168.1.100:8443/api/v1/command"

    override fun onCreate() {
        super.onCreate()
        wakeDetector.setCallback(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        intent?.getStringExtra("SERVER_URL")?.let {
            if (it.isNotEmpty()) {
                serverUrl = "$it/api/v1/command"
            }
        }

        val notification: Notification = NotificationCompat.Builder(this, JarvisApplication.AUDIO_CHANNEL_ID)
            .setContentTitle("Jarvis Edge - Ascolto Attivo")
            .setContentText("Sempre in ascolto per 'Jarvis' con biometria vocale.")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()

        startForeground(1001, notification)
        if (!isRecording) {
            startContinuousRecording()
        }
        return START_STICKY
    }

    private fun startContinuousRecording() {
        val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            )

            audioRecord?.startRecording()
            isRecording = true
            wakeDetector.start()

            serviceScope.launch {
                val buffer = ByteArray(bufferSize)
                while (isRecording && isActive) {
                    val readBytes = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (readBytes > 0) {
                        wakeDetector.processAudioFrame(buffer.copyOf(readBytes))
                    }
                }
            }
        } catch (_: SecurityException) {
            stopSelf()
        }
    }

    override fun onWakeWordDetected(confidence: Float, capturedPcm: ByteArray) {
        val matchResult = biometricMatcher.identifySpeaker(capturedPcm)
        if (!matchResult.isAuthorized) return

        serviceScope.launch {
            val json = JSONObject().apply {
                put("query", "Attivazione vocale da Jarvis Edge")
                put("device_id", "apk_edge_tablet_phone")
                put("voice_pcm_base64", android.util.Base64.encodeToString(capturedPcm, android.util.Base64.NO_WRAP))
            }
            val body = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url(serverUrl)
                .addHeader("Authorization", "Bearer v1.local.apk_edge_token")
                .post(body)
                .build()

            try {
                httpClient.newCall(request).execute().close()
            } catch (_: Exception) {
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isRecording = false
        wakeDetector.stop()
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {
        }
        serviceJob.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
