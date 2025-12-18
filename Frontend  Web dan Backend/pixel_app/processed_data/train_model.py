# ============================================
# Step 0: Import library yang kompatibel dgn Python 3.6
# ============================================
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.ensemble import RandomForestClassifier
import joblib
import pickle
import matplotlib
matplotlib.use('Agg')  # supaya gak error di server tanpa GUI
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================
# Step 1: Load dataset (pastikan file CSV sudah diunggah)
# ============================================
DATA_PATH = os.path.join(os.path.dirname(__file__), "processed_data", "smart_lighting_dataset_2024.csv")

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"❌ Dataset tidak ditemukan di: {DATA_PATH}")

df = pd.read_csv(DATA_PATH)
print("✅ Dataset berhasil dimuat!")
print(df.head())

# ============================================
# Step 2: Bersihkan data
# ============================================
df.drop_duplicates(inplace=True)

if 'ambient_light_lux' in df.columns:
    df['ambient_light_lux'].fillna(df['ambient_light_lux'].mean(), inplace=True)

for col in ['day_of_week', 'time_of_day', 'weather_condition', 'lighting_action_class']:
    if col in df.columns:
        df[col].fillna(df[col].mode()[0], inplace=True)

# ============================================
# Step 3: Pilih fitur dan target
# ============================================
selected_features = ['ambient_light_lux', 'motion_detected', 'day_of_week', 'time_of_day', 'weather_condition']
target = 'lighting_action_class'

data = df[selected_features + [target]]

# Encode kolom kategorikal
le = LabelEncoder()
for col in ['day_of_week', 'time_of_day', 'weather_condition', 'lighting_action_class']:
    data[col] = le.fit_transform(data[col].astype(str))

# ============================================
# Step 4: Split data train & test
# ============================================
X = data[selected_features]
y = data[target]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Ukuran data training:", X_train.shape)
print("Ukuran data testing :", X_test.shape)

# ============================================
# Step 5: Latih model
# ============================================
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
print("✅ Model berhasil dilatih!")

# ============================================
# Step 6: Evaluasi model
# ============================================
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print("\n🎯 Akurasi:", acc)
print("\nLaporan Klasifikasi:")
print(classification_report(y_test, y_pred))

# Confusion Matrix (disimpan sebagai gambar)
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6,5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False)
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.title('Confusion Matrix')

plot_path = os.path.join(os.path.dirname(__file__), "processed_data", "confusion_matrix.png")
plt.savefig(plot_path)
print(f"✅ Confusion matrix disimpan: {plot_path}")

# ============================================
# Step 7: Simpan model & dataset hasil preprocessing
# ============================================
SAVE_DIR = os.path.join(os.path.dirname(__file__), "processed_data")
os.makedirs(SAVE_DIR, exist_ok=True)

processed_csv = os.path.join(SAVE_DIR, "smart_lighting_processed_2024.csv")
pd.concat([X, y], axis=1).to_csv(processed_csv, index=False)
print(f"✅ Dataset preprocessing disimpan: {processed_csv}")

# Simpan model ke pickle (protocol 4 untuk Python 3.6)
model_pickle_path = os.path.join(SAVE_DIR, "smart_lighting_model_pickle.pkl")
with open(model_pickle_path, "wb") as f:
    pickle.dump(model, f, protocol=4)
print(f"✅ Model disimpan (pickle protocol 4): {model_pickle_path}")

# Simpan juga versi joblib
model_joblib_path = os.path.join(SAVE_DIR, "smart_lighting_model_joblib.pkl")
joblib.dump(model, model_joblib_path, protocol=4)
print(f"✅ Model disimpan (joblib protocol 4): {model_joblib_path}")

print("\n✅ Semua proses selesai!")
