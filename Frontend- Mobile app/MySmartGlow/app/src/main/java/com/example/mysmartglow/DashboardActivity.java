package com.example.mysmartglow;

import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.util.Log;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.android.volley.Request;
import com.android.volley.RequestQueue;
import com.android.volley.toolbox.JsonArrayRequest;
import com.android.volley.toolbox.JsonObjectRequest;
import com.android.volley.toolbox.Volley;
import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.components.XAxis;
import com.github.mikephil.charting.components.YAxis;
import com.github.mikephil.charting.data.Entry;
import com.github.mikephil.charting.data.LineData;
import com.github.mikephil.charting.data.LineDataSet;
import com.google.firebase.auth.FirebaseAuth;

import org.json.JSONObject;

import java.util.ArrayList;

public class DashboardActivity extends AppCompatActivity {

    // ================= UI =================
    private TextView textLampStatus, textLightIntensity, textMotionStatus, textLampMode;
    private ImageButton btnToggleLamp, btnAutoMode;
    private Button btnLogout;
    private LineChart lightChart;
    private RecyclerView recyclerHistory;

    // ================= STATE =================
    private boolean lampOn = false;
    private boolean isAutoMode = false;

    // ================= DATA =================
    private LightingLogAdapter historyAdapter;
    private ArrayList<LightingLog> historyList = new ArrayList<>();

    // ================= NETWORK =================
    private RequestQueue queue;
    private Handler handler = new Handler();

    private static final String API_LOG =
            "http://103.151.63.68:8014/api/lighting-log/";
    private static final String API_SET_LIGHT =
            "http://103.151.63.68:8014/api/set-light/";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_dashboard);

        // ===== INIT VIEW =====
        textLampStatus = findViewById(R.id.textLampStatus);
        textLightIntensity = findViewById(R.id.textLightIntensity);
        textMotionStatus = findViewById(R.id.textMotionStatus);
        textLampMode = findViewById(R.id.textLampMode);

        btnToggleLamp = findViewById(R.id.btnToggleLamp);
        btnAutoMode = findViewById(R.id.btnAutoMode);
        btnLogout = findViewById(R.id.btnLogout);

        lightChart = findViewById(R.id.lightChart);
        recyclerHistory = findViewById(R.id.recyclerHistory);

        queue = Volley.newRequestQueue(this);

        historyAdapter = new LightingLogAdapter(historyList);
        recyclerHistory.setLayoutManager(new LinearLayoutManager(this));
        recyclerHistory.setAdapter(historyAdapter);

        initChart();

        btnToggleLamp.setOnClickListener(v -> toggleLamp());
        btnAutoMode.setOnClickListener(v -> toggleAutoMode());

        btnLogout.setOnClickListener(v -> {
            FirebaseAuth.getInstance().signOut();
            startActivity(new Intent(this, LoginActivity.class));
            finish();
        });

        handler.post(refreshRunnable);
    }

    // ================= SEND COMMAND =================
    private void sendLightCommand(String mode, String lampStatus) {
        try {
            JSONObject body = new JSONObject();
            body.put("mode", mode);
            if (lampStatus != null) {
                body.put("lamp_status", lampStatus);
            }

            JsonObjectRequest request = new JsonObjectRequest(
                    Request.Method.POST,
                    API_SET_LIGHT,
                    body,
                    response -> Log.d("SET_LIGHT", response.toString()),
                    error -> Log.e("SET_LIGHT", "Failed", error)
            );

            queue.add(request);

        } catch (Exception e) {
            Log.e("SET_LIGHT", "JSON Error", e);
        }
    }

    // ================= MANUAL MODE =================
    private void toggleLamp() {
        if (isAutoMode) return;

        lampOn = !lampOn;

        if (lampOn) {
            sendLightCommand("MANUAL", "ON");
            textLampMode.setText("MANUAL - ON");
            textLampMode.setTextColor(Color.parseColor("#27AE60"));
            btnToggleLamp.setBackgroundResource(R.drawable.bg_lamp_on);
        } else {
            sendLightCommand("MANUAL", "OFF");
            textLampMode.setText("MANUAL - OFF");
            textLampMode.setTextColor(Color.parseColor("#C0392B"));
            btnToggleLamp.setBackgroundResource(R.drawable.bg_lamp_off);
        }
    }

    // ================= AUTO MODE (INI YANG DIPERBAIKI) =================
    private void toggleAutoMode() {
        isAutoMode = !isAutoMode;

        if (isAutoMode) {
            // AUTO AKTIF
            sendLightCommand("AUTO", lampOn ? "ON" : "OFF");

            btnAutoMode.setBackgroundResource(R.drawable.bg_lamp_on);
            btnToggleLamp.setEnabled(false);
            btnToggleLamp.setAlpha(0.5f);

            textLampMode.setText("AUTO MODE");
            textLampMode.setTextColor(Color.parseColor("#C9FFE5"));

        } else {
            // AUTO NONAKTIF (KEMBALI KE MANUAL)
            sendLightCommand("MANUAL", lampOn ? "ON" : "OFF");

            btnAutoMode.setBackgroundResource(R.drawable.bg_lamp_off);
            btnToggleLamp.setEnabled(true);
            btnToggleLamp.setAlpha(1.0f);

            textLampMode.setText("MANUAL MODE");
            textLampMode.setTextColor(Color.parseColor("#367588"));
        }
    }

    // ================= FETCH SENSOR =================
    private void fetchSensor() {
        JsonArrayRequest request = new JsonArrayRequest(
                Request.Method.GET,
                API_LOG,
                null,
                response -> {
                    try {
                        if (response.length() == 0) return;

                        JSONObject obj = response.getJSONObject(0);

                        float lux = (float) obj.optDouble("ambient_light_lux", 0);
                        int motion = obj.optInt("motion_detected", 0);

                        textLightIntensity.setText("Intensitas Cahaya: " + lux + " lx");
                        textMotionStatus.setText(motion == 1 ? "Terdeteksi" : "Tidak Ada");

                        if (isAutoMode) {
                            if (lux < 100 || motion == 1) {
                                if (!lampOn) {
                                    lampOn = true;
                                    sendLightCommand("AUTO", "ON");
                                    btnToggleLamp.setBackgroundResource(R.drawable.bg_lamp_on);
                                }
                                textLampMode.setText("AUTO - ON");
                                textLampMode.setTextColor(Color.parseColor("#27AE60"));
                            } else {
                                if (lampOn) {
                                    lampOn = false;
                                    sendLightCommand("AUTO", "OFF");
                                    btnToggleLamp.setBackgroundResource(R.drawable.bg_lamp_off);
                                }
                                textLampMode.setText("AUTO - OFF");
                                textLampMode.setTextColor(Color.parseColor("#C0392B"));
                            }
                        }

                        textLampStatus.setText(lampOn ? "ON" : "OFF");
                        textLampStatus.setTextColor(lampOn ? Color.GREEN : Color.RED);

                        addChartEntry(lux);

                    } catch (Exception e) {
                        Log.e("API", "Parse error", e);
                    }
                },
                error -> Log.e("API", "Fetch error")
        );

        queue.add(request);
    }

    // ================= HISTORY =================
    private void fetchHistory() {
        JsonArrayRequest request = new JsonArrayRequest(
                Request.Method.GET,
                API_LOG,
                null,
                response -> {
                    historyList.clear();
                    for (int i = 0; i < response.length(); i++) {
                        JSONObject o = response.optJSONObject(i);
                        historyList.add(new LightingLog(
                                o.optString("timestamp"),
                                o.optDouble("ambient_light_lux"),
                                o.optInt("motion_detected"),
                                o.optInt("lighting_action_class")
                        ));
                    }
                    historyAdapter.notifyDataSetChanged();
                },
                error -> Log.e("HISTORY", "Error")
        );

        queue.add(request);
    }

    // ================= CHART =================
    private void initChart() {
        lightChart.getDescription().setEnabled(false);
        lightChart.setData(new LineData());

        XAxis x = lightChart.getXAxis();
        x.setPosition(XAxis.XAxisPosition.BOTTOM);

        YAxis y = lightChart.getAxisLeft();
        lightChart.getAxisRight().setEnabled(false);
    }

    private void addChartEntry(float value) {
        LineData data = lightChart.getData();
        LineDataSet set;

        if (data.getDataSetCount() == 0) {
            set = new LineDataSet(null, "Lux");
            set.setColor(Color.BLUE);
            set.setDrawCircles(false);
            set.setLineWidth(2f);
            data.addDataSet(set);
        }

        data.addEntry(new Entry(data.getEntryCount(), value), 0);
        data.notifyDataChanged();
        lightChart.notifyDataSetChanged();
        lightChart.invalidate();
    }

    // ================= AUTO REFRESH =================
    private final Runnable refreshRunnable = new Runnable() {
        @Override
        public void run() {
            fetchSensor();
            fetchHistory();
            handler.postDelayed(this, 3000);
        }
    };

    @Override
    protected void onDestroy() {
        super.onDestroy();
        handler.removeCallbacks(refreshRunnable);
    }
}
