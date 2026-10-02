package com.jarvis.edge.features.camera_stream

import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.*
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.util.Base64
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class CameraVisionManager(private val context: Context) {

    private var cameraDevice: CameraDevice? = null
    private var captureSession: CameraCaptureSession? = null
    private var imageReader: ImageReader? = null
    private var backgroundThread: HandlerThread? = null
    private var backgroundHandler: Handler? = null

    private val httpClient = OkHttpClient()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var isStreaming = false
    private var targetServerUrl = "http://192.168.1.100:8443"

    fun updateServerUrl(url: String) {
        this.targetServerUrl = url
    }

    fun startCameraCapture() {
        startBackgroundThread()
        val manager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        try {
            val cameraId = manager.cameraIdList.firstOrNull { id ->
                val chars = manager.getCameraCharacteristics(id)
                val facing = chars.get(CameraCharacteristics.LENS_FACING)
                facing == CameraCharacteristics.LENS_FACING_FRONT || facing == CameraCharacteristics.LENS_FACING_BACK
            } ?: return

            imageReader = ImageReader.newInstance(640, 480, ImageFormat.JPEG, 2).apply {
                setOnImageAvailableListener({ reader ->
                    val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                    val planes = image.planes
                    val buffer = planes[0].buffer
                    val bytes = ByteArray(buffer.remaining())
                    buffer.get(bytes)
                    image.close()

                    if (isStreaming) {
                        dispatchFrameToServer(bytes)
                    }
                }, backgroundHandler)
            }

            manager.openCamera(cameraId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    cameraDevice = camera
                    createCaptureSession()
                }

                override fun onDisconnected(camera: CameraDevice) {
                    camera.close()
                    cameraDevice = null
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    camera.close()
                    cameraDevice = null
                }
            }, backgroundHandler)
            isStreaming = true
        } catch (_: SecurityException) {
        }
    }

    private fun createCaptureSession() {
        val readerSurface = imageReader?.surface ?: return
        try {
            val builder = cameraDevice?.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)?.apply {
                addTarget(readerSurface)
                set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
            } ?: return

            cameraDevice?.createCaptureSession(
                listOf(readerSurface),
                object : CameraCaptureSession.StateCallback() {
                    override fun onConfigured(session: CameraCaptureSession) {
                        captureSession = session
                        try {
                            session.setRepeatingRequest(builder.build(), null, backgroundHandler)
                        } catch (_: CameraAccessException) {
                        }
                    }

                    override fun onConfigureFailed(session: CameraCaptureSession) {
                    }
                },
                backgroundHandler
            )
        } catch (_: CameraAccessException) {
        }
    }

    private fun dispatchFrameToServer(jpegBytes: ByteArray) {
        scope.launch {
            val b64Frame = Base64.encodeToString(jpegBytes, Base64.NO_WRAP)
            val json = JSONObject().apply {
                put("device_id", "apk_edge_camera")
                put("frame_base64", b64Frame)
                put("timestamp", System.currentTimeMillis())
            }
            val body = json.toString().toRequestBody("application/json".toMediaType())
            val req = Request.Builder()
                .url("$targetServerUrl/api/v1/vision/feed")
                .post(body)
                .build()

            try {
                httpClient.newCall(req).execute().close()
            } catch (_: Exception) {
            }
        }
    }

    fun stopCameraCapture() {
        isStreaming = false
        try {
            captureSession?.close()
            captureSession = null
            cameraDevice?.close()
            cameraDevice = null
            imageReader?.close()
            imageReader = null
        } catch (_: Exception) {
        }
        stopBackgroundThread()
    }

    private fun startBackgroundThread() {
        backgroundThread = HandlerThread("JarvisCameraBackground").also { it.start() }
        backgroundHandler = Handler(backgroundThread?.looper ?: return)
    }

    private fun stopBackgroundThread() {
        backgroundThread?.quitSafely()
        try {
            backgroundThread?.join()
            backgroundThread = null
            backgroundHandler = null
        } catch (_: Exception) {
        }
    }
}
