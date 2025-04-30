### Imports
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import os
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score, confusion_matrix
import matplotlib.pyplot as plt

### Label Encoder that handles unseen categories
class LabelEncoderExt:
    def __init__(self):
        self.le = LabelEncoder()
    def fit(self, data):
        self.le = self.le.fit(list(data) + ['Unknown'])
        self.classes_ = self.le.classes_
        return self
    def transform(self, data):
        arr = []
        for x in data:
            arr.append(x if x in self.classes_ else 'Unknown')
        return self.le.transform(arr)

### Paths and Hyperparameters
DATA_PATH   = 'NF-UQ-NIDS-v2.csv' 
OUTPUT_DIR  = './'
CHUNK_SIZE  = 200_000
USE_GPU     = False  

XGB_PARAMS = {
    "objective":    "binary:logistic",
    "eval_metric":  "auc",
    "tree_method":  "hist",
    "device":       "cuda" if USE_GPU else "cpu",
    "max_depth":    6,
    "eta":          0.1,
}

# Important features to keep
DESIRED_FEATURES = [
    'IPV4_SRC_ADDR',
    'IPV4_DST_ADDR',
    'L4_SRC_PORT',
    'L4_DST_PORT',
    'PROTOCOL',
    'TCP_FLAGS',
    'IN_BYTES',
    'IN_PKTS',
    'FLOW_DURATION_MILLISECONDS',
    'SRC_TO_DST_SECOND_BYTES',
    'SRC_TO_DST_AVG_THROUGHPUT'
]


### Initialize encoder placeholders
le_src, le_dst = LabelEncoderExt(), LabelEncoderExt()
fitted_src = fitted_dst = False

### Training Loop
booster       = None
chunk_id      = 0
val_aucs      = []
val_accs      = []
val_f1s       = []

for chunk in pd.read_csv(DATA_PATH, chunksize=CHUNK_SIZE, low_memory=False):
    chunk_id += 1
    print(f"\n Chunk {chunk_id}: {chunk.shape}")

    # ── a) Preprocessing ──
    chunk.replace([np.inf, -np.inf], np.nan, inplace=True)
    chunk.fillna(0, inplace=True)

    if 'Label' not in chunk.columns:
        print("No 'Label' found — skipping chunk.")
        continue

    # Keep only selected features + 'Label' column
    feature_cols = DESIRED_FEATURES + ['Label']
    chunk = chunk[feature_cols]

    # Encode IP addresses
    if not fitted_src:
        le_src.fit(chunk['IPV4_SRC_ADDR'])
        fitted_src = True
    if not fitted_dst:
        le_dst.fit(chunk['IPV4_DST_ADDR'])
        fitted_dst = True

    chunk['IPV4_SRC_ADDR'] = le_src.transform(chunk['IPV4_SRC_ADDR'])
    chunk['IPV4_DST_ADDR'] = le_dst.transform(chunk['IPV4_DST_ADDR'])

    # Handle any other categorical (unlikely)
    for col in chunk.select_dtypes(include='object'):
        le = LabelEncoderExt().fit(chunk[col])
        chunk[col] = le.transform(chunk[col])

    y = chunk['Label'].astype(int)
    X = chunk.drop(columns=['Label'])

    # Impute missing
    X = pd.DataFrame(SimpleImputer(strategy='mean').fit_transform(X), columns=X.columns)
    X = X.clip(-1e6, 1e6)

    # ── b) Train-validation split ──
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval   = xgb.DMatrix(X_val, label=y_val)

    # ── c) Train incrementally ──
    evals = [(dval, 'validation')]
    if booster is None:
        booster = xgb.train(XGB_PARAMS, dtrain, num_boost_round=50, evals=evals, verbose_eval=False)
    else:
        booster = xgb.train(XGB_PARAMS, dtrain, num_boost_round=50, xgb_model=booster, evals=evals, verbose_eval=False)

    # ── d) Metrics ──
    preds = booster.predict(dval)
    y_pred_bin = (preds > 0.5).astype(int)

    auc = roc_auc_score(y_val, preds)
    acc = accuracy_score(y_val, y_pred_bin)
    f1  = f1_score(y_val, y_pred_bin)
    cm  = confusion_matrix(y_val, y_pred_bin)

    val_aucs.append(auc)
    val_accs.append(acc)
    val_f1s.append(f1)

    print(f"Chunk {chunk_id} — AUC: {auc:.4f}, Accuracy: {acc:.4f}, F1: {f1:.4f}")
    print("Confusion Matrix:\n", cm)

### Final Report
print(f"\nMean AUC:      {np.mean(val_aucs):.4f}")
print(f"Mean Accuracy: {np.mean(val_accs):.4f}")
print(f" Mean F1 Score: {np.mean(val_f1s):.4f}")

### Save model and encoders
model_path = os.path.join(OUTPUT_DIR, "xgb_nids_model.json")
encoders_path = os.path.join(OUTPUT_DIR, "ip_encoders.pkl")
metrics_path = os.path.join(OUTPUT_DIR, "chunk_validation_metrics.csv")
importance_path = os.path.join(OUTPUT_DIR, "feature_importance.png")

booster.save_model(model_path)
joblib.dump({'src': le_src, 'dst': le_dst}, encoders_path)

print(f"Model saved to: {model_path}")
print(f"Encoders saved to: {encoders_path}")

# Save validation metrics
metrics_df = pd.DataFrame({
    'Chunk': list(range(1, chunk_id + 1)),
    'AUC': val_aucs,
    'Accuracy': val_accs,
    'F1': val_f1s
})
metrics_df.to_csv(metrics_path, index=False)
print(f"📄 Validation metrics saved to: {metrics_path}")

# Plot Feature Importance
xgb.plot_importance(booster, max_num_features=15, importance_type='gain')
plt.title("Top 15 Features by Gain")
plt.tight_layout()
plt.savefig(importance_path, dpi=300)
plt.show()
print(f"Feature importance plot saved to: {importance_path}")
