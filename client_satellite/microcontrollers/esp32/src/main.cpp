#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsClient.h>

WebSocketsClient webSocket;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.printf("[WSc] Disconnected!\n");
            break;
        case WStype_CONNECTED:
            Serial.printf("[WSc] Connected to url: %s\n", payload);
            webSocket.sendTXT("{\"type\":\"register_node\",\"arch\":\"esp32_s3\"}");
            break;
        case WStype_TEXT:
            Serial.printf("[WSc] get text: %s\n", payload);
            break;
        case WStype_BIN:
            break;
    }
}

void setup() {
    Serial.begin(115200);
    
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    
    while(WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    Serial.println("\nWiFi Connected! IP: ");
    Serial.println(WiFi.localIP());

    webSocket.begin(JARVIS_SERVER_IP, JARVIS_SERVER_PORT, "/api/v1/satellite/stream");
    webSocket.onEvent(webSocketEvent);
    
}

void loop() {
    webSocket.loop();
    
}
