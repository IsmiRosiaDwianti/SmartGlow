package com.example.mysmartglow;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import java.util.List;

public class LightingLogAdapter extends RecyclerView.Adapter<LightingLogAdapter.ViewHolder> {

    private List<LightingLog> historyList;

    public LightingLogAdapter(List<LightingLog> historyList) {
        this.historyList = historyList;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_history, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        LightingLog log = historyList.get(position);

        holder.txtTimestamp.setText("Waktu: " + log.getTimestamp());
        holder.txtLamp.setText("Lampu: " + getStatusText(log.getLightingActionClass()));
        holder.txtLux.setText("Cahaya: " + log.getAmbientLightLux() + " lx");
    }

    @Override
    public int getItemCount() {
        return historyList.size();
    }

    // =============================
    //   KONVERSI STATUS LAMPU
    // =============================
    private String getStatusText(int status) {
        switch (status) {
            case 1:
                return "ON";
            case 2:
                return "REDUP";   // <--- STATUS BARU
            default:
                return "OFF";
        }
    }

    public static class ViewHolder extends RecyclerView.ViewHolder {
        TextView txtTimestamp, txtLamp, txtLux;

        public ViewHolder(@NonNull View itemView) {
            super(itemView);
            txtTimestamp = itemView.findViewById(R.id.txtTimestamp);
            txtLamp = itemView.findViewById(R.id.txtLamp);
            txtLux = itemView.findViewById(R.id.txtLux);
        }
    }
}
