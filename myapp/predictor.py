import joblib
import pandas as pd
import os

# Path to model
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'best_safety_model.joblib')

# Load the model (done once when Django starts)
model = joblib.load(MODEL_PATH)

# Columns must match training data
expected_columns = [
    'State/District', 'Murder with Rape/Gang Rape',
    'Dowry Deaths (Sec. 304B IPC)', 'Abetment to Suicide of Women (Sec. 305/306 IPC)',
    'Miscarriage ', 'Acid Attack (Sec. 326A IPC)',
    'Attempt to Acid Attack (Sec. 326B IPC)',
    'Cruelty by Husband or his relatives',
    'Human Trafficking (Sec. 370 & 370A IPC) ',
    'Selling of Minor Girls (Sec. 372 IPC)',
    'Buying of Minor Girls (Sec. 373 IPC)',
    'Rape', 'Dowry Prohibition Act, 1961',
    'YEAR', 'Total_Crimes ', 'Severe_Crimes'
]

def predict_safety(data):
    df = pd.DataFrame([data])
    df = df.reindex(columns=expected_columns)

    pred = model.predict(df)[0]
    prob = model.predict_proba(df)[0][1]

    return {
        "prediction": "SAFE" if pred == 1 else "UNSAFE",
        "probability": round(prob * 100, 2)
    }
