package me.drton.jmavsim;

import javax.imageio.ImageIO;
import javax.media.j3d.Canvas3D;
import javax.media.j3d.ImageComponent2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * GL 离屏帧服务器 —— 干净帧（无 HUD 叠加）TCP 推流，供 Python 算法端识别定位。
 * 协议: 每帧一行头 "FRAME <epoch_ms> <w> <h> <len>\n" + JPEG 字节流。
 * 端口默认 14590 (TCP, localhost)。首帧同时存盘 frame_first.png 便于校验方向。
 */
public class FrameServer implements Runnable {
    private final Canvas3D offCanvas;
    private final int fps;
    private final int port;
    private volatile boolean running = true;
    private final List<OutputStream> clients = new ArrayList<>();
    private boolean firstSaved = false;

    public FrameServer(Canvas3D offCanvas, int fps, int port) {
        this.offCanvas = offCanvas;
        this.fps = fps;
        this.port = port;
    }

    @Override
    public void run() {
        // TCP 接收线程
        Thread acceptor = new Thread(this::acceptLoop, "FrameServer-accept");
        acceptor.setDaemon(true);
        acceptor.start();

        long interval = 1_000_000_000L / fps;
        System.out.println("[FrameServer] streaming " + fps + " fps on tcp:" + port);
        while (running) {
            long t0 = System.nanoTime();
            try {
                offCanvas.renderOffScreenBuffer();
                offCanvas.waitForOffScreenRendering();
                ImageComponent2D buf = offCanvas.getOffScreenBuffer();
                if (buf == null) {
                    continue;
                }
                BufferedImage img = buf.getImage();
                if (img == null) {
                    continue;
                }
                if (!firstSaved) {
                    firstSaved = true;
                    ImageIO.write(img, "png", new File("frame_first.png"));
                    System.out.println("[FrameServer] first frame saved: frame_first.png "
                                       + img.getWidth() + "x" + img.getHeight());
                }
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                ImageIO.write(img, "jpg", baos);
                byte[] data = baos.toByteArray();
                byte[] header = String.format(
                    "FRAME %d %d %d %d%n", System.currentTimeMillis(),
                    img.getWidth(), img.getHeight(), data.length)
                    .getBytes(StandardCharsets.US_ASCII);
                sendToClients(header, data);
            } catch (javax.media.j3d.IllegalRenderingStateException e) {
                System.err.println("[FrameServer] off-screen render failed: " + e);
                return;
            } catch (Exception e) {
                System.err.println("[FrameServer] frame error: " + e);
            }
            long el = System.nanoTime() - t0;
            if (el < interval) {
                try {
                    Thread.sleep((interval - el) / 1_000_000L);
                } catch (InterruptedException e) {
                    return;
                }
            }
        }
    }

    private void acceptLoop() {
        try (ServerSocket ss = new ServerSocket(port, 5,
                                                java.net.InetAddress.getByName("127.0.0.1"))) {
            while (running) {
                Socket s = ss.accept();
                s.setTcpNoDelay(true);
                synchronized (clients) {
                    clients.add(s.getOutputStream());
                }
                System.out.println("[FrameServer] client connected: " + s.getInetAddress());
            }
        } catch (Exception e) {
            if (running) {
                System.err.println("[FrameServer] accept loop stopped: " + e);
            }
        }
    }

    private void sendToClients(byte[] header, byte[] data) {
        synchronized (clients) {
            List<OutputStream> dead = null;
            for (OutputStream os : clients) {
                try {
                    os.write(header);
                    os.write(data);
                    os.flush();
                } catch (Exception e) {
                    if (dead == null) {
                        dead = new ArrayList<>();
                    }
                    dead.add(os);
                }
            }
            if (dead != null) {
                clients.removeAll(dead);
            }
        }
    }

    public void stop() {
        running = false;
    }
}
