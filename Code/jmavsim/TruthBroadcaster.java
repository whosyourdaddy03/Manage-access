package me.drton.jmavsim;

import javax.vecmath.Vector3d;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;

/**
 * 真值 UDP 广播（50Hz）—— 论文闭环实验的"数据支撑"。
 * 向 127.0.0.1:<port> 发送 ASCII 行：
 *   t=<epoch_ms> tp=x,y,z tv=vx,vy,vz ep=x,y,z
 * 其中 tp/tv 为目标机位置/速度（世界系 NED），ep 为 ego 机位置。
 * 读值块与仿真线程同步（synchronized(world)），避免撕裂读。
 */
public class TruthBroadcaster implements Runnable {
    private final KinematicObject target;
    private final KinematicObject ego;
    private final int port;
    private volatile boolean running = true;

    public TruthBroadcaster(KinematicObject target, KinematicObject ego, int port) {
        this.target = target;
        this.ego = ego;
        this.port = port;
    }

    @Override
    public void run() {
        DatagramSocket sock = null;
        try {
            sock = new DatagramSocket();
            InetAddress addr = InetAddress.getByName("127.0.0.1");
            while (running) {
                long ts = System.currentTimeMillis();
                String msg;
                synchronized (target.getWorld()) {
                    Vector3d p = target.getPosition();
                    Vector3d v = target.getVelocity();
                    Vector3d e = ego.getPosition();
                    msg = String.format(
                        "t=%d tp=%.3f,%.3f,%.3f tv=%.3f,%.3f,%.3f ep=%.3f,%.3f,%.3f",
                        ts, p.x, p.y, p.z, v.x, v.y, v.z, e.x, e.y, e.z);
                }
                byte[] b = msg.getBytes(StandardCharsets.US_ASCII);
                sock.send(new DatagramPacket(b, b.length, addr, port));
                Thread.sleep(20);   // 50 Hz
            }
        } catch (Exception e) {
            System.err.println("TruthBroadcaster stopped: " + e);
        } finally {
            if (sock != null) {
                sock.close();
            }
        }
    }

    public void stop() {
        running = false;
    }
}
