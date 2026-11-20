"""NXTSTEP Placement Prediction Model Training Pipeline.

Dataset: Krooz/Campus_Recruitment_CSV (10,000 campus recruitment records)
Target: PlacementStatus ('Placed' = 1, 'NotPlaced' = 0)

Reproducible ML pipeline:
- Stratified 80/20 train/test split (random_state=42)
- Scikit-Learn ColumnTransformer:
    * Numerical: SimpleImputer(median) + StandardScaler
    * Categorical: SimpleImputer(most_frequent) + OneHotEncoder(ignore)
- 5-fold Stratified CV comparing LogisticRegression vs. RandomForestClassifier
- Model selection based on validation ROC-AUC (with Brier score tie-breaker)
- Held-out evaluation on untouched test split
- Complete pipeline serialization to backend/ml/artifacts/placement_model.joblib
"""

import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_predict,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Paths
BASE_DIR = Path(__file__).resolve().parent  # backend/ml/
DATA_PATH = BASE_DIR / "data" / "Campus_Recruitment.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "placement_model.joblib"

NUMERICAL_FEATURES = [
    "CGPA",
    "Internships",
    "Projects",
    "Workshops/Certifications",
    "AptitudeTestScore",
    "SoftSkillsRating",
    "SSC_Marks",
    "HSC_Marks",
]

CATEGORICAL_FEATURES = [
    "ExtracurricularActivities",
    "PlacementTraining",
]

TARGET_COLUMN = "PlacementStatus"


def load_dataset(csv_path: Path) -> pd.DataFrame:
    """Load and validate the campus recruitment dataset."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {csv_path}. Please download the dataset first."
        )

    df = pd.read_csv(csv_path)

    # Validate essential columns
    expected_cols = set(NUMERICAL_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN])
    actual_cols = set(df.columns)
    missing = expected_cols - actual_cols
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}")

    return df


def build_preprocessor() -> ColumnTransformer:
    """Construct Scikit-Learn preprocessing pipeline for numerical and categorical features."""
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", num_pipeline, NUMERICAL_FEATURES),
            ("cat", cat_pipeline, CATEGORICAL_FEATURES),
        ]
    )


def train_and_evaluate() -> dict[str, Any]:
    """Execute training, model selection, evaluation, and serialization."""
    print("=" * 70)
    print("NXTSTEP ML TRAINING PIPELINE — CAMPUS RECRUITMENT CLASSIFIER")
    print("=" * 70)

    # 1. Load data
    print(f"\n[1/7] Loading dataset from: {DATA_PATH}")
    df = load_dataset(DATA_PATH)
    print(f"      Total records loaded: {df.shape[0]} rows, {df.shape[1]} columns")

    # Drop StudentID if present
    if "StudentID" in df.columns:
        df = df.drop(columns=["StudentID"])
        print("      Dropped StudentID (non-predictive identifier).")

    # Check class distribution
    class_counts = df[TARGET_COLUMN].value_counts()
    class_props = df[TARGET_COLUMN].value_counts(normalize=True) * 100
    print("\n      Class Distribution:")
    for label, count in class_counts.items():
        print(f"       - {label}: {count} ({class_props[label]:.2f}%)")

    # 2. Separate features and target
    X = df[NUMERICAL_FEATURES + CATEGORICAL_FEATURES]
    y = (df[TARGET_COLUMN].astype(str).str.strip() == "Placed").astype(int)

    # 3. Stratified 80/20 train/test split
    print("\n[2/7] Splitting data into 80/20 Stratified Train/Test sets (random_state=42)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"      Training set size:   {X_train.shape[0]} rows")
    print(f"      Held-out test size: {X_test.shape[0]} rows")

    # 4. Construct pipelines for candidate models
    print("\n[3/7] Building candidate Scikit-Learn pipelines...")
    preprocessor = build_preprocessor()

    candidates = {
        "LogisticRegression": Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]),
        "RandomForestClassifier": Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_split=10,
                random_state=42,
            )),
        ]),
    }

    # 5. 5-Fold Stratified Cross-Validation on training split
    print("\n[4/7] Performing 5-Fold Stratified Cross-Validation on training split...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = {}

    for name, pipeline in candidates.items():
        # ROC-AUC CV scores
        roc_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="roc_auc")
        mean_roc = float(np.mean(roc_scores))
        std_roc = float(np.std(roc_scores))

        # Out-of-fold predicted probabilities for Brier score
        oof_probs = cross_val_predict(
            pipeline, X_train, y_train, cv=cv, method="predict_proba"
        )[:, 1]
        brier = float(brier_score_loss(y_train, oof_probs))

        cv_results[name] = {
            "mean_roc_auc": mean_roc,
            "std_roc_auc": std_roc,
            "brier_score": brier,
            "pipeline": pipeline,
        }

        print(f"      [{name}]")
        print(f"       - CV ROC-AUC:    {mean_roc:.4f} (+/- {std_roc:.4f})")
        print(f"       - CV Brier Score: {brier:.4f} (lower is better)")

    # Model selection: Higher ROC-AUC wins; if within 0.0001, lower Brier score wins
    names = list(candidates.keys())
    m1, m2 = names[0], names[1]
    auc1, auc2 = cv_results[m1]["mean_roc_auc"], cv_results[m2]["mean_roc_auc"]
    brier1, brier2 = cv_results[m1]["brier_score"], cv_results[m2]["brier_score"]

    if abs(auc1 - auc2) < 0.0001:
        selected_name = m1 if brier1 <= brier2 else m2
        reason = f"Tie-break on Brier score ({cv_results[selected_name]['brier_score']:.4f})"
    elif auc1 > auc2:
        selected_name = m1
        reason = f"Higher validation ROC-AUC ({auc1:.4f} vs {auc2:.4f})"
    else:
        selected_name = m2
        reason = f"Higher validation ROC-AUC ({auc2:.4f} vs {auc1:.4f})"

    print(f"\n      >>> Selected Model: {selected_name} ({reason})")

    # 6. Fit winning model on full training split and evaluate on untouched test split
    print(f"\n[5/7] Fitting {selected_name} on entire training split (8,000 samples)...")
    best_pipeline = cv_results[selected_name]["pipeline"]
    best_pipeline.fit(X_train, y_train)

    print("\n[6/7] Evaluating selected model on untouched held-out test split (2,000 samples)...")
    y_pred = best_pipeline.predict(X_test)
    y_prob = best_pipeline.predict_proba(X_test)[:, 1]

    test_accuracy = float(accuracy_score(y_test, y_pred))
    test_roc_auc = float(roc_auc_score(y_test, y_prob))
    test_precision = float(precision_score(y_test, y_pred, zero_division=0))
    test_recall = float(recall_score(y_test, y_pred, zero_division=0))
    test_f1 = float(f1_score(y_test, y_pred, zero_division=0))
    test_brier = float(brier_score_loss(y_test, y_prob))
    cm = confusion_matrix(y_test, y_pred)

    print("\n      " + "-" * 50)
    print("      HELD-OUT TEST PERFORMANCE METRICS (UNTOUCHED SPLIT)")
    print("      " + "-" * 50)
    print(f"      Accuracy:        {test_accuracy:.4f} ({test_accuracy * 100:.2f}%)")
    print(f"      ROC-AUC Score:   {test_roc_auc:.4f}")
    print(f"      Precision:       {test_precision:.4f}")
    print(f"      Recall:          {test_recall:.4f}")
    print(f"      F1-Score:        {test_f1:.4f}")
    print(f"      Brier Score:     {test_brier:.4f}")
    print("\n      Confusion Matrix:")
    print(f"       - True Negatives  (NotPlaced correctly): {cm[0][0]}")
    print(f"       - False Positives (NotPlaced as Placed):  {cm[0][1]}")
    print(f"       - False Negatives (Placed as NotPlaced):  {cm[1][0]}")
    print(f"       - True Positives  (Placed correctly):    {cm[1][1]}")
    print("\n      Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["NotPlaced", "Placed"], digits=4))

    # 7. Serialize pipeline artifact
    print(f"\n[7/7] Serializing full fitted pipeline to: {MODEL_PATH}")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_pipeline, MODEL_PATH)
    file_size_kb = os.path.getsize(MODEL_PATH) / 1024
    print(f"      Model artifact successfully saved! (Size: {file_size_kb:.1f} KB)")

    # 8. Sanity check: Reload and test predict_proba()
    print("\n[Sanity Check] Verifying joblib artifact loading and probability output...")
    loaded_pipe = joblib.load(MODEL_PATH)
    sample_record = X_test.iloc[:3]
    sample_probs = loaded_pipe.predict_proba(sample_record)

    print("      Loaded pipeline predict_proba output on 3 sample test rows:")
    for idx, (p_not, p_placed) in enumerate(sample_probs):
        actual_label = "Placed" if y_test.iloc[idx] == 1 else "NotPlaced"
        print(f"       Row {idx + 1}: P(NotPlaced)={p_not:.4f}, P(Placed)={p_placed:.4f} | Actual: {actual_label}")

    assert loaded_pipe is not None, "Reloaded model is None"
    assert sample_probs.shape == (3, 2), f"Unexpected shape {sample_probs.shape}"
    assert np.all(sample_probs >= 0.0) and np.all(sample_probs <= 1.0), "Probabilities out of bounds"
    print("      All sanity checks PASSED successfully!")

    print("\n" + "=" * 70)
    print("STAGE 1 ML TRAINING PIPELINE EXECUTION COMPLETED")
    print("=" * 70)

    return {
        "dataset_shape": df.shape,
        "selected_model": selected_name,
        "selection_reason": reason,
        "cv_results": cv_results,
        "test_metrics": {
            "accuracy": test_accuracy,
            "roc_auc": test_roc_auc,
            "precision": test_precision,
            "recall": test_recall,
            "f1": test_f1,
            "brier_score": test_brier,
            "confusion_matrix": cm.tolist(),
        },
        "artifact_path": str(MODEL_PATH),
        "artifact_size_kb": file_size_kb,
    }


if __name__ == "__main__":
    train_and_evaluate()
