# Supervised Machine Learning Model for DLP Incident Severity Classification

This plan outlines the design and implementation of a supervised machine learning pipeline to classify Netskope email DLP incidents based on `BIN_001` labeled data.

## User Review Required

> [!IMPORTANT]
> The project plan mandates a **High-severity false negatives rate < 5%**. In our validation step, we will compute this specific metric (i.e., the percentage of actual `HIGH`/`CRITICAL` severity incidents that were incorrectly classified as `MEDIUM`/`LOW` severity by the model) and compare Logistic Regression against Random Forest to select the safest model.

## Proposed Changes

We will create a virtual environment, install the required libraries, and create a training script `src/train.py` to build the model.

---

### Component: Environment & Dependencies

We will initialize a virtual environment `venv` inside the project directory and install the necessary dependencies: `pandas`, `scikit-learn`, and `joblib`.

#### [NEW] [requirements.txt](file:///d:/DLP-ML-Training/requirements.txt)
Create a `requirements.txt` file listing:
* `pandas`
* `scikit-learn`
* `joblib`

---

### Component: Machine Learning Pipeline

We will implement the training script, which maps features to the analyst-assigned labels, runs model selection, evaluates predictions, and saves the trained model artifacts.

#### [NEW] [train.py](file:///d:/DLP-ML-Training/src/train.py)
A Python script that:
1. Loads the clustered incident data from `bins/bin_001/bin_001_clustered_final.json`.
2. Loads the analyst labels from `bins/bin_001/bin_001_labels.json`.
3. Performs a data merge/join:
   * Maps each event to its label attributes (`severity`, `allowed_behavior`, `policy_alignment`) based on `sub_bin_id`.
   * Implements a fallback logic: if `sub_bin_id` is missing, is `BIN_001_EDGE_RARE`, or has no direct label entry, it falls back to the default label config for `bin_id = BIN_001` found in the labels file.
4. Prepares features and targets:
   * **Features**: `sender_username_length`, `sender_username_entropy`, `receiver_domain_frequency`, `policy_encoded`.
   * **Target**: `severity` (we can also train separate classifiers or predict multiple columns if needed, but `severity` is the primary target).
5. Splits the dataset into 80% train and 20% test.
6. Scales the features using `StandardScaler`.
7. Trains two models:
   * **Logistic Regression**
   * **Random Forest Classifier**
8. Evaluates both models on the test split:
   * Calculates Accuracy, Precision, Recall, and F1-score.
   * Calculates the **High-severity false negative rate** (percentage of actual high-severity cases predicted as non-high).
9. Selects and saves the best model and scaler to the `models/` directory.

---

## Verification Plan

### Automated Tests
We will run the training script from the virtual environment and review the output logs:
```bash
venv/Scripts/python src/train.py
```
This will print model evaluation metrics and confirm whether we met the success criteria:
* Accuracy $\ge 80\%$
* High-severity false negatives $< 5\%$

### Manual Verification
* Verify that the trained model (`models/severity_model.joblib`) and scaler (`models/scaler.joblib`) are successfully saved to the disk.
* Compile the metrics in `walkthrough.md`.
