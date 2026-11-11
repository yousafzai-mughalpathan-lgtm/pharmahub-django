import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# 1. Dono Files Load karein
train_df = pd.read_csv("Training.csv")
test_df = pd.read_csv("Testing.csv")

# 2. Training Data (Seekhne ke liye)
X_train = train_df.drop('Disease', axis=1)
y_train = train_df['Disease']

# 3. Testing Data (Imtehan ke liye)
X_test = test_df.drop('Disease', axis=1)
y_test = test_df['Disease']

# 4. Model Training
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 5. Accuracy Check (Testing file par)
y_pred = model.predict(X_test)
print(f"Final Test Accuracy: {accuracy_score(y_test, y_pred)*100:.2f}%")

MODEL_FILE_PATH = "disease_model.pkl"
FEATURES_FILE_PATH = "symptom_features.pkl"

# Save the trained model object
with open(MODEL_FILE_PATH, "wb") as f:
    pickle.dump(model, f)

# Save the list of symptom columns (Features)
with open(FEATURES_FILE_PATH, "wb") as f:
    pickle.dump(list(X_train.columns), f)

print(f"✅ Success: Model saved to {MODEL_FILE_PATH}")
print(f"✅ Success: Features list saved to {FEATURES_FILE_PATH}")