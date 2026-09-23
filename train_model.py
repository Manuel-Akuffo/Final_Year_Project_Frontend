import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

# ── Load Dataset ──
df = pd.read_csv("cardio_dataset.csv")
df = df.dropna()

print("Dataset shape:", df.shape)
print("Risk distribution:\n", df['risk_label'].value_counts())

feature_cols = [c for c in df.columns if c != 'risk_label']
X = df[feature_cols]
y = df['risk_label']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Scale for Logistic Regression
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

print("\n" + "=" * 55)
print("     MODEL COMPARISON — CardioSense AI")
print("=" * 55)

# ── Logistic Regression ──
print("\n📊 Training Logistic Regression...")
lr = LogisticRegression(max_iter=1000, random_state=42)
lr.fit(X_train_s, y_train)
lr_pred = lr.predict(X_test_s)
lr_acc  = accuracy_score(y_test, lr_pred)
print(f"   Accuracy: {lr_acc * 100:.2f}%")
print(classification_report(y_test, lr_pred,
      target_names=['Low Risk', 'Moderate Risk', 'High Risk']))

# ── Random Forest ──
print("\n🌲 Training Random Forest...")
rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)   # No scaling needed for RF
rf_pred = rf.predict(X_test)
rf_acc  = accuracy_score(y_test, rf_pred)
print(f"   Accuracy: {rf_acc * 100:.2f}%")
print(classification_report(y_test, rf_pred,
      target_names=['Low Risk', 'Moderate Risk', 'High Risk']))

# ── Winner ──
print("=" * 55)
print(f"  Logistic Regression : {lr_acc * 100:.2f}%")
print(f"  Random Forest       : {rf_acc * 100:.2f}%")
winner     = 'Random Forest' if rf_acc > lr_acc else 'Logistic Regression'
best_model = rf if rf_acc > lr_acc else lr
diff       = abs(rf_acc - lr_acc) * 100
print(f"  Winner              : {winner} by +{diff:.2f}%")
print("=" * 55)

# ── Confusion Matrix for Winner ──
best_pred = rf_pred if rf_acc > lr_acc else lr_pred
cm = confusion_matrix(y_test, best_pred)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Reds',
            xticklabels=['Low', 'Moderate', 'High'],
            yticklabels=['Low', 'Moderate', 'High'])
plt.title(f'Confusion Matrix — {winner} ({max(lr_acc, rf_acc)*100:.2f}%)')
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.tight_layout()
plt.savefig('confusion_matrix.png')
plt.show()
print("✅ Confusion matrix saved!")

# ── Feature Importance (Random Forest only) ──
if winner == 'Random Forest':
    importances = rf.feature_importances_
    plt.figure(figsize=(10, 6))
    indices = np.argsort(importances)[::-1]
    plt.bar(range(len(feature_cols)), importances[indices], color='tomato')
    plt.xticks(range(len(feature_cols)),
               [feature_cols[i] for i in indices], rotation=45, ha='right')
    plt.title('Random Forest — Feature Importance')
    plt.tight_layout()
    plt.savefig('feature_importance.png')
    plt.show()
    print("✅ Feature importance chart saved!")

# ── Save Best Model ──
joblib.dump(best_model,   'heart_model.pkl')
joblib.dump(scaler,       'scaler.pkl')
joblib.dump(feature_cols, 'feature_cols.pkl')

# Save both separately for reference
joblib.dump(lr, 'heart_model_lr.pkl')
joblib.dump(rf, 'heart_model_rf.pkl')

print(f"\n✅ Best model ({winner}) saved as heart_model.pkl")
print("✅ Both models saved separately (heart_model_lr.pkl, heart_model_rf.pkl)")
print(f"✅ Features: {feature_cols}")