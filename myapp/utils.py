from django.core.mail import send_mail
from django.conf import settings

def send_email_to_client(email, token):
    subject = 'Reset Your Password'
    message = f'Please click on the following link to reset your password: http://127.0.0.1:8000/changepg/{token}/'
    email_from = settings.DEFAULT_FROM_EMAIL  # Using DEFAULT_FROM_EMAIL is better practice
    recipient_list = [email]
    
    try:
        send_mail(subject, message, email_from, recipient_list)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
def send_email_to_client_contact():
   pass
    
def about(request):
    return render(request, 'about.html')

def contact(request):
    if request.method == 'POST':
        # handle form data (email, save to DB, etc.)
        messages.success(request, 'Message sent successfully.')
        return redirect('contact')
    return render(request, 'contact.html')

import numpy as np
import pandas as pd
import joblib

# ---------------------------
# Step 0: Load Model and Encoders
# ---------------------------
model = joblib.load('myapp/prediction/xgb_safety_model.pkl')
district_le = joblib.load('myapp/prediction/district_encoder.pkl')
crime_le = joblib.load('myapp/prediction/crime_encoder.pkl')
label_le = joblib.load('myapp/prediction/safety_label_encoder.pkl')

# ---------------------------
# Step 1: Load Dataset & Clean Columns
# ---------------------------
df = pd.read_csv('myapp/Allyearcrime.csv')
df.columns = df.columns.str.strip()  # remove leading/trailing spaces

# Rename columns for easier handling
df.rename(columns={
    'YEAR': 'Year',
    'Murder with Rape/Gang Rape': 'Murder_Rape',
    'Dowry Deaths (Sec. 304B IPC)': 'Dowry_Deaths',
    'Abetment to Suicide of Women (Sec. 305/306 IPC)': 'Suicide_Abetment',
    'Acid Attack (Sec. 326A IPC)': 'Acid_Attack',
    'Attempt to Acid Attack (Sec. 326B IPC)': 'Attempt_Acid',
    'Cruelty by Husband or his relatives': 'Cruelty_Husband',
    'Human Trafficking (Sec. 370 & 370A IPC)': 'Human_Trafficking',
    'Selling of Minor Girls (Sec. 372 IPC)': 'Selling_Minor',
    'Buying of Minor Girls (Sec. 373 IPC)': 'Buying_Minor',
    'Dowry Prohibition Act, 1961': 'Dowry_Act'
}, inplace=True)

# ---------------------------
# Step 2: Ensure Severe_Ratio exists
# ---------------------------
if 'Severe_Ratio' not in df.columns:
    df['Severe_Ratio'] = df.apply(lambda row: row['Severe_Crimes']/row['Total_Crimes'] 
                                  if row['Total_Crimes'] != 0 else 0, axis=1)

# ---------------------------
# Step 3: Reshape Dataset to Long Format
# ---------------------------
crime_columns = ['Murder_Rape','Dowry_Deaths','Suicide_Abetment','Miscarriage','Acid_Attack',
                 'Attempt_Acid','Cruelty_Husband','Human_Trafficking','Selling_Minor','Buying_Minor',
                 'Rape','Dowry_Act']

df_long = df.melt(
    id_vars=['State/District','Year','Total_Crimes','Severe_Crimes','Severe_Ratio','Safety_Label'],
    value_vars=crime_columns,
    var_name='Crime_Type',
    value_name='Crime_Count'
)

# ---------------------------
# Step 4: Prediction Function
# ---------------------------
def predict_safety_django(district_input, crime_input, year=2025):
    """
    Input: district name and crime type
    Output: Predicted Safety Label ('Safe' or 'Unsafe')
    """
    # Filter historical data
    subset = df_long[(df_long['State/District'] == district_input) &
                     (df_long['Crime_Type'] == crime_input)]
    
    if subset.empty:
        Crime_Count = Severe_Crimes = Total_Crimes = Severe_Ratio = 0
    else:
        Crime_Count = subset['Crime_Count'].mean()
        Severe_Crimes = subset['Severe_Crimes'].mean()
        Total_Crimes = subset['Total_Crimes'].mean()
        Severe_Ratio = subset['Severe_Ratio'].mean()
    
    # Encode categorical features
    district_code = district_le.transform([district_input])[0]
    crime_code = crime_le.transform([crime_input])[0]
    
    # Prepare input array
    X_new = np.array([[district_code, crime_code, Crime_Count, Severe_Crimes, Total_Crimes, Severe_Ratio, year]])
    
    # Predict using model
    pred = model.predict(X_new)
    
    # Decode label
    label = label_le.inverse_transform(pred)
    return label[0]



from .models import CrimeReport, userProfile

def officer_score(officer, crime_type):
    score = 0
    if officer.specialty == crime_type:
        score += 30
    if officer.experience_level == "Inspector":
        score += 20
    elif officer.experience_level == "Senior":
        score += 10
    # workload:
    open_cases = CrimeReport.objects.filter(
        assigned_officer=officer,
        resolution_status__in=["Pending","Under Investigation"]
    ).count()
    score += max(0, 20 - open_cases)
    return score
