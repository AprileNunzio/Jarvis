package com.jarvis.edge.features.ui_hud

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.*
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.jarvis.edge.features.audio_listener.ForegroundAudioService
import com.jarvis.edge.features.camera_stream.CameraVisionManager
import com.jarvis.edge.features.server_discovery.ServerDiscoveryManager

class JarvisHudActivity : AppCompatActivity(), ServerDiscoveryManager.DiscoveryCallback {

    private val discoveryManager = ServerDiscoveryManager()
    private var cameraVisionManager: CameraVisionManager? = null

    private lateinit var rootContainer: FrameLayout
    private lateinit var loadingLayout: LinearLayout
    private lateinit var statusText: TextView
    private lateinit var retryButton: Button
    private lateinit var webView: WebView

    private var discoveredServerUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildDynamicUiHierarchy()
        checkSystemPermissions()
        discoveryManager.startDiscovery(this)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun buildDynamicUiHierarchy() {
        rootContainer = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#030712"))
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        loadingLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }

        val titleView = TextView(this).apply {
            text = "JARVIS COGNITIVE EDGE"
            textSize = 24f
            setTextColor(Color.parseColor("#00F0FF"))
            gravity = Gravity.CENTER
            paint.isFakeBoldText = true
        }

        val spinner = ProgressBar(this).apply {
            isIndeterminate = true
            setPadding(0, 32, 0, 32)
        }

        statusText = TextView(this).apply {
            text = "Ricerca del server Jarvis in rete locale..."
            textSize = 14f
            setTextColor(Color.parseColor("#94A3B8"))
            gravity = Gravity.CENTER
        }

        retryButton = Button(this).apply {
            text = "Riprova Ricerca Server"
            setBackgroundColor(Color.parseColor("#0F172A"))
            setTextColor(Color.parseColor("#00F0FF"))
            visibility = View.GONE
            setOnClickListener {
                visibility = View.GONE
                statusText.text = "Scansione della rete in corso..."
                discoveryManager.startDiscovery(this@JarvisHudActivity)
            }
        }

        loadingLayout.addView(titleView)
        loadingLayout.addView(spinner)
        loadingLayout.addView(statusText)
        loadingLayout.addView(retryButton)

        webView = WebView(this).apply {
            visibility = View.GONE
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                mediaPlaybackRequiresUserGesture = false
                allowFileAccess = true
                allowContentAccess = true
                loadWithOverviewMode = true
                useWideViewPort = true
                builtInZoomControls = false
                displayZoomControls = false
                setSupportZoom(false)
            }
            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest) {
                    runOnUiThread {
                        request.grant(request.resources)
                    }
                }
            }
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    loadingLayout.visibility = View.GONE
                    view?.visibility = View.VISIBLE
                }
            }
        }

        rootContainer.addView(webView)
        rootContainer.addView(loadingLayout)
        setContentView(rootContainer)
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        webView.post {
            webView.evaluateJavascript("window.dispatchEvent(new Event('resize'));", null)
        }
    }

    override fun onServerFound(serverUrl: String) {
        discoveredServerUrl = serverUrl
        statusText.text = "Server trovato: $serverUrl\nCaricamento interfaccia di Jarvis..."
        startContinuousAudioService(serverUrl)

        if (hasCameraPermission()) {
            initCameraFeed(serverUrl)
        }

        webView.loadUrl(serverUrl)
    }

    override fun onDiscoveryFailed(message: String) {
        statusText.text = "Server non trovato. Verifica la connessione Wi-Fi."
        retryButton.visibility = View.VISIBLE
    }

    private fun checkSystemPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 100)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        discoveredServerUrl?.let { url ->
            startContinuousAudioService(url)
            if (hasCameraPermission()) {
                initCameraFeed(url)
            }
        }
    }

    private fun hasCameraPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
    }

    private fun initCameraFeed(serverUrl: String) {
        cameraVisionManager = CameraVisionManager(this).apply {
            updateServerUrl(serverUrl)
            startCameraCapture()
        }
    }

    private fun startContinuousAudioService(serverUrl: String) {
        val intent = Intent(this, ForegroundAudioService::class.java).apply {
            putExtra("SERVER_URL", serverUrl)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        discoveryManager.stop()
        cameraVisionManager?.stopCameraCapture()
    }
}
