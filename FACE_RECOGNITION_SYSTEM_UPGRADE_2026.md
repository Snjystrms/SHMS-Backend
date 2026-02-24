## Face Recognition System Upgrade Plan (2026)

### 1. Objective

This document outlines the upgrade of the current face recognition pipeline from the existing **FaceNet-based** architecture to a modern **2026 industry‑standard InsightFace ecosystem**.  
The purpose of this upgrade is to improve **accuracy**, **speed**, **robustness to side‑profiles**, and **scalability** for real‑world deployment.

---

### 2. Proposed 2026 Technology Stack

| Component                 | New (2026 Upgrade Path) | Reason for Upgrade                                      |
|---------------------------|-------------------------|---------------------------------------------------------|
| **Primary Framework**     | InsightFace             | Current SOTA for deep face analysis                     |
| **Object Detection**      | YOLO26n                 | ~43% faster with NMS‑free inference                     |
| **Face Detection**        | RetinaFace              | Higher landmark accuracy and better side‑profile detection |
| **Recognition Model**     | ArcFace (Buffalo_L)     | Higher recognition accuracy (~99.83%)                   |
| **Backbone Architecture** | IResNet100 / ResNet50   | Better feature discrimination in crowded scenes         |

---

### 3. Existing System (Current Flow – FaceNet Based)

The current implementation already uses a **two‑stage detection** approach where YOLO first filters humans before face recognition begins.

1. Camera captures image  
2. YOLOv8 detects all objects and filters only humans (`person` class)  
3. Human regions are passed to MTCNN  
4. MTCNN detects and aligns faces inside each person box  
5. FaceNet generates embeddings  
6. Embeddings are stored in the database  
7. New image → embeddings generated → compared using distance threshold  
8. Match / No Match decision

**Limitations:**

- Weak side‑face detection  
- Lower accuracy in crowded environments  
- Slow for large‑scale multi‑camera usage  
- Sensitive to lighting and pose  

---

### 4. New System Architecture (InsightFace Based)

The upgraded system introduces a two‑stage pipeline: **Human Detection + Face Recognition**.

#### Step 1 – Human Filtering (Object Detection)

YOLO26 will first scan the frame and filter only human subjects from the scene.

- **Purpose:**  
  - Improve processing speed  
  - Reduce unnecessary face detection calls  

#### Step 2 – Face Detection

From detected humans, the InsightFace **RetinaFace** model will:

- Detect faces  
- Identify facial landmarks (eyes, nose, mouth alignment)  
- Normalize face orientation  

#### Step 3 – Feature Extraction (Embeddings Generation)

**ArcFace (Buffalo_L)** will:

- Generate **512‑dimensional embeddings** (face signature)  
- Produce pose‑invariant identity representation  

#### Step 4 – Database Storage

The generated embeddings will be stored in a **Neon PostgreSQL embeddings storage**:

- Each person = unique embedding signature  
- Multiple samples can be stored for better robustness  

#### Step 5 – Recognition / Matching

When a person is scanned again:

1. A new embedding is generated  
2. Compared against stored embeddings  
3. Cosine similarity score is calculated  
4. Highest similarity determines identity  

**Output:**

- Match Found (Identity Verified)  
- Unknown Person  
- Confidence Score (Recognition Accuracy)  

---

### 5. New Recognition Flow (End‑to‑End Pipeline)

**Pipeline:**

Camera Frame  
→ YOLO26 Human Detection  
→ Crop Human Regions  
→ RetinaFace Face Detection  
→ Face Alignment  
→ ArcFace Embedding Generation  
→ Save / Compare with Database  
→ Identity + Accuracy Score  

---

### 6. Expected Improvements

| Feature                 | Old System                 | New System                       |
|-------------------------|----------------------------|----------------------------------|
| **Accuracy**            | ~97%                       | ~99.8%                           |
| **Side‑Face Detection** | Weak                       | Strong                           |
| **Speed**               | Moderate                   | High (GPU‑optimized)             |
| **Multi‑Person Scenes** | Unstable                   | Stable                           |
| **False Positives**     | Higher                     | Very Low                         |
| **Scalability**         | Limited                    | Production‑grade                 |

---

### 7. Conclusion

The migration from **FaceNet** to **InsightFace** with **YOLO26** pre‑filtering converts the system from a basic recognition solution into a **production‑level biometric identification system** suitable for:

- Surveillance  
- Attendance  
- Maritime crew verification  
- Large‑scale identity tracking environments  

---

### 8. New Processing Flow (2026) – Detailed Pipeline

#### Step 1 – Initial Human Detection (YOLO26)

- **Input:** Raw image frame  
- **Process:** YOLO26 scans entire frame  
- **Filtering:** Keeps only human class detections  
- **Purpose:** Remove background objects before face processing  
- **Output:** Clean person bounding boxes  

#### Step 2 – Face Detection & Alignment (RetinaFace – InsightFace)

- **Input:** Person bounding boxes from YOLO26  
- **Process:** RetinaFace detects face inside each person region  
- **Capabilities:**  
  - Multi‑angle detection (front, side, tilted)  
  - Landmark detection (eyes, nose, mouth)  
  - Automatic alignment  
- **Output:** Normalized face crops  

#### Step 3 – Face Embedding Generation (ArcFace – Buffalo_L)

- **Input:** Aligned face images  
- **Process:** ArcFace converts face into a **512‑dimensional identity vector**  
- **Output:** Robust face embeddings (pose & lighting invariant)  

#### Step 4 – Embedding Storage (Neon PostgreSQL Embeddings Storage)

- Store embeddings as unique identity signatures  
- Allow multiple embeddings per person  
- Enable high‑accuracy matching in future scans  

#### Step 5 – Face Recognition / Matching

- New image captured  
- New embedding generated  
- Embedding is **L2‑normalized** and compared against normalized database embeddings using **dot‑product similarity** (equivalent to cosine on normalized vectors)  
- An **Approximate Nearest Neighbor (ANN) index** (e.g., HNSW / IVF in Neon `pgvector`) is used instead of brute‑force scanning to reduce latency at scale  

**Decision Logic:**

- Highest‑score neighbor above threshold → Identified Person  
- No neighbor above threshold → Unknown Person  
 - Confidence score returned  

#### Visual Flow Diagram

Input Frame  
↓  
[YOLO26] → Detect humans only  
↓  
[Human Regions]  
↓  
[RetinaFace] → Detect & align face  
↓  
[ArcFace] → Generate embedding (512D vector)  
↓  
[Neon PostgreSQL embeddings storage] → Save / Compare  
↓  
[Similarity Engine]  
↓  
[Result] → Identity + Confidence Score  

---

### 9. Licensing & Commercial Usage Considerations

| Component                                | License Type                         | Commercial Use Notes                                                                                     |
|------------------------------------------|--------------------------------------|----------------------------------------------------------------------------------------------------------|
| **InsightFace Framework**                | MIT License                          | Free to use in commercial applications                                                                  |
| **InsightFace Pretrained Models** (e.g., `buffalo_l`) | Research / Non‑Commercial (default) | Commercial deployment may require a separate license or commercially‑permitted weights                   |
| **Ultralytics YOLO** (YOLOv8 / YOLO26 family) | AGPL‑3.0                        | Closed‑source or SaaS deployment may require an enterprise license                                      |
| **RetinaFace Model**                     | Depends on distributed weights       | Generally allowed when using properly licensed weights; verify specific model/weights license terms      |
| **ArcFace Embeddings / Models**         | Model‑dependent                      | Commercial use depends on the dataset and model weights license                                         |

**Important Note:**  
The software frameworks are typically open‑source, but **pretrained weights can carry additional usage restrictions**.  
For **production deployment**, only use **commercially permitted weights** or obtain appropriate **commercial licenses** where required.

