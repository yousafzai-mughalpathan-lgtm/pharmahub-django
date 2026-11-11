import pandas as pd
import pickle
from sklearn.metrics import accuracy_score

# 1. Saved Model aur Features Load karein
with open("disease_model.pkl", "rb") as f:
    model = pickle.load(f)

with open("symptom_features.pkl", "rb") as f:
    feature_columns = pickle.load(f)

# 2. Testing Data Load karein
test_df = pd.read_csv("Testing.csv")

# 3. Features aur Target alag karein (features ki sequence wahi rakhein jo training ke waqt thi)
X_test = test_df[feature_columns]
y_test = test_df['Disease']

# 4. Predict karke Accuracy check karein
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred) * 100

print(f"🎯 Final Test Accuracy: {accuracy:.2f}%")