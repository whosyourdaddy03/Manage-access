#!/usr/bin/env python3
"""
AprilTag 实拍采集助手 —— E3/E3b/E3c/E4 自采数据（卷尺+三脚架）

两种用法:
  A. 摄像头现场采集:  python collect_apriltag.py --cam 0
     按键: 1-6=距离档位(0.5/1/2/3/5/8m)  S=通用录制(光照/模糊/移动)
           M=切换模式  Q=退出
     距离档: 终端输入卷尺实测距离(如 0.52) -> 3秒倒计时 -> 自动录 30s
  B. 手机视频登记:    python collect_apriltag.py --register 视频文件 --distance 2.3
     (手机拍完传电脑后用此命令登记进数据集，meta 会记录真值)

目录组织:
  selfdata/static/dist_0p5m/clip_xxx.mp4 + meta.json   -> E3/E3c
  selfdata/moving/move_xxx.mp4                          -> E3b 预测
  selfdata/light|blur|handheld/                         -> E4 检出率
"""
import argparse
import json
import os
import time

import cv2
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
SELF_DIR = os.path.join(BASE, "selfdata")
META = os.path.join(SELF_DIR, "meta.json")

DIST_TIERS = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0]   # 按键 1-6 对应
DURATION = 30.0                                # 每段录制时长(秒)
TAG_SIZE = 0.16                                # AprilTag 打印实测边长(米)，打印后量！


def load_intrinsics(frame_w, frame_h):
    """读取标定内参；分辨率不匹配时降级警告"""
    path = os.path.join(BASE, "calibration", "intrinsics.json")
    if not os.path.exists(path):
        print("[!] 尚未标定: 先运行 calibrate_camera.py，测距值仅供参考组织数据")
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    w, h = d["image_size"]
    if (w, h) != (frame_w, frame_h):
        print(f"[!] 内参分辨率 {w}x{h} 与当前 {frame_w}x{frame_h} 不一致，"
              f"叠加的测距值不可信（仅影响预览，不影响保存）")
    K = np.array(d["camera_matrix"])
    dist = np.array(d["dist_coeffs"])
    return K, dist


def make_detector():
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(aruco_dict, params)


def tag_pose(corners, K, dist):
    """返回 (dist_m, azim_deg) 或 None"""
    obj = np.array([[-TAG_SIZE/2, -TAG_SIZE/2, 0], [TAG_SIZE/2, -TAG_SIZE/2, 0],
                    [TAG_SIZE/2,  TAG_SIZE/2, 0], [-TAG_SIZE/2,  TAG_SIZE/2, 0]],
                   dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, corners[0][0].astype(np.float64), K, dist)
    if not ok:
        return None
    x, y, z = tvec.flatten()
    return float(np.linalg.norm([x, y, z])), float(np.degrees(np.arctan2(x, z)))


def save_meta(entry):
    os.makedirs(SELF_DIR, exist_ok=True)
    meta = []
    if os.path.exists(META):
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)
    meta.append(entry)
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def record_clip(cap, out_path, K, dist, detector):
    """录制 DURATION 秒，叠加检测状态，返回 (保存?, 有效帧数, 总帧数)"""
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fps = min(max(fps_in, 15.0), 60.0)
    n_valid = 0
    n_total = 0
    t0 = time.time()
    ok, frame = cap.read()
    vw = None
    while ok and time.time() - t0 < DURATION:
        n_total += 1
        if vw is None:
            vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps, (frame.shape[1], frame.shape[0]))
        disp = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is not None and len(ids) > 0:
            n_valid += 1
            cv2.aruco.drawDetectedMarkers(disp, corners, ids)
            if K is not None:
                p = tag_pose(corners, K, dist)
                if p:
                    cv2.putText(disp, f"z={p[0]:.2f}m az={p[1]:.1f}deg",
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        left = DURATION - (time.time() - t0)
        cv2.putText(disp, f"REC {left:4.1f}s  valid {n_valid}/{n_total}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        vw.write(disp)
        cv2.imshow("collecting", disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        ok, frame = cap.read()
    if vw:
        vw.release()
    return n_total, n_valid


def live_mode(cam_id, width, height):
    cap = cv2.VideoCapture(cam_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    ok, frame = cap.read()
    if not ok:
        print("[!] 摄像头打开失败")
        return
    h, w = frame.shape[:2]
    Kd = load_intrinsics(w, h)
    K, dist = Kd if Kd else (None, None)
    detector = make_detector()
    mode = "static"
    print(f"\n当前模式: {mode} | 分辨率 {w}x{h}")
    print("按键: 1-6=距离档  S=通用录制  M=切模式  Q=退出")

    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        disp = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        status = "no tag"
        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(disp, corners, ids)
            if K is not None:
                p = tag_pose(corners, K, dist)
                if p:
                    status = f"z={p[0]:.2f}m az={p[1]:.1f}deg"
            else:
                status = "tag OK (未标定)"
        cv2.putText(disp, f"{status}   mode={mode}   1-6=dist S=rec M=mode Q=quit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    (0, 255, 0) if "no" not in status else (0, 0, 255), 2)
        cv2.imshow("collect (live)", disp)
        k = cv2.waitKey(1) & 0xFF

        if k in (ord("q"), ord("Q"), 27):
            break
        elif k in (ord("m"), ord("M")):
            order = ["static", "moving", "light", "blur", "handheld"]
            mode = order[(order.index(mode) + 1) % len(order)]
            print(f"模式 -> {mode}")
        elif ord("1") <= k <= ord("6") or k in (ord("s"), ord("S")):
            if ord("1") <= k <= ord("6"):
                if mode not in ("static",):
                    mode = "static"
                    print("模式 -> static")
                nominal = DIST_TIERS[k - ord("1")]
                raw = input(f"卷尺实测距离(米, 回车={nominal}): ").strip()
                true_d = float(raw) if raw else nominal
                label = f"dist_{str(nominal).replace('.', 'p')}m"
                meta_extra = {"true_distance_m": true_d, "nominal_m": nominal}
            else:
                label = input("标签(如 night/handheld/move01): ").strip() or "clip"
                meta_extra = {}
            # 3 秒倒计时（给你回到三脚架/摆好姿势）
            t_end = time.time() + 3
            while time.time() < t_end:
                ok, frame = cap.read()
                if ok:
                    d = cv2.putText(frame.copy(), f"START IN {t_end - time.time():.0f}",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                    cv2.imshow("collect (live)", d)
                cv2.waitKey(1)
            out_dir = os.path.join(SELF_DIR, mode)
            os.makedirs(out_dir, exist_ok=True)
            idx += 1
            out_path = os.path.join(out_dir, f"{label}_{time.strftime('%H%M%S')}.mp4")
            print(f"录制中 -> {out_path}")
            n_total, n_valid = record_clip(cap, out_path, K, dist, detector)
            ratio = n_valid / max(n_total, 1)
            print(f"完成: 有效帧率 {ratio:.0%} ({n_valid}/{n_total})")
            if ratio < 0.5:
                print("[!] 有效帧率过低，建议检查光照/距离后重录")
            save_meta({"file": os.path.relpath(out_path, BASE),
                       "mode": mode, "label": label, "width": w, "height": h,
                       "created": time.strftime("%Y-%m-%d %H:%M:%S"), **meta_extra})
            print("[OK] 已登记 meta.json")
    cap.release()
    cv2.destroyAllWindows()


def register_mode(video, distance, mode, label):
    if not os.path.exists(video):
        print(f"[!] 文件不存在: {video}")
        return
    cap = cv2.VideoCapture(video)
    ok, frame = cap.read()
    if not ok:
        print("[!] 视频无法读取")
        return
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    out_dir = os.path.join(SELF_DIR, mode)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.basename(video))
    if os.path.abspath(video) != os.path.abspath(dst):
        os.replace(video, dst)
    save_meta({"file": os.path.relpath(dst, BASE), "mode": mode, "label": label or mode,
               "width": w, "height": h, "fps": fps, "frames": frames,
               "true_distance_m": distance,
               "created": time.strftime("%Y-%m-%d %H:%M:%S")})
    print(f"[OK] 已登记: {dst} ({w}x{h}@{fps:.0f}fps, {frames}帧, 距离={distance}m)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", type=int, default=None)
    ap.add_argument("--register", type=str, default=None, help="登记已拍摄的视频文件")
    ap.add_argument("--distance", type=float, default=None, help="--register 时的实测距离")
    ap.add_argument("--mode", type=str, default="static",
                    choices=["static", "moving", "light", "blur", "handheld"])
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    if args.register:
        register_mode(args.register, args.distance, args.mode, None)
    elif args.cam is not None:
        live_mode(args.cam, args.width, args.height)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
