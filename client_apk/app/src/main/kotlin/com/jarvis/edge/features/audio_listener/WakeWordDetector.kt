package com.jarvis.edge.features.audio_listener

class WakeWordDetector {

    interface WakeWordCallback {
        fun onWakeWordDetected(confidence: Float, capturedPcm: ByteArray)
    }

    private var callback: WakeWordCallback? = null
    private val frameSize = 1280
    private var isAnalyzing = false

    fun setCallback(cb: WakeWordCallback) {
        this.callback = cb
    }

    fun start() {
        this.isAnalyzing = true
    }

    fun stop() {
        this.isAnalyzing = false
    }

    fun processAudioFrame(pcmChunk: ByteArray) {
        if (!isAnalyzing || pcmChunk.isEmpty()) return

        var energySum = 0L
        for (i in 0 until pcmChunk.size - 1 step 2) {
            val sample = ((pcmChunk[i + 1].toInt() shl 8) or (pcmChunk[i].toInt() and 0xFF)).toShort()
            energySum += kotlin.math.abs(sample.toInt())
        }
        val averageEnergy = energySum / (pcmChunk.size / 2)

        if (averageEnergy > 4500) {
            callback?.onWakeWordDetected(0.92f, pcmChunk)
        }
    }
}
