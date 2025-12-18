package com.example.mysmartglow;

public class LightingLog {

    private String timestamp;
    private double ambientLightLux;
    private int motionDetected;
    private int lightingActionClass; // 0 = OFF, 1 = ON, 2 = REDUP

    public LightingLog(String timestamp, double ambientLightLux, int motionDetected, int lightingActionClass) {
        this.timestamp = timestamp;
        this.ambientLightLux = ambientLightLux;
        this.motionDetected = motionDetected;
        this.lightingActionClass = lightingActionClass;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public double getAmbientLightLux() {
        return ambientLightLux;
    }

    public int getMotionDetected() {
        return motionDetected;
    }

    public int getLightingActionClass() {
        return lightingActionClass;
    }

    // =============================
    // STATUS LAMPU (ON / OFF / REDUP)
    // =============================
    public String getLampStatusText() {
        switch (lightingActionClass) {
            case 1:
                return "ON";
            case 2:
                return "REDUP";
            default:
                return "OFF";
        }
    }

    // =============================
    // STATUS GERAKAN
    // =============================
    public String getMotionText() {
        return (motionDetected == 1) ? "Terdeteksi" : "Tidak Ada";
    }
}
