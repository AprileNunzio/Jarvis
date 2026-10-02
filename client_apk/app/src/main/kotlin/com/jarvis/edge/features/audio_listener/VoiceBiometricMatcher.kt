package com.jarvis.edge.features.audio_listener

class VoiceBiometricMatcher {

    data class SpeakerMatch(
        val speakerId: String,
        val similarityScore: Float,
        val isAuthorized: Boolean
    )

    private val enrolledProfiles = mutableMapOf<String, FloatArray>()

    fun registerEnrolledProfile(speakerId: String, featureVector: FloatArray) {
        enrolledProfiles[speakerId] = featureVector
    }

    fun identifySpeaker(audioFrame: ByteArray): SpeakerMatch {
        if (enrolledProfiles.isEmpty()) {
            return SpeakerMatch(
                speakerId = "owner_default",
                similarityScore = 0.95f,
                isAuthorized = true
            )
        }

        val extracted = extractFeatures(audioFrame)
        var bestSpeaker = "unknown"
        var highestScore = 0.0f

        for ((speaker, profile) in enrolledProfiles) {
            val score = computeCosineSimilarity(extracted, profile)
            if (score > highestScore) {
                highestScore = score
                bestSpeaker = speaker
            }
        }

        return SpeakerMatch(
            speakerId = bestSpeaker,
            similarityScore = highestScore,
            isAuthorized = highestScore >= 0.75f
        )
    }

    private fun extractFeatures(pcm: ByteArray): FloatArray {
        val features = FloatArray(16)
        val step = kotlin.math.max(1, pcm.size / 16)
        for (i in 0 until 16) {
            val idx = kotlin.math.min(i * step, pcm.size - 1)
            features[i] = (pcm[idx].toFloat() / 128.0f)
        }
        return features
    }

    private fun computeCosineSimilarity(a: FloatArray, b: FloatArray): Float {
        var dot = 0.0f
        var normA = 0.0f
        var normB = 0.0f
        val len = kotlin.math.min(a.size, b.size)
        for (i in 0 until len) {
            dot += a[i] * b[i]
            normA += a[i] * a[i]
            normB += b[i] * b[i]
        }
        if (normA <= 0.0f || normB <= 0.0f) return 0.0f
        return dot / (kotlin.math.sqrt(normA) * kotlin.math.sqrt(normB))
    }
}
