import os
import random
import unicodedata
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
# ACCESSORY RULES  
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
# IMAGE HELPERS  
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
# CSV + ASSET HELPERS  
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
# RANDOM ACCESSORY SELECTION
# ==========================================================

# Folder name -> placement rule from ACCESSORY_RULES.
# The PNG filename itself no longer needs to contain words such as
# "glasses", "hat" or "necklace" because its folder defines the type.
ACCESSORY_CATEGORIES = {
    "glasses": "glasses",
    "hats": "hat",
    "necklaces": "necklace",
}

# The project currently uses "rock" as the canonical tribe key, while the
# accessory directory in the repository is named "rockstars". Both are accepted.
TRIBE_FOLDER_ALIASES = {
    "indie": "indie",
    "pop": "pop",
    "rock": "rockstars",
    "rockstar": "rockstars",
    "rockstars": "rockstars",
    "tecno": "tecno",
    "techno": "tecno",
    "urban": "urban",
}

# Apply lower accessories first and face accessories last, so glasses are not
# accidentally hidden by another transparent PNG. Selection is still random.
ACCESSORY_OVERLAY_ORDER = {
    "necklaces": 0,
    "hats": 1,
    "glasses": 2,
}

def _normalise_key(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(value).strip())
    return "".join(
        char for char in nfkd if not unicodedata.combining(char)
    ).lower()


def _find_accessories_root(asset_dir: str) -> str | None:
    # The screenshot/project folder uses the misspelling "accesories".
    # Supporting both spellings avoids breaking if it is renamed later.
    for folder_name in ("accesories", "accessories"):
        candidate = os.path.join(asset_dir, folder_name)
        if os.path.isdir(candidate):
            return candidate
    return None


def _png_files(folder: str) -> list[str]:
    return sorted(
        os.path.join(folder, filename)
        for filename in os.listdir(folder)
        if filename.lower().endswith(".png")
        and os.path.isfile(os.path.join(folder, filename))
    )


def select_random_accessories(tribe: str, asset_dir: str) -> list[tuple[str, str, str]]:
    """
    Select two different accessory categories for a tribe, then one random PNG
    from each selected category.

    Returns a list of tuples:
        (category_folder, placement_rule_key, png_path)
    """
    accessories_root = _find_accessories_root(asset_dir)
    if accessories_root is None:
        print(
            f"[clothing] Missing accessories directory inside: {asset_dir}. "
            "Expected 'accesories' or 'accessories'."
        )
        return []

    tribe_key = _normalise_key(tribe)
    tribe_folder_name = TRIBE_FOLDER_ALIASES.get(tribe_key, tribe_key)
    tribe_dir = os.path.join(accessories_root, tribe_folder_name)

    if not os.path.isdir(tribe_dir):
        print(f"[clothing] Missing tribe accessory folder: {tribe_dir}")
        return []

    available = []
    for category_folder, rule_key in ACCESSORY_CATEGORIES.items():
        category_dir = os.path.join(tribe_dir, category_folder)
        if not os.path.isdir(category_dir):
            continue

        pngs = _png_files(category_dir)
        if pngs:
            available.append((category_folder, rule_key, pngs))

    if len(available) < 2:
        found = [category for category, _, _ in available]
        print(
            f"[clothing] Tribe '{tribe}' needs at least two populated accessory "
            f"folders. Found: {found}"
        )
        return []

    chosen_categories = random.sample(available, k=2)
    selected = [
        (category, rule_key, random.choice(pngs))
        for category, rule_key, pngs in chosen_categories
    ]

    # Selection is random; only the compositing order is deterministic.
    selected.sort(key=lambda item: ACCESSORY_OVERLAY_ORDER[item[0]])
    return selected


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
    tribe: str,
    output_path: str,
    asset_dir: str,
    landmarks_path: str | None = None,
) -> str | None:
    """Apply two random, tribe-specific accessories to the same portrait."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    img = cv2.imread(user_image_path)
    if img is None:
        print(f"[clothing] Cannot open input image: {user_image_path}")
        return None

    selected = select_random_accessories(tribe=tribe, asset_dir=asset_dir)
    if len(selected) != 2:
        return None

    # Load both PNGs before changing the portrait. This prevents saving a
    # half-styled result if one selected file is invalid or corrupted.
    loaded_accessories = []
    for category, rule_key, asset_path in selected:
        accessory = load_asset(asset_path)
        if accessory is None:
            print(f"[clothing] Cannot load accessory: {asset_path}")
            return None
        loaded_accessories.append((category, rule_key, asset_path, accessory))

    H, W = img.shape[:2]
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Detect landmarks only once and reuse them for both accessories.
    face_landmarks, pose_landmarks = _get_landmarks(rgb)

    if landmarks_path:
        _save_landmarks(img, face_landmarks, pose_landmarks, landmarks_path)

    # Both chosen accessories must have the landmarks required by their rule.
    for category, rule_key, asset_path, accessory in loaded_accessories:
        rule = ACCESSORY_RULES[rule_key]
        if rule["source"] == "face" and face_landmarks is None:
            print(f"[clothing] Face landmarks required for '{category}' but not found.")
            return None
        if rule["source"] == "pose" and pose_landmarks is None:
            print(f"[clothing] Pose landmarks required for '{category}' but not found.")
            return None

    print(f"[clothing] Tribe: {tribe}")
    for category, rule_key, asset_path, accessory in loaded_accessories:
        print(f"[clothing] Selected {category}: {asset_path}")
        img = place_accessory_dynamically(
            img=img,
            accessory=accessory,
            rule=ACCESSORY_RULES[rule_key],
            face=face_landmarks,
            pose=pose_landmarks,
            W=W,
            H=H,
        )

    if not cv2.imwrite(output_path, img):
        print(f"[clothing] Could not save output image: {output_path}")
        return None

    print(f"[clothing] Saved with two accessories: {output_path}")
    return output_path