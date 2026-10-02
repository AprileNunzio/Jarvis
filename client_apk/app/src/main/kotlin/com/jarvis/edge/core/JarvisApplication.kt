package com.jarvis.edge.core

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class JarvisApplication : Application() {

    companion object {
        const val AUDIO_CHANNEL_ID = "jarvis_continuous_audio_channel"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val audioChannel = NotificationChannel(
                AUDIO_CHANNEL_ID,
                "Jarvis Background Listener",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Mantiene il rilevatore di wake-word 'Jarvis' permanentemente attivo su microfono locale."
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(audioChannel)
        }
    }
}
