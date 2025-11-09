import joblib
import os
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'processed_data', 'smart_lighting_model_v4_py36.pkl')
model = joblib.load(MODEL_PATH)

def predict_lighting_action(lux, motion, day, time_of_day, weather):
    """
    Return NUMBER 0,1,2 sesuai output model ML
    """
    input_data = np.array([[lux, motion, day, time_of_day, weather]])
    prediction = model.predict(input_data)[0]
    return prediction  # 0,1,2
