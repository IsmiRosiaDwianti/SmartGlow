package com.example.mysmartglow;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.firestore.QueryDocumentSnapshot;

import java.util.ArrayList;
import java.util.List;

public class HistoryActivity extends AppCompatActivity {

    RecyclerView recyclerView;
    LightingLogAdapter adapter;
    List<LightingLog> historyList = new ArrayList<>();
    FirebaseFirestore firestore;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_history);

        recyclerView = findViewById(R.id.recyclerHistory);
        recyclerView.setHasFixedSize(true);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));

        adapter = new LightingLogAdapter(historyList);
        recyclerView.setAdapter(adapter);

        firestore = FirebaseFirestore.getInstance();

        loadData();
    }

    private void loadData() {
        firestore.collection("lighting_log")
                .orderBy("timestamp")
                .get()
                .addOnSuccessListener(queryDocumentSnapshots -> {
                    historyList.clear();

                    for (QueryDocumentSnapshot doc : queryDocumentSnapshots) {

                        String timestamp = doc.getString("timestamp");
                        double lux = doc.getDouble("lux");
                        int lamp = doc.getLong("lamp_status").intValue();

                        // Jika Firestore tidak punya motion_detected → default 0
                        int motion = doc.getLong("motion_detected") != null
                                ? doc.getLong("motion_detected").intValue()
                                : 0;

                        historyList.add(new LightingLog(
                                timestamp,
                                lux,
                                motion,
                                lamp
                        ));
                    }

                    adapter.notifyDataSetChanged();
                });
    }
}
