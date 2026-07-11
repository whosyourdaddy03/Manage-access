package com.ruoyi.visualization.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.visualization.mapper.VisiualizationDataMapper;
import com.ruoyi.visualization.service.VisiualizationDataService;
import jakarta.servlet.http.HttpServletResponse;
import org.apache.commons.lang3.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

@Service
public class VisiualizationDataServiceImpl implements VisiualizationDataService {

    private final Logger logger = LoggerFactory.getLogger(VisiualizationDataServiceImpl.class);
    private static final ExecutorService executor = Executors.newCachedThreadPool();

    private static final String BASE_IMAGE_PATH_010 = "D:\\BaiduNetdiskDownload\\JPEGImages\\010\\";
    private static final String BASE_IMAGE_PATH_020 = "D:\\BaiduNetdiskDownload\\JPEGImages\\020\\";
    @Autowired
    private VisiualizationDataMapper visiualizationDataMapper;

    /**
     * 获取xml原始数据
     *
     * @param id 标签id
     * @return 数据信息
     */
    @Override
    public JSONObject queryRawData(String id) {
        Map<String, String> map = visiualizationDataMapper.queryRawData(id);
        return (JSONObject) JSON.toJSON(map);
    }


    /**
     * 绘制图片
     *
     * @param id       标签id
     * @param response 服务器响应对象
     */
    @Override
    public void queryPicture(String id, HttpServletResponse response) throws IOException {
        //获取坐标信息
        JSONObject jsonObject = queryRawData(id);
        if (CollectionUtils.isEmpty(jsonObject)) {
            //如果图片不存在，返回 404 并终止
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "图片文件不存在");
            return;
        }

        Integer xmin = jsonObject.getInteger("xmin");
        Integer xmax = jsonObject.getInteger("xmax");
        Integer ymin = jsonObject.getInteger("ymin");
        Integer ymax = jsonObject.getInteger("ymax");

        String filePath = StringUtils.EMPTY;
        if (id.startsWith("01")) {
            filePath = BASE_IMAGE_PATH_010 + id + ".jpg";
        } else if (id.startsWith("02")) {
            filePath = BASE_IMAGE_PATH_020 + id + ".jpg";
        }

        //读取原始图片
        File imageFile = new File(filePath);
        if (!imageFile.exists()) {
            //如果图片不存在，返回 404 并终止
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "图片文件不存在");
            return;
        }
        BufferedImage originalImage = ImageIO.read(imageFile);
        if (originalImage == null) {
            response.sendError(HttpServletResponse.SC_UNSUPPORTED_MEDIA_TYPE, "不支持的图片格式");
            return;
        }

        //绘制红色矩形框
        Graphics2D g2d = originalImage.createGraphics();
        try {
            g2d.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g2d.setColor(Color.RED);
            g2d.setStroke(new BasicStroke(3)); // 边框粗细
            int width = xmax - xmin;
            int height = ymax - ymin;
            g2d.drawRect(xmin, ymin, width, height);
        } finally {
            g2d.dispose();
        }

        //将处理后的图片直接写入响应输出流
        response.setContentType("image/jpeg");
        //可选：禁止缓存（让每次请求都重新生成）
        response.setHeader("Cache-Control", "no-cache, no-store, must-revalidate");
        try (OutputStream out = response.getOutputStream()) {
            ImageIO.write(originalImage, "jpg", out);
            out.flush();
        }
    }

    /**
     * 模型预测结果查询
     *
     * @return
     */
    @Override
    public JSONArray queryPrediction() {
        List<Map<String, String>> list = visiualizationDataMapper.queryPrediction();
        return (JSONArray) JSON.toJSON(list);
    }


    /**
     * 实时模型生成
     *
     * @return
     */
    @Override
    public JSONArray queryAllEpochIds() {
        List<String> list = visiualizationDataMapper.queryAllEpochIds();
        return (JSONArray) JSON.toJSON(list);
    }

    @Override
    public JSONArray queryEpochResults() {
        List<Map<String, Object>> list = visiualizationDataMapper.queryEpochResults();
        return (JSONArray) JSON.toJSON(list);
    }

    @Override
    public JSONArray queryEpochResultsByGroup(String id) {
        List<Map<String, Object>> list = visiualizationDataMapper.queryEpochResultsByGroup(id);
        return (JSONArray) JSON.toJSON(list);
    }

    @Override
    public JSONArray queryDatasetList() {
        List<Map<String, Object>> list = visiualizationDataMapper.queryDatasetList();
        return (JSONArray) JSON.toJSON(list);
    }

    @Override
    public JSONObject queryImageList(String folder, int pageNum, int pageSize) {
        // 确定图片目录
        String imageDir;
        if ("010".equals(folder)) {
            imageDir = BASE_IMAGE_PATH_010;
        } else if ("020".equals(folder)) {
            imageDir = BASE_IMAGE_PATH_020;
        } else {
            imageDir = BASE_IMAGE_PATH_010;
        }

        File dir = new File(imageDir);
        JSONObject result = new JSONObject();

        if (!dir.exists() || !dir.isDirectory()) {
            result.put("total", 0);
            result.put("rows", new JSONArray());
            return result;
        }

        // 获取所有jpg文件并按名称排序
        List<String> allImages = Arrays.stream(Objects.requireNonNull(dir.listFiles((d, name) -> name.toLowerCase().endsWith(".jpg"))))
                .map(File::getName)
                .sorted()
                .collect(Collectors.toList());

        int total = allImages.size();
        int fromIndex = Math.min((pageNum - 1) * pageSize, total);
        int toIndex = Math.min(fromIndex + pageSize, total);

        List<String> pageItems = allImages.subList(fromIndex, toIndex);
        JSONArray rows = new JSONArray();
        for (String fileName : pageItems) {
            JSONObject item = new JSONObject();
            String id = fileName.replace(".jpg", "");
            item.put("id", id);
            item.put("fileName", fileName);
            item.put("folder", folder);
            item.put("imagePath", imageDir + fileName);
            rows.add(item);
        }

        result.put("total", total);
        result.put("rows", rows);
        return result;
    }

    @Override
    public void getRawImage(String id, HttpServletResponse response) throws IOException {
        String filePath = StringUtils.EMPTY;
        if (id.startsWith("01")) {
            filePath = BASE_IMAGE_PATH_010 + id + ".jpg";
        } else if (id.startsWith("02")) {
            filePath = BASE_IMAGE_PATH_020 + id + ".jpg";
        } else {
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "图片ID格式不正确");
            return;
        }

        File imageFile = new File(filePath);
        if (!imageFile.exists()) {
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "图片文件不存在");
            return;
        }

        BufferedImage originalImage = ImageIO.read(imageFile);
        if (originalImage == null) {
            response.sendError(HttpServletResponse.SC_UNSUPPORTED_MEDIA_TYPE, "不支持的图片格式");
            return;
        }

        response.setContentType("image/jpeg");
        response.setHeader("Cache-Control", "max-age=3600");
        try (OutputStream out = response.getOutputStream()) {
            ImageIO.write(originalImage, "jpg", out);
            out.flush();
        }
    }

    @Override
    public void generationModel() {
        // 1. 构建进程
        ProcessBuilder pb = new ProcessBuilder("python", "-u", "D:\\BaiduNetdiskDownload\\test_script.py");
        // 2. 强制 Python 使用 UTF-8 输出
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        // 3. 合并错误流到标准输出流，便于统一读取
        pb.redirectErrorStream(true);

        try {
            Process process = pb.start();

            // 4. 异步读取输出（避免主线程阻塞）
            executor.submit(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        // 使用若依的日志打印，支持中文和特殊符号
                        logger.info("Python输出: {}", line);
                    }
                } catch (IOException e) {
                    logger.error("读取Python输出失败", e);
                } finally {
                    // 可选：等待进程结束并回收资源（不阻塞主线程）
                    try {
                        int exitCode = process.waitFor();
                        logger.info("Python脚本执行完毕，退出码: {}", exitCode);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        logger.warn("等待Python进程被中断");
                    }
                }
            });
            // 5. 主线程立即返回
            logger.info("Python脚本已异步启动，不等待结果。");
        } catch (IOException e) {
            logger.error("启动Python脚本失败", e);
        }
    }
}
