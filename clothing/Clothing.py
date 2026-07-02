import os
import cv2
import mediapipe as mp
import numpy as np
import pandas as pd

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import FaceLandmarker, PoseLandmarker
from mediapipe.tasks.python.vision import (
    FaceLandmarkerOptions,
    PoseLandmarkerOptions,
)
from mediapipe.tasks.python.core.base_options import BaseOptions


# ==========================================================
# MODEL PATHS  — download once and point these at the files
# ==========================================================
_HERE = os.path.dirname(os.path.abspath(__file__))

FACE_MODEL_PATH = os.path.join(_HERE, "models", "face_landmarker.task")
POSE_MODEL_PATH = os.path.join(_HERE, "models", "pose_landmarker_full.task")


# ==========================================================
# ACCESSORY RULES  (unchanged)
# ==========================================================

ACCESSORY_RULES = {
    "glasses": {
        "source": "face",
        "left": 33,
        "right": 263,
        "scale_w": 1.5,
        "shift_y": 0.0,
    },
    "hat": {
        "source": "face",
        "left": 33,
        "right": 263,
        "scale_w": 2.5,
        "shift_y": -0.6,
    },
    "wig": {
        "source": "face",
        "left": 33,
        "right": 263,
        "scale_w": 4.5,
        "shift_y": 0.2,
    },
    "necklace": {
        "source": "pose",
        "mode": "neck",
        "left": 11,
        "right": 12,
        "scale_w": 0.62,
        "shift_x": 0.0,
        "shift_y": 0.05,
        "rot_mult": 0.0,
    },
    "chain": {
        "source": "pose",
        "mode": "neck",
        "left": 11,
        "right": 12,
        "scale_w": 0.75,
        "shift_x": 0.0,
        "shift_y": 0.00,
        "rot_mult": 0.0,
    },
    "scarf": {
        "source": "pose",
        "left": 11,
        "right": 12,
        "scale_w": 0.55,
        "shift_y": 0.10,
        "rot_mult": 0.0,
    },
    "suit": {
        "source": "pose",
        "left": 11,
        "right": 12,
        "bottom_left": 23,
        "bottom_right": 24,
        "scale_h": 1.00,
        "shift_y": 0.25,
        "rot_mult": 0.0,
    },
}


# ==========================================================
# IMAGE HELPERS  (unchanged)
# ==========================================================

def crop_transparent(img):
    if img.shape[2] != 4:
        return img
    alpha = img[:, :, 3]
    coords = cv2.findNonZero(alpha)
    if coords is None:
        return img
    x, y, w, h = cv2.boundingRect(coords)
    return img[y:y + h, x:x + w]


def load_asset(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return crop_transparent(img)


def rotate_image(img, angle):
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img, matrix, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return crop_transparent(rotated)


def overlay(bg, fg, x, y, w, h):
    if w <= 0 or h <= 0:
        return bg
    fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_AREA)
    H, W = bg.shape[:2]
    if x >= W or y >= H or x + w <= 0 or y + h <= 0:
        return bg
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + w, W), min(y + h, H)
    fg_crop = fg[y1 - y:y1 - y + (y2 - y1), x1 - x:x1 - x + (x2 - x1)]
    alpha = fg_crop[:, :, 3] / 255.0
    for c in range(3):
        bg[y1:y2, x1:x2, c] = (
            alpha * fg_crop[:, :, c] + (1 - alpha) * bg[y1:y2, x1:x2, c]
        )
    return bg


# ==========================================================
# CSV + ASSET HELPERS  (unchanged)
# ==========================================================

def get_signature(artist_name, csv_path):
    df = pd.read_csv(csv_path)
    row = df[df["Artist"].str.lower() == artist_name.lower()]
    if row.empty:
        return None
    return row.iloc[0]["Signature_Look"]


def asset_file(signature, asset_dir):
    return os.path.join(asset_dir, signature + ".png")


# ==========================================================
# MODEL DOWNLOAD HELPER
# ==========================================================

def _ensure_models():
    """Download .task model files if not already present."""
    import urllib.request

    models_dir = os.path.join(_HERE, "models")
    os.makedirs(models_dir, exist_ok=True)

    files = {
        FACE_MODEL_PATH: (
            "https://storage.googleapis.com/mediapipe-models/"
            "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
        ),
        POSE_MODEL_PATH: (
            "https://storage.googleapis.com/mediapipe-models/"
            "pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
        ),
    }

    for dest, url in files.items():
        if not os.path.exists(dest):
            print(f"[clothing] Downloading {os.path.basename(dest)}…")
            urllib.request.urlretrieve(url, dest)
            print(f"[clothing] Saved → {dest}")


# ==========================================================
# LANDMARK EXTRACTION  (new task-based API)
# ==========================================================

def _get_landmarks(rgb_image: np.ndarray):
    """
    Returns (face_landmarks, pose_landmarks) using the new Tasks API.
    face_landmarks : list of landmark objects with .x .y (or None)
    pose_landmarks : object with .landmark list (or None)  ← same shape
                     as the old mp.solutions.pose result so placement
                     code below works unchanged.
    """
    _ensure_models()

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

    # ── Face ──────────────────────────────────────────────────────────────
    face_opts = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=FACE_MODEL_PATH),
        num_faces=1,
    )
    with FaceLandmarker.create_from_options(face_opts) as detector:
        face_result = detector.detect(mp_image)

    face_landmarks = None
    if face_result.face_landmarks:
        face_landmarks = face_result.face_landmarks[0]   # list of NormalizedLandmark

    # ── Pose ──────────────────────────────────────────────────────────────
    pose_opts = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=POSE_MODEL_PATH),
    )
    with PoseLandmarker.create_from_options(pose_opts) as detector:
        pose_result = detector.detect(mp_image)

    # Wrap in a simple namespace so placement code can still do
    # pose_landmarks.landmark[idx].x / .y — identical to the old API.
    pose_landmarks = None
    if pose_result.pose_landmarks:
        class _PoseWrap:
            def __init__(self, lm_list):
                self.landmark = lm_list
        pose_landmarks = _PoseWrap(pose_result.pose_landmarks[0])

    return face_landmarks, pose_landmarks


# ==========================================================
# PLACEMENT  (unchanged — works with both old and new landmark objects)
# ==========================================================

def place_accessory_dynamically(img, accessory, rule, face, pose, W, H):
    if rule["source"] == "face":
        if face is None:
            print("[clothing] Face landmarks needed but not found.")
            return img
        lm = face
    elif rule["source"] == "pose":
        if pose is None:
            print("[clothing] Pose landmarks needed but not found.")
            return img
        lm = pose.landmark
    else:
        return img

    p1 = lm[rule["left"]]
    p2 = lm[rule["right"]]

    lx, ly = int(p1.x * W), int(p1.y * H)
    rx, ry = int(p2.x * W), int(p2.y * H)

    raw_angle = np.degrees(np.arctan2(ry - ly, rx - lx))
    angle = raw_angle * rule.get("rot_mult", 1.0)

    acc = rotate_image(accessory, angle)

    asset_h, asset_w = acc.shape[:2]
    aspect = asset_h / asset_w

    if "bottom_left" in rule and "bottom_right" in rule:
        b1 = lm[rule["bottom_left"]]
        b2 = lm[rule["bottom_right"]]
        shoulder_y = (ly + ry) / 2
        hip_y = (int(b1.y * H) + int(b2.y * H)) / 2
        torso_height = abs(hip_y - shoulder_y)
        h = int(torso_height * rule.get("scale_h", 1.0))
        w = int(h / aspect)
    else:
        anchor_dist = abs(rx - lx)
        w = int(anchor_dist * rule["scale_w"])
        h = int(w * aspect)

    cx = (lx + rx) // 2
    cy = (ly + ry) // 2
    shift_x = rule.get("shift_x", 0.0)
    shift_y = rule.get("shift_y", 0.0)
    x = int(cx - w / 2 + w * shift_x)
    y = int(cy - h / 2 + h * shift_y)

    return overlay(img, acc, x, y, w, h)


# ==========================================================
# PIPELINE FUNCTION CALLED FROM main.py 
# ==========================================================

def _save_landmarks(img: np.ndarray, face, pose, path: str) -> None:
    vis = img.copy()
    H, W = vis.shape[:2]
    GREEN = (0, 255, 0)

    if face is not None:
        # Draw face mesh tessellation (connections between landmarks)
        for start_idx, end_idx in mp.solutions.face_mesh.FACEMESH_TESSELATION:
            x1 = int(face[start_idx].x * W); y1 = int(face[start_idx].y * H)
            x2 = int(face[end_idx].x * W);   y2 = int(face[end_idx].y * H)
            cv2.line(vis, (x1, y1), (x2, y2), GREEN, 1)
        # Draw contours on top slightly brighter
        for start_idx, end_idx in mp.solutions.face_mesh.FACEMESH_CONTOURS:
            x1 = int(face[start_idx].x * W); y1 = int(face[start_idx].y * H)
            x2 = int(face[end_idx].x * W);   y2 = int(face[end_idx].y * H)
            cv2.line(vis, (x1, y1), (x2, y2), GREEN, 2)

    if pose is not None:
        # Draw skeleton connections
        for start_idx, end_idx in mp.solutions.pose.POSE_CONNECTIONS:
            x1 = int(pose.landmark[start_idx].x * W); y1 = int(pose.landmark[start_idx].y * H)
            x2 = int(pose.landmark[end_idx].x * W);   y2 = int(pose.landmark[end_idx].y * H)
            cv2.line(vis, (x1, y1), (x2, y2), GREEN, 2)
        # Draw joint dots on top
        for lm in pose.landmark:
            x, y = int(lm.x * W), int(lm.y * H)
            cv2.circle(vis, (x, y), 5, GREEN, -1)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, vis)
    print(f"[clothing] Landmarks saved → {path}")


def apply_look(
    user_image_path: str,
    artist_name: str,
    output_path: str,
    csv_path: str,
    asset_dir: str,
    landmarks_path: str | None = None,
) -> str | None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img = cv2.imread(user_image_path)
    if img is None:
        print(f"[clothing] Cannot open input image: {user_image_path}")
        return None

    signature = get_signature(artist_name, csv_path)
    if signature is None:
        print(f"[clothing] Artist not found in CSV: {artist_name}")
        return None

    signature = str(signature).strip()
    signature_lower = signature.lower()

    asset_path = asset_file(signature, asset_dir)
    accessory = load_asset(asset_path)
    if accessory is None:
        print(f"[clothing] Missing asset: {asset_path}")
        return None

    print(f"[clothing] Artist:         {artist_name}")
    print(f"[clothing] Signature look: {signature}")

    H, W = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    face_landmarks, pose_landmarks = _get_landmarks(rgb)

    if landmarks_path:
        _save_landmarks(img, face_landmarks, pose_landmarks, landmarks_path)

    applied = False
    for key, rule in ACCESSORY_RULES.items():
        if key in signature_lower:
            img = place_accessory_dynamically(
                img=img,
                accessory=accessory,
                rule=rule,
                face=face_landmarks,
                pose=pose_landmarks,
                W=W,
                H=H,
            )
            applied = True
            break

    if not applied:
        print(
            f"[clothing] Unsupported accessory type: {signature}. "
            f"Add a matching keyword to ACCESSORY_RULES."
        )
        return None

    cv2.imwrite(output_path, img)
    print(f"[clothing] Saved: {output_path}")
    return output_path