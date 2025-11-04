import joblib
import os
import numpy as np

# Load model ML
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'processed_data', 'smart_lighting_model.pkl')
model = joblib.load(MODEL_PATH)

def predict_lighting_action(lux, motion, day, time_of_day, weather):
    """
    Return NUMBER 0,1,2 sesuai output model asli
    """
    input_data = np.array([[lux, motion, day, time_of_day, weather]])
    prediction = model.predict(input_data)[0]
    
    print(f"🎯 AI Prediction: {prediction} (type: {type(prediction)})")
    
    # ✅ RETURN NUMBER LANGSUNG, BUKAN STRING!
    return prediction  # Bisa 0, 1, atau 2