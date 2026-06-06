import os
import cv2
import mediapipe as mp
import numpy as np
import pandas as pd


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
        img,
        matrix,
        (w, h),
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

    x1 = max(x, 0)
    y1 = max(y, 0)
    x2 = min(x + w, W)
    y2 = min(y + h, H)

    fg_x1 = x1 - x
    fg_y1 = y1 - y
    fg_x2 = fg_x1 + (x2 - x1)
    fg_y2 = fg_y1 + (y2 - y1)

    fg_crop = fg[fg_y1:fg_y2, fg_x1:fg_x2]

    alpha = fg_crop[:, :, 3] / 255.0

    for c in range(3):
        bg[y1:y2, x1:x2, c] = (
            alpha * fg_crop[:, :, c]
            + (1 - alpha) * bg[y1:y2, x1:x2, c]
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
# PLACEMENT
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

        bl_y = int(b1.y * H)
        br_y = int(b2.y * H)

        shoulder_y = (ly + ry) / 2
        hip_y = (bl_y + br_y) / 2

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

def apply_look(
    user_image_path: str,
    artist_name: str,
    output_path: str,
    csv_path: str,
    asset_dir: str,
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

    print(f"[clothing] Artist: {artist_name}")
    print(f"[clothing] Signature look: {signature}")

    H, W = img.shape[:2]

    mp_face = mp.solutions.face_mesh
    mp_pose = mp.solutions.pose

    with mp_face.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
    ) as face_mesh, mp_pose.Pose(
        static_image_mode=True,
    ) as pose:

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        face_result = face_mesh.process(rgb)
        pose_result = pose.process(rgb)

        face_landmarks = None
        if face_result.multi_face_landmarks:
            face_landmarks = face_result.multi_face_landmarks[0].landmark

        pose_landmarks = pose_result.pose_landmarks

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
