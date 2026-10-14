package me.drton.jmavsim;

import javax.vecmath.Matrix3d;
import javax.vecmath.Vector3d;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * 随机航迹四旋翼 —— 论文闭环实验的"目标无人机"（视觉识别对象）。
 * 不跑物理引擎：位置/速度/姿态由 Catmull-Rom 样条轨迹计划直接给定。
 * 世界系：x-北, y-东, z-下（地面 z=0，高度越高 z 越小）。
 *
 * 轨迹特点：
 *   - 10-12 个随机航点, 种子化可复现
 *   - Catmull-Rom 样条插值: 过航点、切线连续、运动平滑
 *   - 每段速度随机 0.5-2.0 m/s（模拟加减速）
 *   - 轨迹循环: 末航点→首航点无缝周期
 *   - 部分航点设计在遮挡物后方(从相机视角被遮挡)
 */
public class ScriptedQuad extends KinematicObject {
    // ---- 随机种子(可复现) ----
    private static final long SEED = 20261008L;

    // ---- 飞行空域(距护航相机(0,-40,-12)约 2-10m) ----
    private static final double X_MIN = -8.0, X_MAX = 8.0;
    private static final double Y_MIN = -30.0, Y_MAX = -38.0;
    private static final double Z_MIN = -15.0, Z_MAX = -9.0;  // z 越小越高

    // ---- 遮挡物定义(与 Simulator.java 中添加的 Obstacle 一致) ----
    // 格式: {centerX, centerY, centerZ, halfX, halfY, halfZ}
    private static final double[][] OBSTACLES = {
        {3.0, -37.0, -12.0, 1.0, 1.0, 2.0},     // 建筑 2x2x4
        {-2.0, -36.5, -11.0, 0.3, 0.3, 1.5},    // 树 0.6x0.6x3
        {5.0, -35.5, -13.0, 0.2, 0.2, 1.75},    // 杆 0.4x0.4x3.5
        {-4.0, -37.5, -12.0, 0.75, 0.75, 1.25},  // 小屋 1.5x1.5x2.5
    };
    private static final double MARGIN = 0.5;  // 航点离遮挡物边界至少留 0.5m
    private static final double OCCLUSION_Y = -36.5;

    // ---- 轨迹参数 ----
    private static final int NUM_WAYPOINTS = 11;
    private static final double SPEED_MIN = 1.0;    // m/s
    private static final double SPEED_MAX = 2.5;    // m/s

    // ---- 生成的航点和段时长 ----
    private final List<Vector3d> waypoints = new ArrayList<>();
    private final List<Double> segmentDurations = new ArrayList<>();
    private double totalDuration = 0.0;  // 秒

    private final Matrix3d rot = new Matrix3d();
    private final Vector3d vel = new Vector3d();
    private long phaseT0 = -1;
    private double lastYaw = 0.0;

    public ScriptedQuad(World world, String modelFile, boolean showGui) {
        super(world, showGui);
        modelFromFile(modelFile);
        generateTrajectory();
    }

    /** 检查点是否在任意遮挡物内部(含安全余量) */
    private boolean isInsideObstacle(Vector3d p) {
        for (double[] o : OBSTACLES) {
            if (Math.abs(p.x - o[0]) < o[3] + MARGIN
                && Math.abs(p.y - o[1]) < o[4] + MARGIN
                && Math.abs(p.z - o[2]) < o[5] + MARGIN) {
                return true;
            }
        }
        return false;
    }

    /**
     * 检查线段 p1→p2 是否穿过任意遮挡物的 XY 包围盒。
     * 用排除法: 如果两端点都不在遮挡物 XY 包围盒的 x/y 范围内, 线段不可能穿过。
     * 简单段-AABB 相交检测: 只检查 XY 平面(z 方向忽略, 因为无人机高度变化小)。
     */
    private boolean segmentCrossesObstacle(Vector3d p1, Vector3d p2) {
        for (double[] o : OBSTACLES) {
            double bxMin = o[0] - o[3] - MARGIN, bxMax = o[0] + o[3] + MARGIN;
            double byMin = o[1] - o[4] - MARGIN, byMax = o[1] + o[4] + MARGIN;
            // 如果任一端点在障碍物 x 范围外且另一端也在同侧, 不相交
            if (Math.max(p1.x, p2.x) < bxMin || Math.min(p1.x, p2.x) > bxMax) continue;
            if (Math.max(p1.y, p2.y) < byMin || Math.min(p1.y, p2.y) > byMax) continue;
            // 两端点的 x/y 区间与障碍物区间重叠 → 可能相交, 做精细检测
            // 求线段与矩形四条边的交点(Slater-Liang 算法简化版)
            double dx = p2.x - p1.x, dy = p2.y - p1.y;
            double t1 = (bxMin - p1.x), t2 = (bxMax - p1.x);
            double t3 = (byMin - p1.y), t4 = (byMax - p1.y);
            double tEnter = Math.max(
                dx > 0 ? t1 / (dx != 0 ? dx : 1e-9) : t2 / (dx != 0 ? dx : 1e-9),
                dy > 0 ? t3 / (dy != 0 ? dy : 1e-9) : t4 / (dy != 0 ? dy : 1e-9));
            double tExit = Math.min(
                dx > 0 ? t2 / (dx != 0 ? dx : 1e-9) : t1 / (dx != 0 ? dx : 1e-9),
                dy > 0 ? t4 / (dy != 0 ? dy : 1e-9) : t3 / (dy != 0 ? dy : 1e-9));
            if (tEnter < tExit && tExit > 0 && tEnter < 1.0) {
                return true;  // 线段在 t∈(0,1) 穿过障碍物
            }
        }
        return false;
    }

    /**
     * 为穿遮挡物的段生成绕行航点: 在遮挡物侧面插入一个中间航点。
     * 策略: 绕行点放在遮挡物 x 外侧(左或右), y 推到可见区(y > OCCLUSION_Y),
     * 使无人机先横移到障碍物侧面(仍可见), 再从侧面滑入遮挡区, 不穿楼。
     */
    private Vector3d makeDetour(Vector3d p1, Vector3d p2) {
        for (double[] o : OBSTACLES) {
            double bxMin = o[0] - o[3] - MARGIN, bxMax = o[0] + o[3] + MARGIN;
            double byMin = o[1] - o[4] - MARGIN, byMax = o[1] + o[4] + MARGIN;
            if (Math.max(p1.x, p2.x) < bxMin || Math.min(p1.x, p2.x) > bxMax) continue;
            if (Math.max(p1.y, p2.y) < byMin || Math.min(p1.y, p2.y) > byMax) continue;
            double midX = (p1.x + p2.x) / 2.0;
            // x: 障碍物外侧(左或右, 取离段中点更远的一侧)
            double sideX = (midX < o[0]) ? bxMin : bxMax;
            // y: 推到可见区(OCCLUSION_Y + 1), 保证绕行时仍可见
            double sideY = OCCLUSION_Y + 1.5;
            double z = (p1.z + p2.z) / 2.0;
            Vector3d detour = new Vector3d(sideX, sideY, z);
            if (!isInsideObstacle(detour)) {
                return detour;
            }
        }
        return null;
    }

    /**
     * 生成随机航点 + 绕行避障 + 计算每段时长。
     * 策略: 约 1/3 航点放在遮挡区(y < OCCLUSION_Y), 使遮挡事件周期性出现;
     *       航点和段都不穿过遮挡物, 如穿过则插入绕行航点。
     */
    private void generateTrajectory() {
        Random rng = new Random(SEED);
        int occlusionCount = 0;
        int targetOcclusion = 2;

        for (int i = 0; i < NUM_WAYPOINTS; i++) {
            boolean wantOcclusion = (i >= 3) && (occlusionCount < targetOcclusion)
                && (i % 4 == 3 || (NUM_WAYPOINTS - i) <= (targetOcclusion - occlusionCount));

            Vector3d wp = null;
            int tries = 0;
            while (tries < 80) {
                double x, y, z;
                if (wantOcclusion) {
                    y = OCCLUSION_Y - 1.0 - rng.nextDouble() * 0.5;  // [-37.5, -36.5], 窄带
                } else {
                    y = (OCCLUSION_Y + 1.0) + rng.nextDouble() * (Y_MAX - OCCLUSION_Y - 1.0);
                }
                x = X_MIN + rng.nextDouble() * (X_MAX - X_MIN);
                z = Z_MIN + rng.nextDouble() * (Z_MAX - Z_MIN);
                Vector3d cand = new Vector3d(x, y, z);
                // 拒绝: 点在遮挡物内 或 与前一航点的连线穿遮挡物
                if (!isInsideObstacle(cand)) {
                    if (i == 0 || !segmentCrossesObstacle(waypoints.get(i - 1), cand)) {
                        // 末→首段也检查(仅最后一段)
                        if (i < NUM_WAYPOINTS - 1
                            || !segmentCrossesObstacle(cand, waypoints.get(0))) {
                            wp = cand;
                            break;
                        }
                    }
                }
                tries++;
            }
            // 80次仍找不到: 退化到可见区中心(保证不穿楼)
            if (wp == null) {
                wp = new Vector3d(0.0, OCCLUSION_Y + 2.0, -11.0);
            }
            if (wantOcclusion) occlusionCount++;
            waypoints.add(wp);
        }

        // 计算每段距离和时长
        int n = waypoints.size();
        for (int i = 0; i < n; i++) {
            Vector3d p0 = waypoints.get(i);
            Vector3d p1 = waypoints.get((i + 1) % n);
            double dx = p0.x - p1.x, dy = p0.y - p1.y, dz = p0.z - p1.z;
            double dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            double speed = SPEED_MIN + rng.nextDouble() * (SPEED_MAX - SPEED_MIN);
            double dur = dist / Math.max(speed, 0.1);
            segmentDurations.add(dur);
            totalDuration += dur;
        }
    }

    /**
     * Catmull-Rom 样条插值。
     * 给定 4 个控制点 p0,p1,p2,p3, 在 t=[0,1] 间插值出 p1→p2 段上的点。
     * 切线 = (p2-p0)/2 和 (p3-p1)/2, 保证过航点且切线连续。
     */
    private Vector3d catmullRom(Vector3d p0, Vector3d p1, Vector3d p2, Vector3d p3, double t) {
        double t2 = t * t;
        double t3 = t2 * t;
        double x = 0.5 * ((2.0 * p1.x)
            + (-p0.x + p2.x) * t
            + (2.0 * p0.x - 5.0 * p1.x + 4.0 * p2.x - p3.x) * t2
            + (-p0.x + 3.0 * p1.x - 3.0 * p2.x + p3.x) * t3);
        double y = 0.5 * ((2.0 * p1.y)
            + (-p0.y + p2.y) * t
            + (2.0 * p0.y - 5.0 * p1.y + 4.0 * p2.y - p3.y) * t2
            + (-p0.y + 3.0 * p1.y - 3.0 * p2.y + p3.y) * t3);
        double z = 0.5 * ((2.0 * p1.z)
            + (-p0.z + p2.z) * t
            + (2.0 * p0.z - 5.0 * p1.z + 4.0 * p2.z - p3.z) * t2
            + (-p0.z + 3.0 * p1.z - 3.0 * p2.z + p3.z) * t3);
        return new Vector3d(x, y, z);
    }

    /**
     * Catmull-Rom 切线(速度方向), 用于计算机头朝向。
     */
    private Vector3d catmullRomTangent(Vector3d p0, Vector3d p1, Vector3d p2, Vector3d p3, double t) {
        double t2 = t * t;
        double dx = 0.5 * ((-p0.x + p2.x)
            + 2.0 * (2.0 * p0.x - 5.0 * p1.x + 4.0 * p2.x - p3.x) * t
            + 3.0 * (-p0.x + 3.0 * p1.x - 3.0 * p2.x + p3.x) * t2);
        double dy = 0.5 * ((-p0.y + p2.y)
            + 2.0 * (2.0 * p0.y - 5.0 * p1.y + 4.0 * p2.y - p3.y) * t
            + 3.0 * (-p0.y + 3.0 * p1.y - 3.0 * p2.y + p3.y) * t2);
        double dz = 0.5 * ((-p0.z + p2.z)
            + 2.0 * (2.0 * p0.z - 5.0 * p1.z + 4.0 * p2.z - p3.z) * t
            + 3.0 * (-p0.z + 3.0 * p1.z - 3.0 * p2.z + p3.z) * t2);
        return new Vector3d(dx, dy, dz);
    }

    @Override
    public void update(long t, boolean paused) {
        if (paused) {
            return;
        }
        if (phaseT0 < 0) {
            phaseT0 = t;
        }

        // 周期内已过时间(秒)
        double elapsed = (t - phaseT0) / 1000.0;
        double te = elapsed % totalDuration;  // 循环

        // 找到当前在第几段
        int n = waypoints.size();
        double acc = 0.0;
        int seg = 0;
        for (int i = 0; i < n; i++) {
            double dur = segmentDurations.get(i);
            if (acc + dur > te) {
                seg = i;
                break;
            }
            acc += dur;
        }
        double segT = (te - acc) / segmentDurations.get(seg);  // [0,1)

        // Catmull-Rom 需要 4 个控制点: p0=seg-1, p1=seg, p2=seg+1, p3=seg+2
        Vector3d p0 = waypoints.get((seg - 1 + n) % n);
        Vector3d p1 = waypoints.get(seg);
        Vector3d p2 = waypoints.get((seg + 1) % n);
        Vector3d p3 = waypoints.get((seg + 2) % n);

        Vector3d pos = catmullRom(p0, p1, p2, p3, segT);
        Vector3d tangent = catmullRomTangent(p0, p1, p2, p3, segT);

        // 速度 = 切线方向 * (段距离/段时长) → 归一化后乘段速
        double dxs = p1.x - p2.x, dys = p1.y - p2.y, dzs = p1.z - p2.z;
        double segLen = Math.sqrt(dxs * dxs + dys * dys + dzs * dzs);
        double segSpeed = segLen / segmentDurations.get(seg);
        double tanLen = Math.sqrt(tangent.x * tangent.x + tangent.y * tangent.y + tangent.z * tangent.z);
        if (tanLen > 1e-6) {
            vel.set(tangent.x / tanLen * segSpeed,
                    tangent.y / tanLen * segSpeed,
                    tangent.z / tanLen * segSpeed);
        } else {
            vel.set(0, 0, 0);
        }

        // 机头朝速度方向(悬停时保持上次偏航)
        double speed = Math.sqrt(vel.x * vel.x + vel.y * vel.y);
        if (speed > 0.1) {
            lastYaw = Math.atan2(vel.y, vel.x);
        }
        rot.rotZ(lastYaw);
        setRotation(rot);
        setPosition(pos);
        setVelocity(vel);
    }
}
