#!/usr/bin/env python3
"""
棋盘格相机内参标定 —— Z=f·D/w 测距与角度反解的前提（论文第4章）

用法（在 code 目录下，任选一条路径）:
  1) 生成可打印棋盘格:   python calibrate_camera.py --gen-board
  2) 摄像头现场采集+标定: python calibrate_camera.py --cam 0
     操作: SPACE=抓拍  C=标定(需>=12张)  Q=退出
  3) 用已拍图片目录标定:  python calibrate_camera.py --imgs calib_imgs

输出: calibration/intrinsics.json  (K/dist/分辨率/重投影误差)
注意: 标定分辨率必须与后续采集/评测的分辨率一致，否则内参无效。
"""
import argparse
import json
import os
import time

import cv2
import numpy as np

# 棋盘格规格：内角点 9x6，方格边长 2.5cm（打印后用卷尺量一遍，改这里）
BOARD_COLS, BOARD_ROWS = 9, 6
SQUARE_M = 0.025

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(BASE, "calibration", "intrinsics.json")
IMG_DIR = os.path.join(BASE, "calib_imgs")


def gen_board(out_path):
    """生成 A4 可打印棋盘格：10x7 个方格（对应 9x6 内角点），25mm/格"""
    px_per_mm = 10  # 10px/mm，打印时选"实际大小/100%"即得 25mm 方格
    cols, rows = BOARD_COLS + 1, BOARD_ROWS + 1  # 10 x 7 方格
    w, h = cols * 25 * px_per_mm, rows * 25 * px_per_mm  # 2500 x 1750
    board = np.zeros((h, w), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                y0, x0 = r * 25 * px_per_mm, c * 25 * px_per_mm
                board[y0:y0 + 25 * px_per_mm, x0:x0 + 25 * px_per_mm] = 255
    cv2.imwrite(out_path, board)
    print(f"棋盘格已保存: {out_path}")
    print(f"打印要求: A4 竖向、缩放 100%（不要'适应页面'），打印后用卷尺量")
    print(f"方格边长应为 25mm，若不同请修改脚本顶部 SQUARE_M 后重新标定")


def detect_corners(gray):
    pattern = (BOARD_COLS, BOARD_ROWS)
    ok, corners = cv2.findChessboardCorners(
        gray, pattern, cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None
    corners = cv2.cornerSubPix(
        gray, corners, (11, 11), (-1, -1),
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3))
    return corners


def calibrate(images, size):
    """images: list of BGR images -> (rms, K, dist)"""
    objp = np.zeros((BOARD_COLS * BOARD_ROWS, 3), np.float32)
    objp[:, :2] = np.mgrid[0:BOARD_COLS, 0:BOARD_ROWS].T.reshape(-1, 2) * SQUARE_M
    obj_points, img_points = [], []
    for im in images:
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        corners = detect_corners(gray)
        if corners is None:
            continue
        obj_points.append(objp)
        img_points.append(corners)
    n = len(obj_points)
    if n < 12:
        print(f"[!] 有效角点图仅 {n} 张（需>=12），变换角度多拍几张")
        return None
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, size, None, None)
    # 逐帧重投影误差分布
    per_view = []
    for op, ip, rv, tv in zip(obj_points, img_points, rvecs, tvecs):
        proj, _ = cv2.projectPoints(op, rv, tv, K, dist)
        per_view.append(float(np.linalg.norm(proj.reshape(-1, 2) -
                                             ip.reshape(-1, 2), axis=1).mean()))
    print(f"\n=== 标定结果（{n} 张图, {size[0]}x{size[1]}）===")
    print(f"重投影 RMS : {rms:.4f} px  (良好 <0.5, 可接受 <1.0)")
    print(f"fx = {K[0, 0]:.2f}   fy = {K[1, 1]:.2f}")
    print(f"cx = {K[0, 2]:.2f}   cy = {K[1, 2]:.2f}")
    print(f"畸变系数   : {np.ravel(dist)[:5].round(5).tolist()}")
    print(f"单帧误差范围: {min(per_view):.2f} ~ {max(per_view):.2f} px")
    return rms, K, dist, n, per_view


def save(rms, K, dist, size, n_imgs, source):
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    data = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "board": {"cols": BOARD_COLS, "rows": BOARD_ROWS, "square_m": SQUARE_M},
        "image_size": [int(size[0]), int(size[1])],
        "rms_px": float(rms),
        "n_images": int(n_imgs),
        "camera_matrix": K.tolist(),
        "dist_coeffs": np.ravel(dist)[:8].tolist(),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[OK] 内参已保存: {OUT_JSON}")
    print("后续 collect_apriltag.py / eval_localization.py 会自动读取。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-board", action="store_true", help="生成打印棋盘格")
    ap.add_argument("--cam", type=int, default=None, help="摄像头编号，现场采集+标定")
    ap.add_argument("--imgs", type=str, default=None, help="从图片目录标定")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    if args.gen_board:
        gen_board(os.path.join(BASE, "chessboard_9x6_25mm.png"))
        return
    if args.imgs:
        files = sorted(f for f in os.listdir(args.imgs)
                       if f.lower().endswith((".jpg", ".png", ".jpeg")))
        imgs = [cv2.imread(os.path.join(args.imgs, f)) for f in files]
        imgs = [im for im in imgs if im is not None]
        if not imgs:
            print(f"[!] {args.imgs} 中没有图片")
            return
        size = (imgs[0].shape[1], imgs[0].shape[0])
        res = calibrate(imgs, size)
        if res:
            save(res[0], res[1], res[2], size, res[3], f"images:{args.imgs}")
        return
    if args.cam is not None:
        cap = cv2.VideoCapture(args.cam)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        grabbed = []
        os.makedirs(IMG_DIR, exist_ok=True)
        print("操作: SPACE=抓拍  C=标定  Q=退出  （目标>=12张，角度多变化）")
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners = detect_corners(gray)
            disp = frame.copy()
            if corners is not None:
                cv2.drawChessboardCorners(disp, (BOARD_COLS, BOARD_ROWS), corners, True)
                cv2.putText(disp, f"corners OK  grabbed={len(grabbed)}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(disp, f"no board  grabbed={len(grabbed)}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("calibration (SPACE=grab C=calib Q=quit)", disp)
            k = cv2.waitKey(1) & 0xFF
            if k == ord(" ") and corners is not None:
                grabbed.append(frame.copy())
                cv2.imwrite(os.path.join(IMG_DIR, f"calib_{len(grabbed):02d}.jpg"), frame)
                print(f"  抓拍第 {len(grabbed)} 张")
            elif k in (ord("c"), ord("C")):
                if grabbed:
                    size = (grabbed[0].shape[1], grabbed[0].shape[0])
                    res = calibrate(grabbed, size)
                    if res:
                        save(res[0], res[1], res[2], size, res[3], f"cam{args.cam}")
            elif k in (ord("q"), ord("Q"), 27):
                break
        cap.release()
        cv2.destroyAllWindows()
        return
    ap.print_help()


if __name__ == "__main__":
    main()
