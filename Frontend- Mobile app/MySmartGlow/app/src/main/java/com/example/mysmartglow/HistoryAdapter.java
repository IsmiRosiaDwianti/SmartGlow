package com.example.mysmartglow;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import java.util.List;

public class HistoryAdapter extends RecyclerView.Adapter<HistoryAdapter.ViewHolder> {

    private List<LightingLog> historyList;

    public HistoryAdapter(List<LightingLog> historyList) {
        this.historyList = historyList;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_history, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        LightingLog log = historyList.get(position);

        holder.txtTimestamp.setText("Waktu: " + log.getTimestamp());
        holder.txtLamp.setText("Lampu: " + log.getLampStatusText());
        holder.txtLux.setText("Lux: " + log.getAmbientLightLux());
    }

    @Override
    public int getItemCount() {
        return historyList.size();
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
