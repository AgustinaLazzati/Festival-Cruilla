# ==========================================================
# Cruïlla Clothing.py
# Face + Pose overlay system
# Uses CSV artist -> Signature_Look -> asset PNG
# ==========================================================

import os
import cv2
import mediapipe as mp
import numpy as np
import pandas as pd

# ==========================================================
# PATHS
# ==========================================================
BASE_DIR = "/export/hhome/ps2g07/code/Festival-Cruilla"

INPUT_IMAGE = os.path.join(BASE_DIR, "inputs", "Prova1.jpg")
CSV_PATH    = "/export/hhome/ps2g07/code/data/Artistas_Cruilla.csv"

ASSET_DIR   = os.path.join(BASE_DIR, "inputs")
OUTPUT_DIR  = os.path.join(BASE_DIR, "outputs")

OUTPUT_PATH = os.path.join(OUTPUT_DIR, "final_result3.png")

# CHANGE THIS
ARTIST_NAME = "Garbage"


# ==========================================================
# LOAD PNG/JPG
# ==========================================================
def load_asset(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)

    if img is None:
        return None

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)

    if img.shape[2] == 3:
        bgr = img
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)

        bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = alpha
        img = bgra

    return img


# ==========================================================
# OVERLAY
# ==========================================================
def overlay(bg, fg, x, y, w, h):

    fg = cv2.resize(fg, (w, h))

    H, W = bg.shape[:2]

    if x >= W or y >= H:
        return bg

    if x + w <= 0 or y + h <= 0:
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
# CSV LOOKUP
# ==========================================================
def get_signature(artist):

    df = pd.read_csv(CSV_PATH)

    row = df[df["Artist"].str.lower() == artist.lower()]

    if row.empty:
        return None

    return row.iloc[0]["Signature_Look"]


# ==========================================================
# MAP CSV LOOK -> FILE
# ==========================================================
def asset_file(signature):

    return os.path.join(ASSET_DIR, signature + ".png")


# ==========================================================
# MAIN
# ==========================================================
def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    img = cv2.imread(INPUT_IMAGE)

    if img is None:
        print("Cannot open input image")
        return

    H, W = img.shape[:2]

    signature = get_signature(ARTIST_NAME)

    if signature is None:
        print("Artist not found in CSV")
        return

    print("Artist:", ARTIST_NAME)
    print("Look:", signature)

    asset_path = asset_file(signature)

    accessory = load_asset(asset_path)

    if accessory is None:
        print("Missing asset:", asset_path)
        return

    mp_face = mp.solutions.face_mesh
    mp_pose = mp.solutions.pose

    with mp_face.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True
    ) as face_mesh, mp_pose.Pose(
        static_image_mode=True
    ) as pose:

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        face_result = face_mesh.process(rgb)
        pose_result = pose.process(rgb)

        # --------------------------------------------------
        # FACE ITEMS
        # --------------------------------------------------
        if "glasses" in signature or "hat" in signature or "wig" in signature:

            if face_result.multi_face_landmarks:

                face = face_result.multi_face_landmarks[0].landmark

                left_eye = face[33]
                right_eye = face[263]
                forehead = face[10]

                lx = int(left_eye.x * W)
                rx = int(right_eye.x * W)
                ey = int(left_eye.y * H)

                fx = int(forehead.x * W)
                fy = int(forehead.y * H)

                eye_w = abs(rx - lx)

                # Glasses
                if "glasses" in signature:
                    w = int(eye_w * 1.8)
                    h = int(w * 0.45)
                    x = int((lx + rx)/2 - w/2)
                    y = ey - h//2
                    img[:] = overlay(img, accessory, x, y, w, h)

                # Hat / Wig
                else:
                    w = int(eye_w * 2.3)
                    h = int(w * 0.9)
                    x = fx - w//2
                    y = fy - h + 20
                    img[:] = overlay(img, accessory, x, y, w, h)

        # --------------------------------------------------
        # BODY ITEMS
        # --------------------------------------------------
        else:

            if pose_result.pose_landmarks:

                lm = pose_result.pose_landmarks.landmark

                ls = lm[11]
                rs = lm[12]
                lh = lm[23]
                rh = lm[24]

                x1 = int(min(ls.x, rs.x) * W)
                x2 = int(max(ls.x, rs.x) * W)

                y1 = int(min(ls.y, rs.y) * H)
                y2 = int(max(lh.y, rh.y) * H)

                torso_w = x2 - x1
                torso_h = y2 - y1

                w = int(torso_w * 1.8)
                h = int(torso_h * 1.5)

                x = int((x1 + x2)/2 - w/2)
                y = y1 - 20

                img[:] = overlay(img, accessory, x, y, w, h)

    cv2.imwrite(OUTPUT_PATH, img)

    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()